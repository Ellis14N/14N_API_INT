import asyncio
import json
import logging
import math
import os
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import Context, FastMCP

from countries import ACLED_NAMES, resolve_country, AFRICAN_CANONICAL_NAMES
from travel_advisories import fetch_all_advisories

logging.basicConfig(level=logging.INFO)
load_dotenv()

ACLED_API_URL = "https://acleddata.com/api/acled/read"
ACLED_TOKEN_URL = "https://acleddata.com/oauth/token"
ACLED_USERNAME = os.getenv("ACLED_USERNAME", "")
ACLED_PASSWORD = os.getenv("ACLED_PASSWORD", "")

DIPLOMATIC_KEYWORDS = [
    "embassy", "embassies", "consulate", "consular", "diplomatic",
    "ambassador", "high commission", "chancellery",
]

mcp = FastMCP(
    "14N API Integration",
    host="0.0.0.0",
    port=int(os.getenv("PORT", "8000")),
)

_token: str = ""
_token_expiry: float = 0.0


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

async def get_token() -> str:
    global _token, _token_expiry
    if _token and time.time() < _token_expiry:
        return _token
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            ACLED_TOKEN_URL,
            data={
                "username": ACLED_USERNAME,
                "password": ACLED_PASSWORD,
                "grant_type": "password",
                "client_id": "acled",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        _token = data["access_token"]
        _token_expiry = time.time() + 23 * 3600
    return _token


# ---------------------------------------------------------------------------
# Core fetch
# ---------------------------------------------------------------------------

async def _fetch_country(client: httpx.AsyncClient, token: str, country: str, date_from: str, date_to: str) -> list[dict]:
    params: dict[str, str | int] = {
        "country": country,
        "event_date": f"{date_from}|{date_to}",
        "event_date_where": "BETWEEN",
        "limit": 5000,
    }
    logging.info("Fetching %s", country)
    resp = await client.get(
        ACLED_API_URL,
        params=params,
        headers={"Authorization": f"Bearer {token}"},
    )
    if resp.status_code != 200:
        logging.error("ACLED error for %s: %s %s", country, resp.status_code, resp.text)
        return []
    data = resp.json()
    return data.get("data", [])


# ---------------------------------------------------------------------------
# Geo helper
# ---------------------------------------------------------------------------

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ---------------------------------------------------------------------------
# Trigger checks
# ---------------------------------------------------------------------------

def _check_trigger_1(events: list[dict]) -> dict | None:
    """≥20% week-on-week increase sustained over 14 days (2 consecutive weeks)."""
    from collections import defaultdict
    weekly: dict[str, int] = defaultdict(int)
    for e in events:
        try:
            d = date.fromisoformat(e["event_date"])
            week = d.strftime("%Y-W%W")
            weekly[week] += 1
        except Exception:
            continue
    weeks = sorted(weekly.keys())
    if len(weeks) < 2:
        return None
    for i in range(len(weeks) - 1):
        prev, curr = weekly[weeks[i]], weekly[weeks[i + 1]]
        if prev > 0 and (curr - prev) / prev >= 0.20:
            return {
                "weeks": [weeks[i], weeks[i + 1]],
                "counts": [prev, curr],
                "increase_pct": round((curr - prev) / prev * 100, 1),
            }
    return None


def _check_trigger_2(events: list[dict], lat: float, lon: float, radius_km: float = 100) -> list[dict]:
    """Armed group events within radius_km of provided coordinates."""
    armed_types = {"Battles", "Explosions/Remote violence", "Violence against civilians"}
    hits = []
    for e in events:
        if e.get("event_type") not in armed_types:
            continue
        try:
            elat = float(e["latitude"])
            elon = float(e["longitude"])
        except (KeyError, ValueError, TypeError):
            continue
        dist = _haversine_km(lat, lon, elat, elon)
        if dist <= radius_km:
            hits.append({
                "date": e.get("event_date"),
                "event_type": e.get("event_type"),
                "sub_event_type": e.get("sub_event_type"),
                "actor1": e.get("actor1"),
                "location": e.get("location"),
                "distance_km": round(dist, 1),
                "notes": e.get("notes", "")[:200],
            })
    return hits


def _check_trigger_3(events: list[dict]) -> list[dict]:
    """High-profile kidnapping of foreign nationals."""
    keywords = ["foreign national", "foreigner", "expatriate", "expat", "kidnap", "abduct"]
    hits = []
    for e in events:
        sub = (e.get("sub_event_type") or "").lower()
        notes = (e.get("notes") or "").lower()
        if "abduction" not in sub and "kidnap" not in sub:
            continue
        if any(k in notes for k in keywords):
            hits.append({
                "date": e.get("event_date"),
                "location": e.get("location"),
                "actor1": e.get("actor1"),
                "notes": e.get("notes", "")[:300],
            })
    return hits


def _check_trigger_4(events: list[dict], capital: str) -> dict | None:
    """Sustained protests in capital ≥3 consecutive days, or multi-city protests same day."""
    from collections import defaultdict
    protest_events = [
        e for e in events
        if (e.get("event_type") or "").lower() in ("protests", "riots")
    ]

    capital_dates = sorted({
        e["event_date"] for e in protest_events
        if capital.lower() in (e.get("location") or "").lower()
    })
    max_streak = streak = 1
    streak_dates: list[str] = []
    current_streak: list[str] = capital_dates[:1] if capital_dates else []
    for i in range(1, len(capital_dates)):
        prev = date.fromisoformat(capital_dates[i - 1])
        curr = date.fromisoformat(capital_dates[i])
        if (curr - prev).days == 1:
            streak += 1
            current_streak.append(capital_dates[i])
            if streak > max_streak:
                max_streak = streak
                streak_dates = current_streak[:]
        else:
            streak = 1
            current_streak = [capital_dates[i]]

    capital_hit = max_streak >= 3

    daily_cities: dict[str, set] = defaultdict(set)
    for e in protest_events:
        daily_cities[e["event_date"]].add(e.get("location", ""))
    multi_city_days = {d: list(cities) for d, cities in daily_cities.items() if len(cities) >= 2}

    if not capital_hit and not multi_city_days:
        return None

    result: dict = {}
    if capital_hit:
        result["capital_sustained"] = {"consecutive_days": max_streak, "dates": streak_dates}
    if multi_city_days:
        result["multi_city"] = multi_city_days
    return result


def _check_trigger_5(events: list[dict], facility_coords: tuple[float, float] | None = None, radius_km: float = 5) -> list[dict]:
    """Demonstrations near diplomatic premises (keyword) and optionally near facility coords."""
    protest_types = {"Protests", "Riots"}
    hits = []
    for e in events:
        if e.get("event_type") not in protest_types:
            continue
        notes = (e.get("notes") or "").lower()
        location = (e.get("location") or "").lower()
        keyword_match = any(k in notes or k in location for k in DIPLOMATIC_KEYWORDS)

        coord_match = False
        distance_km = None
        if facility_coords:
            try:
                elat = float(e["latitude"])
                elon = float(e["longitude"])
                distance_km = _haversine_km(facility_coords[0], facility_coords[1], elat, elon)
                coord_match = distance_km <= radius_km
            except (KeyError, ValueError, TypeError):
                pass

        if keyword_match or coord_match:
            hits.append({
                "date": e.get("event_date"),
                "location": e.get("location"),
                "event_type": e.get("event_type"),
                "sub_event_type": e.get("sub_event_type"),
                "keyword_match": keyword_match,
                "distance_km": round(distance_km, 1) if distance_km is not None else None,
                "notes": e.get("notes", "")[:300],
            })
    return hits


# ---------------------------------------------------------------------------
# Capital lookup
# ---------------------------------------------------------------------------

CAPITALS: dict[str, str] = {
    "Algeria": "Algiers", "Angola": "Luanda", "Benin": "Porto-Novo",
    "Botswana": "Gaborone", "Burkina Faso": "Ouagadougou", "Burundi": "Gitega",
    "Cabo Verde": "Praia", "Cameroon": "Yaounde", "Central African Republic": "Bangui",
    "Chad": "N'Djamena", "Comoros": "Moroni", "Democratic Republic of the Congo": "Kinshasa",
    "Djibouti": "Djibouti", "Egypt": "Cairo", "Equatorial Guinea": "Malabo",
    "Eritrea": "Asmara", "Eswatini": "Mbabane", "Ethiopia": "Addis Ababa",
    "Gabon": "Libreville", "Gambia": "Banjul", "Ghana": "Accra", "Guinea": "Conakry",
    "Guinea-Bissau": "Bissau", "Ivory Coast": "Yamoussoukro", "Kenya": "Nairobi",
    "Lesotho": "Maseru", "Liberia": "Monrovia", "Libya": "Tripoli",
    "Madagascar": "Antananarivo", "Malawi": "Lilongwe", "Mali": "Bamako",
    "Mauritania": "Nouakchott", "Mauritius": "Port Louis", "Morocco": "Rabat",
    "Mozambique": "Maputo", "Namibia": "Windhoek", "Niger": "Niamey",
    "Nigeria": "Abuja", "Republic of the Congo": "Brazzaville", "Rwanda": "Kigali",
    "Sao Tome and Principe": "Sao Tome", "Senegal": "Dakar", "Seychelles": "Victoria",
    "Sierra Leone": "Freetown", "Somalia": "Mogadishu", "South Africa": "Pretoria",
    "South Sudan": "Juba", "Sudan": "Khartoum", "Tanzania": "Dodoma",
    "Togo": "Lome", "Tunisia": "Tunis", "Uganda": "Kampala",
    "Zambia": "Lusaka", "Zimbabwe": "Harare",
}


# ---------------------------------------------------------------------------
# ACLED tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def fetch_acled_events(
    country: str,
    date_from: str,
    date_to: str,
    event_type: str | None = None,
    limit: int = 5000,
) -> dict:
    """Fetch conflict events from the ACLED API.

    Args:
        country: Country name (e.g. "Mali", "Somalia").
        date_from: Start date in YYYY-MM-DD format.
        date_to: End date in YYYY-MM-DD format.
        event_type: Optional event type filter (e.g. "Battles", "Protests").
        limit: Maximum number of records to return (default 5000).
    """
    async def _impl():
        token = await get_token()
        canonical = resolve_country(country)
        if canonical is None:
            return {"error": f"Unrecognised country: '{country}'. Check spelling or use an ISO code."}
        params: dict[str, str | int] = {
            "country": canonical,
            "event_date": f"{date_from}|{date_to}",
            "event_date_where": "BETWEEN",
            "limit": limit,
        }
        if event_type:
            params["event_type"] = event_type
        async with httpx.AsyncClient(timeout=180) as client:
            resp = await client.get(
                ACLED_API_URL,
                params=params,
                headers={"Authorization": f"Bearer {token}"},
            )
            resp.raise_for_status()
            return resp.json()

    try:
        return await asyncio.wait_for(_impl(), timeout=180)
    except asyncio.TimeoutError:
        return {"error": "Query timed out after 180 seconds"}


