import asyncio
import logging
import math
import os
import time
from datetime import date, timedelta

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from countries import ACLED_NAMES, resolve_country

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
    async with httpx.AsyncClient(timeout=30) as client:
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

    # Consecutive days in capital
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

    # Multi-city same day
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
# MCP tools
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

    logging.info("Calling ACLED API: %s %s", ACLED_API_URL, params)
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(
            ACLED_API_URL,
            params=params,
            headers={"Authorization": f"Bearer {token}"},
        )
        logging.info("ACLED response status: %s", resp.status_code)
        if resp.status_code != 200:
            logging.error("ACLED error body: %s", resp.text)
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
async def run_africa_report(
    facility_lat: float | None = None,
    facility_lon: float | None = None,
) -> dict:
    """Run the ACLED Daily Africa Report across all 54 African countries.

    Checks 5 security triggers over the past 30 days and returns a
    structured country-by-country report of all triggered alerts.

    Args:
        facility_lat: Optional latitude of an operating facility for
                      Trigger 2 (armed group proximity) checks.
        facility_lon: Optional longitude of an operating facility for
                      Trigger 2 (armed group proximity) checks.
    """
    date_to = date.today()
    date_from = date_to - timedelta(days=30)
    date_from_str = date_from.isoformat()
    date_to_str = date_to.isoformat()

    facility_coords: tuple[float, float] | None = None
    if facility_lat is not None and facility_lon is not None:
        facility_coords = (facility_lat, facility_lon)

    token = await get_token()

    async with httpx.AsyncClient(timeout=60) as client:
        tasks = [
            _fetch_country(client, token, country, date_from_str, date_to_str)
            for country in ACLED_NAMES
        ]
        results = await asyncio.gather(*tasks)

    country_events: dict[str, list[dict]] = dict(zip(ACLED_NAMES, results))

    report: dict[str, dict] = {}

    for country, events in country_events.items():
        if not events:
            continue

        alerts: dict = {}

        # Trigger 1 — week-on-week escalation
        t1 = _check_trigger_1(events)
        if t1:
            alerts["trigger_1_escalation"] = t1

        # Trigger 2 — armed group proximity (only if coordinates provided)
        if facility_coords:
            t2 = _check_trigger_2(events, facility_coords[0], facility_coords[1])
            if t2:
                alerts["trigger_2_armed_proximity"] = t2

        # Trigger 3 — foreign national kidnappings
        t3 = _check_trigger_3(events)
        if t3:
            alerts["trigger_3_kidnappings"] = t3

        # Trigger 4 — sustained/multi-city protests
        capital = CAPITALS.get(country, "")
        t4 = _check_trigger_4(events, capital)
        if t4:
            alerts["trigger_4_protests"] = t4

        # Trigger 5 — demonstrations near diplomatic/facility premises
        t5 = _check_trigger_5(events, facility_coords)
        if t5:
            alerts["trigger_5_diplomatic"] = t5

        if alerts:
            report[country] = {
                "total_events_30d": len(events),
                "alerts": alerts,
            }

    return {
        "report_date": date_to_str,
        "period": f"{date_from_str} to {date_to_str}",
        "countries_with_alerts": len(report),
        "facility_coords_used": facility_coords,
        "results": report,
    }


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
