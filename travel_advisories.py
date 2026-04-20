"""
Travel advisory fetchers — UK FCDO, US State Department, Australian DFAT, French MEAE.

Server-side Python port of the JS parsers in acled-fetcher-main/docs/index.html.
Direct HTTP requests are used (no CORS proxies needed server-side).
"""
import asyncio
import re
from datetime import datetime, timezone
from html.parser import HTMLParser

import httpx


# ---------------------------------------------------------------------------
# HTML utilities
# ---------------------------------------------------------------------------

class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._parts: list[str] = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "head", "noscript"):
            self._skip = True

    def handle_endtag(self, tag):
        if tag in ("script", "style", "head", "noscript"):
            self._skip = False

    def handle_data(self, data):
        if not self._skip:
            self._parts.append(data)

    def result(self) -> str:
        return re.sub(r"\s+", " ", "".join(self._parts)).strip()


def _html_to_text(raw: str) -> str:
    p = _TextExtractor()
    try:
        p.feed(raw or "")
    except Exception:
        pass
    return p.result()


def _extract_primary_driver(text: str) -> str:
    t = (text or "").lower()
    rules = [
        (r"terroris|terrorist|attentat", "Terrorism risk"),
        (r"kidnap|abduct", "Kidnapping risk"),
        (r"civil unrest|unrest|demonstration|protest", "Civil unrest"),
        (r"armed conflict|conflict|war|fighting|insurg", "Armed conflict"),
        (r"violent crime|crime|carjacking|robbery", "Violent crime"),
        (r"health|disease|outbreak|epidemic", "Health risk"),
        (r"natural disaster|flood|cyclone|earthquake", "Natural hazards"),
    ]
    for pattern, label in rules:
        if re.search(pattern, t):
            return label
    return "Security risk"


# ---------------------------------------------------------------------------
# Country profile lookup (handles tricky names / alternate slugs)
# ---------------------------------------------------------------------------

_PROFILES: dict[str, dict] = {
    "republic of the congo": {
        "aliases": ["congo", "republic of congo", "congo brazzaville", "roc"],
        "fcdo_slugs": ["congo"],
        "french_slugs": ["republique-du-congo", "congo"],
        "dfat_names": ["Republic of the Congo", "Congo, Republic of", "Congo-Brazzaville"],
        "state_dept_names": ["Congo (Brazzaville)", "Republic of the Congo"],
    },
    "democratic republic of the congo": {
        "aliases": ["drc", "dr congo", "congo kinshasa", "democratic republic of congo"],
        "fcdo_slugs": ["democratic-republic-of-the-congo"],
        "french_slugs": ["republique-democratique-du-congo"],
        "dfat_names": ["Democratic Republic of the Congo", "DR Congo"],
        "state_dept_names": ["Congo (Kinshasa)", "Democratic Republic of the Congo"],
    },
    "ivory coast": {
        "aliases": ["cote d'ivoire", "cote divoire", "côte d'ivoire"],
        "fcdo_slugs": ["cote-d-ivoire"],
        "french_slugs": ["cote-d-ivoire"],
        "dfat_names": ["Côte d'Ivoire", "Cote d'Ivoire", "Ivory Coast"],
        "state_dept_names": ["Cote d'Ivoire", "Ivory Coast"],
    },
    "central african republic": {
        "aliases": ["car"],
        "fcdo_slugs": ["central-african-republic"],
        "french_slugs": ["republique-centrafricaine"],
        "dfat_names": ["Central African Republic"],
        "state_dept_names": ["Central African Republic"],
    },
    "sao tome and principe": {
        "aliases": [],
        "fcdo_slugs": ["sao-tome-and-principe"],
        "french_slugs": ["sao-tome-et-principe"],
        "dfat_names": ["Sao Tome and Principe"],
        "state_dept_names": ["Sao Tome and Principe"],
    },
    "cabo verde": {
        "aliases": ["cape verde"],
        "fcdo_slugs": ["cape-verde"],
        "french_slugs": ["cap-vert"],
        "dfat_names": ["Cabo Verde", "Cape Verde"],
        "state_dept_names": ["Cabo Verde", "Cape Verde"],
    },
    "eswatini": {
        "aliases": ["swaziland"],
        "fcdo_slugs": ["eswatini"],
        "french_slugs": ["eswatini"],
        "dfat_names": ["Eswatini"],
        "state_dept_names": ["Eswatini"],
    },
    "equatorial guinea": {
        "aliases": [],
        "fcdo_slugs": ["equatorial-guinea"],
        "french_slugs": ["guinee-equatoriale"],
        "dfat_names": ["Equatorial Guinea"],
        "state_dept_names": ["Equatorial Guinea"],
    },
    "guinea-bissau": {
        "aliases": [],
        "fcdo_slugs": ["guinea-bissau"],
        "french_slugs": ["guinee-bissau"],
        "dfat_names": ["Guinea-Bissau"],
        "state_dept_names": ["Guinea-Bissau"],
    },
    "burkina faso": {
        "aliases": [],
        "fcdo_slugs": ["burkina-faso"],
        "french_slugs": ["burkina-faso"],
        "dfat_names": ["Burkina Faso"],
        "state_dept_names": ["Burkina Faso"],
    },
    "sierra leone": {
        "aliases": [],
        "fcdo_slugs": ["sierra-leone"],
        "french_slugs": ["sierra-leone"],
        "dfat_names": ["Sierra Leone"],
        "state_dept_names": ["Sierra Leone"],
    },
    "south africa": {
        "aliases": [],
        "fcdo_slugs": ["south-africa"],
        "french_slugs": ["afrique-du-sud"],
        "dfat_names": ["South Africa"],
        "state_dept_names": ["South Africa"],
    },
    "south sudan": {
        "aliases": [],
        "fcdo_slugs": ["south-sudan"],
        "french_slugs": ["soudan-du-sud"],
        "dfat_names": ["South Sudan"],
        "state_dept_names": ["South Sudan"],
    },
}