@mcp.tool()
async def run_africa_report(
    facility_lat: float | None = None,
    facility_lon: float | None = None,
    ctx: Context | None = None,
) -> dict:
    """Run the ACLED Daily Africa Report across all 54 African countries.

    Checks 5 security triggers over the past 30 days and returns a
    structured country-by-country report of all triggered alerts.

    Args:
        facility_lat: Optional latitude of an operating facility for Trigger 2 checks.
        facility_lon: Optional longitude of an operating facility for Trigger 2 checks.
    """
    cache_dir = Path("/data/cache") if Path("/data").exists() else Path("cache")
    cache_file = cache_dir / f"acled_conflicts_{datetime.utcnow().strftime('%Y-%m-%d')}.json"

    if facility_lat is None and facility_lon is None:
        if cache_file.exists():
            try:
                with open(cache_file) as f:
                    return json.load(f)["data"]
            except Exception as e:
                logging.warning("ACLED cache read failed: %s", e)
        else:
            return {
                "error": "Data not yet available",
                "message": "ACLED data is refreshed daily at 03:00 UTC. Please try again after the cache has been populated, or run the cron job manually.",
            }

    async def _impl():
        date_to = date.today()
        date_from = date_to - timedelta(days=30)
        date_from_str = date_from.isoformat()
        date_to_str = date_to.isoformat()

        facility_coords: tuple[float, float] | None = None
        if facility_lat is not None and facility_lon is not None:
            facility_coords = (facility_lat, facility_lon)

        if ctx:
            await ctx.report_progress(0, 54, "Authenticating with ACLED...")

        token = await get_token()

        if ctx:
            await ctx.report_progress(1, 54, "Fetching data for 54 countries...")

        async with httpx.AsyncClient(timeout=180) as client:
            results = await asyncio.gather(*[
                _fetch_country(client, token, country, date_from_str, date_to_str)
                for country in ACLED_NAMES
            ])

        if ctx:
            await ctx.report_progress(50, 54, "Analysing triggers...")

        country_events: dict[str, list[dict]] = dict(zip(ACLED_NAMES, results))
        report: dict[str, dict] = {}

        for country, events in country_events.items():
            if not events:
                continue
            alerts: dict = {}

            t1 = _check_trigger_1(events)
            if t1:
                alerts["trigger_1_escalation"] = t1
            if facility_coords:
                t2 = _check_trigger_2(events, facility_coords[0], facility_coords[1])
                if t2:
                    alerts["trigger_2_armed_proximity"] = t2
            t3 = _check_trigger_3(events)
            if t3:
                alerts["trigger_3_kidnappings"] = t3
            t4 = _check_trigger_4(events, CAPITALS.get(country, ""))
            if t4:
                alerts["trigger_4_protests"] = t4
            t5 = _check_trigger_5(events, facility_coords)
            if t5:
                alerts["trigger_5_diplomatic"] = t5

            if alerts:
                report[country] = {
                    "total_events_30d": len(events),
                    "alerts": alerts,
                }

        if ctx:
            await ctx.report_progress(54, 54, "Report complete.")

        return {
            "report_date": date_to_str,
            "period": f"{date_from_str} to {date_to_str}",
            "countries_with_alerts": len(report),
            "facility_coords_used": facility_coords,
            "results": report,
        }

    try:
        return await asyncio.wait_for(_impl(), timeout=180)
    except asyncio.TimeoutError:
        return {"error": "Query timed out after 180 seconds"}


