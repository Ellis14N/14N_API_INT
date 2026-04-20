"""
Travel advisory fetchers — UK FCDO, US State Department, Australian DFAT, French MEAE.

Independent travel advisory parsers and normalizers. These functions fetch and
normalize government travel advisories and are explicitly independent from any
ACLED conflict-event data or ACLED-specific processing.
Direct HTTP requests are used (no CORS proxies needed server-side).
"""
import asyncio
import re
import unicodedata
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


def _normalize_name_for_lookup(name: str) -> str:
    """Normalize a country/destination name for stable lookup (strip accents/punctuation)."""
    if not name:
        return ""
    s = unicodedata.normalize("NFKD", name)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9\s]", "", s.lower())
    s = re.sub(r"\s+", " ", s).strip()
    return s


async def _fetch_state_dept_cadata_map(client: httpx.AsyncClient) -> dict:
    """Fetch the State Dept TravelAdvisories JSON feed and return a mapping of
    normalized country name -> advisory dict.

    This feed is faster and more stable than ArcGIS for simple advisory lookups.
    """
    url = "https://cadataapi.state.gov/api/TravelAdvisories"
    try:
        resp = await client.get(url, timeout=20)
        resp.raise_for_status()
        arr = resp.json()
    except Exception:
        return {}

    mapping: dict[str, dict] = {}
    for item in arr:
        title = item.get("Title") or ""
        link = item.get("Link") or item.get("id")
        summary = item.get("Summary") or ""
        published = item.get("Published") or item.get("Updated")

        m = re.match(r"^(?P<country>.+?)\s*-\s*Level\s*(?P<level>\d+):\s*(?P<level_text>.+)$", title)
        if m:
            country = m.group("country").strip()
            try:
                level = int(m.group("level"))
            except Exception:
                level = 0
            level_text = m.group("level_text").strip()
        else:
            # Fallbacks
            parts = title.split(" - ")
            country = parts[0].strip() if parts else title.strip()
            lm = re.search(r"Level\s*(\d+)", title)
            level = int(lm.group(1)) if lm else 0
            # take remainder of title after first dash as text
            level_text = parts[1].strip() if len(parts) > 1 else ""

        key = _normalize_name_for_lookup(country)
        mapping[key] = {
            "level": level,
            "level_text": level_text,
            "advisory": _html_to_text(summary) if summary else title,
            "updated_at": published,
            "primary_driver": _extract_primary_driver(summary),
            "url": link,
            "source": "cadataapi",
        }

    return mapping


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
        "dfat_hrefs": ["/destinations/africa/cote-divoire-ivory-coast"],
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
    # First try the CA Data API feed for a quick, reliable match
    try:
        cadata_map = await _fetch_state_dept_cadata_map(client)
        for name in profile.get("state_dept_names", []):
            k = _normalize_name_for_lookup(name)
            if k in cadata_map:
                return cadata_map[k]
    except Exception:
        cadata_map = {}

    # Fallback: try the direct travel.state.gov country page (slug-based)
    # This helps when the CA feed or ArcGIS do not include an exact match.
    slug_candidates = [profile.get("canonical")] + profile.get("state_dept_names", [])
    for cand in slug_candidates:
        if not cand:
            continue
        slug = re.sub(r"[^a-z0-9]+", "-", cand.lower()).strip("-")
        url = f"https://travel.state.gov/content/travel/en/traveladvisories/traveladvisories/{slug}-travel-advisory.html"
        try:
            resp = await client.get(url, timeout=15)
            if resp.status_code != 200:
                continue
            text = _html_to_text(resp.text)
            # Look for 'Level X' in the text
            m = re.search(r"Level\s*([1-4])\b", text, re.IGNORECASE)
            if not m:
                continue
            level = int(m.group(1))
            # Try to extract a short level_text nearby
            m2 = re.search(rf"{re.escape('Level')}\s*{level}\s*[:\-]?\s*([^\n\r\.\,]{{5,200}})", text, re.IGNORECASE)
            level_text = m2.group(1).strip() if m2 else f"Level {level}"
            return {
                "level": level if 1 <= level <= 4 else 0,
                "level_text": level_map.get(level, level_text),
                "advisory": level_text,
                "updated_at": None,
                "primary_driver": _extract_primary_driver(text),
                "url": url,
            }
        except Exception:
            continue

    # Try a sequence of increasingly loose queries against the ArcGIS layer.
    for name in profile["state_dept_names"]:
        # Variants to try: exact, stripped-parentheses, and token-based searches
        variants = [name, re.sub(r"\s*\([^)]*\)", "", name).strip()]
        norm = _normalize_name_for_lookup(name)
        tokens = [t for t in norm.split() if len(t) > 3]

        tried = set()

        async def _try_where(where_clause: str):
            if where_clause in tried:
                return None
            tried.add(where_clause)
            try:
                resp = await client.get(base, params={"f": "json", "where": where_clause, "outFields": "*"}, timeout=15)
                resp.raise_for_status()
                features = resp.json().get("features", [])
                if not features:
                    return None
                return features[0].get("attributes", {})
            except Exception:
                return None

        # Exact + LIKE attempts for each variant
        for v in variants:
            v_clean = v.replace("'", "''")
            attrs = await _try_where(f"Country_Name = '{v_clean}'")
            if attrs:
                level = int(attrs.get("Advisory_Level") or 0)
                updated_at = None
                if attrs.get("Date_Updated"):
                    try:
                        updated_at = datetime.fromtimestamp(int(attrs["Date_Updated"]) / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
                    except Exception:
                        pass
                return {
                    "level": level if 1 <= level <= 4 else 0,
                    "level_text": level_map.get(level, "Advisory level unavailable"),
                    "advisory": f"US State Department {level_map.get(level, 'advisory')} for {attrs.get('Country_Name', profile['canonical'])}.",
                    "updated_at": updated_at,
                    "primary_driver": _extract_primary_driver(attrs.get("Advisory_Text") or attrs.get("Latest_Headline") or ""),
                    "url": "https://travel.state.gov/content/travel/en/traveladvisories/traveladvisories.html",
                }

            attrs = await _try_where(f"Country_Name LIKE '%{v_clean}%'")
            if attrs:
                level = int(attrs.get("Advisory_Level") or 0)
                updated_at = None
                if attrs.get("Date_Updated"):
                    try:
                        updated_at = datetime.fromtimestamp(int(attrs["Date_Updated"]) / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
                    except Exception:
                        pass
                return {
                    "level": level if 1 <= level <= 4 else 0,
                    "level_text": level_map.get(level, "Advisory level unavailable"),
                    "advisory": f"US State Department {level_map.get(level, 'advisory')} for {attrs.get('Country_Name', profile['canonical'])}.",
                    "updated_at": updated_at,
                    "primary_driver": _extract_primary_driver(attrs.get("Advisory_Text") or attrs.get("Latest_Headline") or ""),
                    "url": "https://travel.state.gov/content/travel/en/traveladvisories/traveladvisories.html",
                }

        # Token-based LIKE queries
        for token in tokens:
            token_clean = token.replace("'", "''")
            attrs = await _try_where(f"Country_Name LIKE '%{token_clean}%'")
            if attrs:
                level = int(attrs.get("Advisory_Level") or 0)
                updated_at = None
                if attrs.get("Date_Updated"):
                    try:
                        updated_at = datetime.fromtimestamp(int(attrs["Date_Updated"]) / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
                    except Exception:
                        pass
                return {
                    "level": level if 1 <= level <= 4 else 0,
                    "level_text": level_map.get(level, "Advisory level unavailable"),
                    "advisory": f"US State Department {level_map.get(level, 'advisory')} for {attrs.get('Country_Name', profile['canonical'])}.",
                    "updated_at": updated_at,
                    "primary_driver": _extract_primary_driver(attrs.get("Advisory_Text") or attrs.get("Latest_Headline") or ""),
                    "url": "https://travel.state.gov/content/travel/en/traveladvisories/traveladvisories.html",
                }

        # Final fallback: fetch all features with advisory levels and match locally
        try:
            params = {
                "f": "json",
                "where": "Advisory_Level IS NOT NULL",
                "outFields": "Country_Name,Advisory_Level,Advisory_Text,Latest_Headline,Date_Updated",
                "resultRecordCount": 1000,
            }
            resp = await client.get(base, params=params, timeout=30)
            resp.raise_for_status()
            features = resp.json().get("features", [])
            if features:
                # Build mapping of normalized country name -> attrs
                mapping = {}
                for f in features:
                    attrs = f.get("attributes", {})
                    cn = attrs.get("Country_Name") or ""
                    mapping[_normalize_name_for_lookup(cn)] = attrs

                # Look for best match among profile names
                for cand in profile["state_dept_names"]:
                    n = _normalize_name_for_lookup(cand)
                    if n in mapping:
                        attrs = mapping[n]
                        level = int(attrs.get("Advisory_Level") or 0)
                        updated_at = None
                        if attrs.get("Date_Updated"):
                            try:
                                updated_at = datetime.fromtimestamp(int(attrs["Date_Updated"]) / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
                            except Exception:
                                pass
                        return {
                            "level": level if 1 <= level <= 4 else 0,
                            "level_text": level_map.get(level, "Advisory level unavailable"),
                            "advisory": f"US State Department {level_map.get(level, 'advisory')} for {attrs.get('Country_Name', profile['canonical'])}.",
                            "updated_at": updated_at,
                            "primary_driver": _extract_primary_driver(attrs.get("Advisory_Text") or attrs.get("Latest_Headline") or ""),
                            "url": "https://travel.state.gov/content/travel/en/traveladvisories/traveladvisories.html",
                        }
                # token fallback
                for cand in profile["state_dept_names"]:
                    n = _normalize_name_for_lookup(cand)
                    for k, attrs in mapping.items():
                        if n in k or k in n:
                            level = int(attrs.get("Advisory_Level") or 0)
                            updated_at = None
                            if attrs.get("Date_Updated"):
                                try:
                                    updated_at = datetime.fromtimestamp(int(attrs["Date_Updated"]) / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
                                except Exception:
                                    pass
                            return {
                                "level": level if 1 <= level <= 4 else 0,
                                "level_text": level_map.get(level, "Advisory level unavailable"),
                                "advisory": f"US State Department {level_map.get(level, 'advisory')} for {attrs.get('Country_Name', profile['canonical'])}.",
                                "updated_at": updated_at,
                                "primary_driver": _extract_primary_driver(attrs.get("Advisory_Text") or attrs.get("Latest_Headline") or ""),
                                "url": "https://travel.state.gov/content/travel/en/traveladvisories/traveladvisories.html",
                            }
        except Exception:
            pass

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
        key = _normalize_name_for_lookup(name)
        result[key] = {
            "name": name,
            "level_text": _html_to_text(cells[2]).strip(),
            "updated_at": _html_to_text(cells[3]).strip() if len(cells) > 3 else None,
            "href": href_m.group(1) if href_m else None,
        }
    return result


async def fetch_dfat_table(client: httpx.AsyncClient) -> dict[str, dict]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }

    # 1) Official DFAT export (preferred): https://www.smartraveller.gov.au/destinations-export
    try:
        resp = await client.get("https://www.smartraveller.gov.au/destinations-export", timeout=20, follow_redirects=True, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            # data may be a list or a dict containing a list under common keys
            items = []
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                for k in ("advisories", "destinations", "items", "data"):
                    if isinstance(data.get(k), list):
                        items = data.get(k)
                        break
                if not items:
                    # maybe top-level dict of slugs
                    # attempt to coerce values that look like entries
                    items = [v for v in data.values() if isinstance(v, dict)]

            mapping: dict[str, dict] = {}
            for it in items:
                if not isinstance(it, dict):
                    continue
                # robust field extraction across variations
                name = None
                if isinstance(it.get("country"), dict):
                    name = it.get("country", {}).get("name")
                name = name or it.get("name") or it.get("title") or it.get("pageTitle") or it.get("countryName")
                if not name:
                    continue
                advice = it.get("advice") or it.get("levelText") or it.get("latestUpdate") or it.get("description") or ""
                level = it.get("level") or it.get("adviceLevel") or None
                published = it.get("published") or it.get("lastUpdated") or it.get("lastFetched") or None
                pageUrl = it.get("pageUrl") or it.get("url") or it.get("link") or None

                key = _normalize_name_for_lookup(name)
                mapping[key] = {
                    "name": name,
                    "level": int(level) if (isinstance(level, int) or (isinstance(level, str) and level.isdigit())) else 0,
                    "level_text": str(advice) if advice else "",
                    "advisory": _html_to_text(advice) if isinstance(advice, str) else str(advice),
                    "updated_at": published,
                    "primary_driver": _extract_primary_driver(advice),
                    "href": pageUrl,
                    "source": "dfat-export",
                }
            if mapping:
                return mapping
    except Exception:
        pass

    # 2) Public third-party API (kevle1) as a fallback: https://smartraveller.kevle.xyz/api/advisories
    try:
        resp = await client.get("https://smartraveller.kevle.xyz/api/advisories", timeout=15)
        if resp.status_code == 200:
            j = resp.json()
            arr = j.get("advisories") if isinstance(j, dict) and isinstance(j.get("advisories"), list) else (j if isinstance(j, list) else [])
            mapping = {}
            for it in arr:
                if not isinstance(it, dict):
                    continue
                country = it.get("country") or {}
                name = country.get("name") if isinstance(country, dict) else it.get("name") or it.get("title")
                if not name:
                    continue
                advice = it.get("advice") or it.get("latestUpdate") or ""
                level = it.get("level") or None
                pageUrl = it.get("pageUrl") or it.get("url") or None
                key = _normalize_name_for_lookup(name)
                mapping[key] = {
                    "name": name,
                    "level": int(level) if (isinstance(level, int) or (isinstance(level, str) and level.isdigit())) else 0,
                    "level_text": advice,
                    "advisory": _html_to_text(advice) if isinstance(advice, str) else str(advice),
                    "updated_at": it.get("published") or it.get("lastFetched"),
                    "primary_driver": _extract_primary_driver(advice),
                    "href": pageUrl,
                    "source": "smartraveller-kevle",
                }
            if mapping:
                return mapping
    except Exception:
        pass

    # 3) Last-resort: parse the HTML destinations index (original behavior)
    try:
        resp = await client.get("https://www.smartraveller.gov.au/destinations", timeout=20, follow_redirects=True, headers=headers)
        resp.raise_for_status()
        return _parse_dfat_table(resp.text)
    except Exception:
        return {}


async def fetch_dfat(client: httpx.AsyncClient, country: str, table: dict[str, dict] | None = None) -> dict:
    profile = _resolve_profile(country)
    level_map = {
        "do not travel": 4,
        "reconsider your need to travel": 3,
        "exercise a high degree of caution": 2,
        "exercise normal safety precautions": 1,
    }

    # If the profile includes direct DFAT hrefs, try them first (reliable when index fetch fails)
    if profile.get("dfat_hrefs"):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }
        for href in profile.get("dfat_hrefs", []):
            url = f"https://www.smartraveller.gov.au{href}"
            try:
                resp = await client.get(url, timeout=15, follow_redirects=True, headers=headers)
                if resp.status_code != 200:
                    continue
                page_text = _html_to_text(resp.text)
                txt = (page_text or "").lower()
                dfat_map = {
                    "do not travel": 4,
                    "reconsider your need to travel": 3,
                    "exercise a high degree of caution": 2,
                    "exercise normal safety precautions": 1,
                }
                level = 0
                level_text = None
                for phrase, lvl in dfat_map.items():
                    if phrase in txt:
                        level = lvl
                        level_text = phrase.title()
                        break
                if level == 0:
                    m = re.search(r"level\s*([1-4])", txt, re.IGNORECASE)
                    if m:
                        level = int(m.group(1))
                        level_text = level_map.get(level)
                if level:
                    return {
                        "level": level,
                        "level_text": level_text or "See advisory page",
                        "advisory": (page_text.split('\n')[0] if page_text else ""),
                        "updated_at": None,
                        "primary_driver": _extract_primary_driver(page_text),
                        "url": url,
                    }
            except Exception:
                continue

    if table is None:
        try:
            table = await fetch_dfat_table(client)
        except Exception:
            # Don't fail immediately if the DFAT index/table fetch fails; try direct country pages below.
            table = {}

    entry = None
    # Try normalized direct matches first
    for name in profile["dfat_names"]:
        key = _normalize_name_for_lookup(name)
        entry = table.get(key)
        if entry:
            break

    # Fallback: loose matches (substring / token) against normalized table keys
    if not entry:
        norm_candidates = [_normalize_name_for_lookup(n) for n in profile["dfat_names"]]
        for k, v in table.items():
            for cand in norm_candidates:
                if cand == k or cand in k or k in cand:
                    entry = v
                    break
            if entry:
                break

    if not entry:
        # Token-based fallback: match any significant token
        tokens = []
        for cand in [_normalize_name_for_lookup(n) for n in profile["dfat_names"]]:
            tokens.extend([t for t in cand.split() if len(t) > 3])
        for token in tokens:
            for k, v in table.items():
                if token in k:
                    entry = v
                    break
            if entry:
                break

    if not entry:
        # Try direct country pages on smartraveller (several slug/region candidates)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }

        def _slugify(name: str) -> str:
            return _normalize_name_for_lookup(name).replace(" ", "-")

        slug_candidates = set()
        # basic slugs from dfat_names (dedupe duplicates)
        seen_parts = []
        for name in profile.get("dfat_names", []):
            s = _slugify(name)
            slug_candidates.add(s)
            slug_candidates.add(s.replace("-d-", "-"))
            if s and s not in seen_parts:
                seen_parts.append(s)

        # combined slug from unique parts (e.g., 'cote-divoire-ivory-coast')
        if len(seen_parts) > 1:
            combined = "-".join(seen_parts)
            slug_candidates.add(combined)
            slug_candidates.add(combined.replace("-d-", "-"))

        # canonical slug
        canonical_slug = _slugify(profile.get("canonical", ""))
        if canonical_slug:
            slug_candidates.add(canonical_slug)

        # also add pairwise combinations with canonical to catch patterns like
        # 'cote-divoire-ivory-coast'
        for s in list(slug_candidates):
            if s and canonical_slug:
                slug_candidates.add(f"{s}-{canonical_slug}")
                slug_candidates.add(f"{canonical_slug}-{s}")

        region_candidates = ["africa", "asia", "europe", "americas", "oceania", "asia-pacific"]

        page_text = None
        page_url = None
        for slug in slug_candidates:
            if not slug:
                continue
            for region in (["africa"] + region_candidates + [None]):
                if region:
                    url = f"https://www.smartraveller.gov.au/destinations/{region}/{slug}"
                else:
                    url = f"https://www.smartraveller.gov.au/destinations/{slug}"
                try:
                    resp = await client.get(url, timeout=20, follow_redirects=True, headers=headers)
                    if resp.status_code != 200:
                        continue
                    page_text = _html_to_text(resp.text)
                    page_url = url
                    break
                except Exception:
                    continue
            if page_text:
                break

        if page_text:
            # Look for DFAT level phrases in the page text
            txt = (page_text or "").lower()
            dfat_map = {
                "do not travel": 4,
                "reconsider your need to travel": 3,
                "exercise a high degree of caution": 2,
                "exercise normal safety precautions": 1,
            }
            level = 0
            level_text = None
            for phrase, lvl in dfat_map.items():
                if phrase in txt:
                    level = lvl
                    level_text = phrase.title()
                    break

            # If not found, try to extract a headed level like 'Level X' or similar
            if level == 0:
                m = re.search(r"level\s*([1-4])", txt, re.IGNORECASE)
                if m:
                    level = int(m.group(1))
                    level_text = level_map.get(level) if (level := level) else None

            if level == 0:
                return {"error": f"No DFAT advisory found for '{country}'"}

            return {
                "level": level,
                "level_text": level_text or "See advisory page",
                "advisory": (page_text.split('\n')[0] if page_text else ""),
                "updated_at": None,
                "primary_driver": _extract_primary_driver(page_text),
                "url": page_url,
            }

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