def _resolve_profile(country: str) -> dict:
    key = re.sub(r"\s+", " ", (country or "").lower().strip())
    for canonical, profile in _PROFILES.items():
        candidates = [canonical] + [a.lower() for a in profile.get("aliases", [])]
        if key in candidates:
            return {**profile, "canonical": canonical.title()}
    slug = re.sub(r"[^a-z0-9]+", "-", key).strip("-")
    name = " ".join(w.capitalize() for w in country.strip().split())
    return {
        "canonical": name,
        "fcdo_slugs": [slug],
        "french_slugs": [slug],
        "dfat_names": [name],
        "state_dept_names": [name],
    }


# ---------------------------------------------------------------------------
# UK FCDO
# ---------------------------------------------------------------------------

async def fetch_fcdo(client: httpx.AsyncClient, country: str) -> dict:
    profile = _resolve_profile(country)
    for slug in profile["fcdo_slugs"]:
        resp = await client.get(
            f"https://www.gov.uk/api/content/foreign-travel-advice/{slug}",
            timeout=15,
        )
        if resp.status_code == 404:
            continue
        resp.raise_for_status()
        data = resp.json()
        details = data.get("details", {})
        statuses = details.get("alert_status", [])

        level, level_text = 1, "Normal caution"
        advisory = f"FCDO advises normal caution for {profile['canonical']}."
        if "avoid_all_travel" in statuses or "avoid_all_travel_to_whole_country" in statuses:
            level, level_text = 4, "Advises against all travel"
            advisory = f"FCDO advises against all travel to {profile['canonical']}."
        elif "avoid_all_travel_to_parts" in statuses:
            level, level_text = 3, "Advises against all travel to parts"
            advisory = f"FCDO advises against all travel to parts of {profile['canonical']}."
        elif "avoid_all_but_essential_travel" in statuses:
            level, level_text = 3, "Advises against all but essential travel"
            advisory = f"FCDO advises against all but essential travel to {profile['canonical']}."
        elif "avoid_all_but_essential_travel_to_parts" in statuses:
            level, level_text = 2, "Advises against all but essential travel to parts"
            advisory = f"FCDO advises against all but essential travel to parts of {profile['canonical']}."

        safety_text = ""
        for part in details.get("parts", []):
            if "safety" in (part.get("slug") or ""):
                safety_text = _html_to_text(part.get("body", ""))
                break

        history = details.get("change_history", [])
        updated_raw = (history[0].get("public_timestamp") if history else None) or data.get("public_updated_at")

        return {
            "level": level,
            "level_text": level_text,
            "advisory": advisory,
            "updated_at": updated_raw,
            "primary_driver": _extract_primary_driver(safety_text),
            "url": f"https://www.gov.uk/foreign-travel-advice/{slug}",
        }
    return {"error": f"No FCDO advisory found for '{country}'"}