# ---------------------------------------------------------------------------
# Travel advisories
# ---------------------------------------------------------------------------

@mcp.prompt()
def travel_advisories_prompt() -> str:
    """Prompt guiding Claude on how to use and present travel advisory data."""
    return """
You are a security intelligence analyst monitoring travel advisories for African countries on behalf of 14N Strategies.

When asked about travel advisories:

1. Call `run_travel_advisories_report()` first. This compares today's advisories against yesterday's across all 54 African countries from four official government sources:
   - UK FCDO (Foreign, Commonwealth & Development Office)
   - US State Department
   - Australian DFAT (Department of Foreign Affairs and Trade)
   - French MEAE (Ministry of Europe and Foreign Affairs)

    Note: These travel advisories are independent from ACLED conflict-event data; do not conflate or combine the advisory outputs with ACLED event analyses.

2. If new or elevated advisories are found, present them clearly:
   - Lead with the country and the source that issued the advisory
   - State the new level and what it means (e.g. Level 3: Reconsider Travel)
   - Include the primary driver (e.g. Terrorism risk, Civil unrest)
   - Include the advisory text and a link to the source
   - Note the previous level so the reader understands the direction of change

3. If no new advisories have been issued, say so clearly and briefly. Do not pad the response.

4. For a specific country query, call `fetch_travel_advisories(country)` directly to get live data from all four sources simultaneously.

5. Advisory levels across sources (for reference):
   - Level 4 / Formally advised against / Do Not Travel — highest risk, avoid entirely
   - Level 3 / Reconsider Travel / Advised against except essential — significant risk
   - Level 2 / Exercise Increased Caution / Enhanced vigilance — elevated risk
   - Level 1 / Normal Precautions — standard risk

Keep responses concise and intelligence-focused. Flag the most severe changes first.
""".strip()