# ---------------------------------------------------------------------------
# US State Department (ArcGIS)
# ---------------------------------------------------------------------------

async def fetch_state_dept(client: httpx.AsyncClient, country: str) -> dict:
    profile = _resolve_profile(country)
    level_map = {
        1: "Level 1: Exercise Normal Precautions",
        2: "Level 2: Exercise Increased Caution",
        3: "Level 3: Reconsider Travel",
        4: "Level 4: Do Not Travel",
    }
    base = "https://gis.state.gov/arcgis/rest/services/travel/Travel/MapServer/0/query"

    for name in profile["state_dept_names"]:
        where = f"Country_Name = '{name.replace(chr(39), chr(39)*2)}'"
        try:
            resp = await client.get(f"{base}?f=json&where={where}&outFields=*", timeout=15)
            resp.raise_for_status()
            features = resp.json().get("features", [])
            if not features:
                continue
            attrs = features[0].get("attributes", {})
            level = int(attrs.get("Advisory_Level") or 0)
            updated_at = None
            if attrs.get("Date_Updated"):
                try:
                    updated_at = datetime.fromtimestamp(
                        int(attrs["Date_Updated"]) / 1000, tz=timezone.utc
                    ).strftime("%Y-%m-%d")
                except Exception:
                    pass
            return {
                "level": level if 1 <= level <= 4 else 0,
                "level_text": level_map.get(level, "Advisory level unavailable"),
                "advisory": f"US State Department {level_map.get(level, 'advisory')} for {attrs.get('Country_Name', profile['canonical'])}.",
                "updated_at": updated_at,
                "primary_driver": _extract_primary_driver(
                    attrs.get("Advisory_Text") or attrs.get("Latest_Headline") or ""
                ),
                "url": "https://travel.state.gov/content/travel/en/traveladvisories/traveladvisories.html",
            }
        except Exception:
            continue
    return {"error": f"No US State Department advisory found for '{country}'"}


# ---------------------------------------------------------------------------
# Australian DFAT
# Fetch the destinations table once (shared across countries) for efficiency.
# ---------------------------------------------------------------------------

def _parse_dfat_table(html: str) -> dict[str, dict]:
    """Parse the smartraveller.gov.au/destinations table into {country_name_lower: entry}."""
    result: dict[str, dict] = {}
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.DOTALL | re.IGNORECASE)
    for row in rows:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL | re.IGNORECASE)
        if len(cells) < 3:
            continue
        name = _html_to_text(cells[0]).strip()
        if not name:
            continue
        href_m = re.search(r'href="(/destinations/[^"]+)"', cells[0])
        result[name.lower()] = {
            "name": name,
            "level_text": _html_to_text(cells[2]).strip(),
            "updated_at": _html_to_text(cells[3]).strip() if len(cells) > 3 else None,
            "href": href_m.group(1) if href_m else None,
        }
    return result


async def fetch_dfat_table(client: httpx.AsyncClient) -> dict[str, dict]:
    resp = await client.get("https://www.smartraveller.gov.au/destinations", timeout=20)
    resp.raise_for_status()
    return _parse_dfat_table(resp.text)


async def fetch_dfat(client: httpx.AsyncClient, country: str, table: dict[str, dict] | None = None) -> dict:
    profile = _resolve_profile(country)
    level_map = {
        "do not travel": 4,
        "reconsider your need to travel": 3,
        "exercise a high degree of caution": 2,
        "exercise normal safety precautions": 1,
    }

    if table is None:
        try:
            table = await fetch_dfat_table(client)
        except Exception as e:
            return {"error": f"Failed to fetch DFAT destinations table: {e}"}

    entry = None
    for name in profile["dfat_names"]:
        entry = table.get(name.lower())
        if entry:
            break

    if not entry:
        return {"error": f"No DFAT advisory found for '{country}'"}

    level = level_map.get((entry["level_text"] or "").lower(), 0)
    advisory = f"DFAT advises: {entry['level_text']} for {entry['name']}."
    primary_driver = "Security risk"

    if entry.get("href"):
        try:
            detail = await client.get(
                f"https://www.smartraveller.gov.au{entry['href']}", timeout=15
            )
            if detail.status_code == 200:
                detail_text = _html_to_text(detail.text)
                primary_driver = _extract_primary_driver(detail_text)
                m = re.search(r"Latest update:\s*([^.]+\.)", detail_text, re.IGNORECASE)
                if m:
                    advisory = m.group(1).strip()
        except Exception:
            pass

    return {
        "level": level,
        "level_text": entry["level_text"],
        "advisory": advisory,
        "updated_at": entry.get("updated_at"),
        "primary_driver": primary_driver,
        "url": f"https://www.smartraveller.gov.au{entry['href']}" if entry.get("href") else "https://www.smartraveller.gov.au/destinations",
    }


# ---------------------------------------------------------------------------
# French MEAE
# ---------------------------------------------------------------------------

async def fetch_meae(client: httpx.AsyncClient, country: str) -> dict:
    profile = _resolve_profile(country)
    candidates = []
    for slug in profile["french_slugs"]:
        candidates += [
            f"https://www.diplomatie.gouv.fr/fr/information-par-pays/{slug}/conseils-aux-voyageurs-securite",
            f"https://www.diplomatie.gouv.fr/fr/conseils-aux-voyageurs/conseils-par-pays-destination/{slug}/",
        ]

    for url in candidates:
        try:
            resp = await client.get(url, timeout=20, follow_redirects=True)
            if resp.status_code != 200 or len(resp.text) < 1200:
                continue
            text = _html_to_text(resp.text)

            level, level_text = 0, "See advisory page"
            if re.search(r"formellement\s+d[eé]conseill", text, re.IGNORECASE):
                level, level_text = 4, "Formally advised against"
            elif re.search(r"d[eé]conseill\S+\s+sauf\s+raison\s+imp[eé]rative", text, re.IGNORECASE):
                level, level_text = 3, "Advised against except for imperative reasons"
            elif re.search(r"vigilance\s+renforc[eé]e", text, re.IGNORECASE):
                level, level_text = 2, "Enhanced vigilance"

            updated_m = re.search(r"Derni[eè]re mise [aà] jour\s*:?\s*([^\-\n]{5,40})", text, re.IGNORECASE)

            return {
                "level": level,
                "level_text": level_text,
                "advisory": f"MEAE advises: {level_text} for {profile['canonical']}.",
                "updated_at": updated_m.group(1).strip() if updated_m else None,
                "primary_driver": _extract_primary_driver(text),
                "url": url,
            }
        except Exception:
            continue

    return {"error": f"No MEAE advisory found for '{country}'"}


# ---------------------------------------------------------------------------
# Combined single-country fetch
# ---------------------------------------------------------------------------

async def fetch_all_advisories(country: str) -> dict:
    async with httpx.AsyncClient(follow_redirects=True) as client:
        results = await asyncio.gather(
            fetch_fcdo(client, country),
            fetch_state_dept(client, country),
            fetch_dfat(client, country),
            fetch_meae(client, country),
            return_exceptions=True,
        )
    labels = ("fcdo", "us_state_dept", "aus_dfat", "french_meae")
    return {
        "country": country,
        **{
            label: ({"error": str(r)} if isinstance(r, Exception) else r)
            for label, r in zip(labels, results)
        },
    }


# ---------------------------------------------------------------------------
# Bulk fetch for all countries (used by cron — fetches DFAT table once)
# ---------------------------------------------------------------------------

async def fetch_advisories_for_countries(countries: list[str]) -> dict[str, dict]:
    async with httpx.AsyncClient(follow_redirects=True) as client:
        # Fetch DFAT table once
        try:
            dfat_table = await fetch_dfat_table(client)
        except Exception:
            dfat_table = {}

        sem = asyncio.Semaphore(8)

        async def _fetch_one(country: str) -> tuple[str, dict]:
            async with sem:
                fcdo, state, dfat, meae = await asyncio.gather(
                    fetch_fcdo(client, country),
                    fetch_state_dept(client, country),
                    fetch_dfat(client, country, table=dfat_table),
                    fetch_meae(client, country),
                    return_exceptions=True,
                )
            labels = ("fcdo", "us_state_dept", "aus_dfat", "french_meae")
            return country, {
                label: ({"error": str(r)} if isinstance(r, Exception) else r)
                for label, r in zip(labels, (fcdo, state, dfat, meae))
            }

        pairs = await asyncio.gather(*[_fetch_one(c) for c in countries])
    return dict(pairs)