@mcp.tool()
async def fetch_travel_advisories(country: str) -> dict:
    """Fetch live travel advisories for a specific country from UK FCDO, US State Department, Australian DFAT, and French MEAE.

    Use this when you need the current advisory for a single country on demand.

    Args:
        country: Country name (e.g. "Mali", "Somalia", "Democratic Republic of the Congo").
    """
    try:
        return await asyncio.wait_for(fetch_all_advisories(country), timeout=45)
    except asyncio.TimeoutError:
        return {"error": "Advisory fetch timed out after 45 seconds"}


@mcp.tool()
async def run_travel_advisories_report() -> dict:
    """Run the daily travel advisory report for all 54 African countries.

    Reads today's cached snapshot (populated at 02:00 Morocco time by GitHub Actions)
    and compares against yesterday's to surface any new or elevated advisories.
    """
    GITHUB_RAW = "https://raw.githubusercontent.com/Ellis14N/14N_API_INT/data/cache"
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    yesterday_str = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")

    # Load today's cache from GitHub data branch
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{GITHUB_RAW}/travel_advisories_{today_str}.json")
        if resp.status_code == 404:
            return {
                "error": "Data not yet available",
                "message": f"Travel advisory cache for {today_str} has not been generated yet. It refreshes daily at 02:00 Morocco time. Try again later or trigger the workflow manually in GitHub Actions.",
            }
        resp.raise_for_status()
        today_data: dict = resp.json()["data"]
    except Exception as e:
        return {"error": f"Cache fetch failed: {e}"}

    # Load yesterday's cache for diff
    yesterday_data: dict = {}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{GITHUB_RAW}/travel_advisories_{yesterday_str}.json")
        if resp.status_code == 200:
            yesterday_data = resp.json().get("data", {})
    except Exception as e:
        logging.warning("Could not load yesterday's advisory cache: %s", e)

    sources = ("fcdo", "us_state_dept", "aus_dfat", "french_meae")
    source_labels = {
        "fcdo": "UK FCDO",
        "us_state_dept": "US State Department",
        "aus_dfat": "Australian DFAT",
        "french_meae": "French MEAE",
    }

    new_advisories = []
    for country, today_sources in today_data.items():
        yesterday_sources = yesterday_data.get(country, {})
        for src in sources:
            today_src = today_sources.get(src, {})
            if today_src.get("error") or today_src.get("level") is None:
                continue
            today_level = int(today_src.get("level") or 0)
            yesterday_level = int((yesterday_sources.get(src) or {}).get("level") or 0)
            if today_level > yesterday_level:
                new_advisories.append({
                    "country": country,
                    "source": source_labels[src],
                    "previous_level": yesterday_level,
                    "current_level": today_level,
                    "level_text": today_src.get("level_text"),
                    "advisory": today_src.get("advisory"),
                    "primary_driver": today_src.get("primary_driver"),
                    "updated_at": today_src.get("updated_at"),
                    "url": today_src.get("url"),
                })

    new_advisories.sort(key=lambda x: x["current_level"], reverse=True)

    # Build full current snapshot for all 54 countries
    all_countries_current = {}
    for country, today_sources in today_data.items():
        country_levels = {}
        for src in sources:
            today_src = today_sources.get(src, {})
            if today_src.get("error") or today_src.get("level") is None:
                country_levels[source_labels[src]] = "unavailable"
            else:
                country_levels[source_labels[src]] = {
                    "level": today_src.get("level"),
                    "level_text": today_src.get("level_text"),
                    "primary_driver": today_src.get("primary_driver"),
                    "url": today_src.get("url"),
                }
        all_countries_current[country] = country_levels

    return {
        "report_date": today_str,
        "compared_to": yesterday_str if yesterday_data else "no prior data",
        "new_advisories_count": len(new_advisories),
        "new_advisories": new_advisories,
        "summary": (
            f"{len(new_advisories)} new or elevated advisory/advisories issued since yesterday."
            if new_advisories else "No new travel advisories issued since yesterday."
        ),
        "all_countries_current_levels": all_countries_current,
    }


# ---------------------------------------------------------------------------
# Diagnostic tool
# ---------------------------------------------------------------------------

@mcp.tool()
async def test_connectivity() -> dict:
    """Test outbound connectivity to ACLED API and advisory sources."""
    results: dict[str, object] = {
        "acled_username_set": bool(ACLED_USERNAME),
        "acled_password_set": bool(ACLED_PASSWORD),
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                ACLED_TOKEN_URL,
                data={
                    "username": ACLED_USERNAME,
                    "password": ACLED_PASSWORD,
                    "grant_type": "password",
                    "client_id": "acled",
                },
            )
            results["acled_token_status"] = resp.status_code
    except Exception as exc:
        results["acled_token_error"] = str(exc)

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get("https://httpbin.org/ip")
            results["outbound_ip"] = resp.json().get("origin", "unknown")
    except Exception as exc:
        results["outbound_error"] = str(exc)

    return results


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
