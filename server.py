import asyncio
import logging
import math
import os
import time
from datetime import date, timedelta

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Timeout configuration
# ---------------------------------------------------------------------------
# Timeouts are intentionally generous to accommodate:
#   - Concurrent requests to 54+ African airports via OpenSky (up to 300 s)
#   - ACLED API responses that vary with data volume (up to 180 s)
#   - Unpredictable network latency on external API calls
# get_token:             60 s  — single auth POST, elevated from 30 s
# fetch_acled_events:   180 s  — single-country ACLED query
# run_africa_report:    180 s  — 54-country concurrent ACLED gather
# fetch_airport_activity: 300 s — single-airport OpenSky query
# run_opensky_report:   300 s  — all-airport concurrent OpenSky gather
# ---------------------------------------------------------------------------

from countries import ACLED_NAMES, resolve_country
from airports import AFRICAN_AIRPORTS, AIRPORTS_BY_COUNTRY, get_airport

logging.basicConfig(level=logging.INFO)
load_dotenv()

ACLED_API_URL = "https://acleddata.com/api/acled/read"
ACLED_TOKEN_URL = "https://acleddata.com/oauth/token"
ACLED_USERNAME = os.getenv("ACLED_USERNAME", "")
ACLED_PASSWORD = os.getenv("ACLED_PASSWORD", "")

OPENSKY_API_URL = "https://opensky-network.org/api"
OPENSKY_USERNAME = os.getenv("OPENSKY_USERNAME", "")
OPENSKY_PASSWORD = os.getenv("OPENSKY_PASSWORD", "")

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
    async with httpx.AsyncClient(timeout=180) as client:
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

    async with httpx.AsyncClient(timeout=180) as client:
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


# ---------------------------------------------------------------------------
# OpenSky helpers
# ---------------------------------------------------------------------------

async def _fetch_opensky_airport(
    client: httpx.AsyncClient,
    icao: str,
    begin: int,
    end: int,
) -> dict:
    """Fetch departures and arrivals for one airport from OpenSky."""
    auth = (OPENSKY_USERNAME, OPENSKY_PASSWORD)
    results: dict = {"icao": icao, "departures": [], "arrivals": [], "error": None}

    try:
        dep = await client.get(
            f"{OPENSKY_API_URL}/flights/departure",
            params={"airport": icao, "begin": begin, "end": end},
            auth=auth,
        )
        arr = await client.get(
            f"{OPENSKY_API_URL}/flights/arrival",
            params={"airport": icao, "begin": begin, "end": end},
            auth=auth,
        )
        results["departures"] = dep.json() if dep.status_code == 200 else []
        results["arrivals"] = arr.json() if arr.status_code == 200 else []
        if dep.status_code not in (200, 404):
            logging.warning("OpenSky %s departure: %s", icao, dep.status_code)
        if arr.status_code not in (200, 404):
            logging.warning("OpenSky %s arrival: %s", icao, arr.status_code)
    except Exception as e:
        results["error"] = str(e)
        logging.error("OpenSky fetch error for %s: %s", icao, e)

    return results


def _summarise_flights(departures: list, arrivals: list, begin_ts: int | None = None, end_ts: int | None = None) -> dict:
    """Build a summary with totals, daily time series, and trend vs first half of window."""
    from collections import defaultdict
    from datetime import datetime

    all_flights = departures + arrivals
    daily: dict[str, int] = defaultdict(int)

    for flight in all_flights:
        ts = flight.get("firstSeen") or flight.get("lastSeen")
        if not ts:
            continue
        d = datetime.utcfromtimestamp(ts)
        key = d.strftime("%Y-%m-%d")
        daily[key] += 1

    # Calculate reduction % if window boundaries provided
    reduction_pct: float | None = None
    if begin_ts is not None and end_ts is not None:
        mid_ts = (begin_ts + end_ts) / 2
        first_half = [f for f in all_flights if (f.get("firstSeen") or f.get("lastSeen") or 0) < mid_ts]
        second_half = [f for f in all_flights if (f.get("firstSeen") or f.get("lastSeen") or 0) >= mid_ts]
        if len(first_half) > 0:
            reduction_pct = round((len(first_half) - len(second_half)) / len(first_half) * 100, 1)

    return {
        "total_flights": len(all_flights),
        "total_departures": len(departures),
        "total_arrivals": len(arrivals),
        "daily_series": dict(sorted(daily.items())),
        "reduction_pct": reduction_pct,
    }


# ---------------------------------------------------------------------------
# OpenSky MCP tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def fetch_airport_activity(
    airport_icao: str,
    days_back: int = 7,
) -> dict:
    """Fetch departures and arrivals for a specific African airport over the past N days.

    Args:
        airport_icao: ICAO airport code (e.g. "HKJK" for Nairobi, "FAOR" for Johannesburg).
        days_back: Number of days to look back, max 7 (default 7).
    """
    days_back = min(max(days_back, 1), 7)
    icao = airport_icao.upper().strip()
    airport = get_airport(icao)
    if airport is None:
        return {"error": f"Airport '{icao}' not found in African airport database."}

    end_ts = int(time.time())
    begin_ts = end_ts - (days_back * 86400)

    async with httpx.AsyncClient(timeout=300) as client:
        result = await _fetch_opensky_airport(client, icao, begin_ts, end_ts)

    summary = _summarise_flights(result["departures"], result["arrivals"], begin_ts, end_ts)
    return {
        "airport": airport,
        "period_days": days_back,
        **summary,
        "error": result["error"],
    }


@mcp.tool()
async def run_opensky_report(reduction_threshold_pct: float = 25.0) -> dict:
    """Run OpenSky Data across all major African airports over the past 3 days.

    Returns airports that have experienced a reduction in air traffic of at least
    reduction_threshold_pct% (default 4%), comparing the first half of the window
    to the second half.

    Args:
        reduction_threshold_pct: Minimum % reduction in flights to include an airport (default 25.0).
    """
    end_ts = int(time.time())
    begin_ts = end_ts - (3 * 86400)

    async with httpx.AsyncClient(timeout=300) as client:
        tasks = [
            _fetch_opensky_airport(client, airport["icao"], begin_ts, end_ts)
            for airport in AFRICAN_AIRPORTS
        ]
        results = await asyncio.gather(*tasks)

    # Group by country, only including airports with >= threshold reduction
    country_report: dict[str, dict] = {}
    airports_checked = 0
    airports_flagged = 0

    for airport_data, result in zip(AFRICAN_AIRPORTS, results):
        airports_checked += 1

        # Primary filter: skip airports with no flight data before any further processing
        all_flights = result["departures"] + result["arrivals"]
        if not all_flights:
            continue

        summary = _summarise_flights(result["departures"], result["arrivals"], begin_ts, end_ts)

        # Primary filter: must meet reduction threshold
        if summary["reduction_pct"] is None or summary["reduction_pct"] < reduction_threshold_pct:
            continue

        airports_flagged += 1
        country = airport_data["country"]
        if country not in country_report:
            country_report[country] = {"airports": [], "total_flights": 0}

        country_report[country]["airports"].append({
            "icao": airport_data["icao"],
            "name": airport_data["name"],
            "city": airport_data["city"],
            **summary,
        })
        country_report[country]["total_flights"] += summary["total_flights"]

    from datetime import datetime
    return {
        "report_date": datetime.utcnow().strftime("%Y-%m-%d"),
        "period": "past 3 days",
        "reduction_threshold_pct": reduction_threshold_pct,
        "airports_checked": airports_checked,
        "airports_flagged": airports_flagged,
        "countries_with_reductions": len(country_report),
        "results": country_report,
    }


# ---------------------------------------------------------------------------
# Diagnostic tool
# ---------------------------------------------------------------------------

@mcp.tool()
async def test_connectivity() -> dict:
    """Test outbound connectivity to ACLED and OpenSky APIs.

    Returns status codes, errors, and credential presence for debugging.
    """
    results: dict[str, object] = {
        "acled_username_set": bool(ACLED_USERNAME),
        "acled_password_set": bool(ACLED_PASSWORD),
        "opensky_username_set": bool(OPENSKY_USERNAME),
        "opensky_password_set": bool(OPENSKY_PASSWORD),
    }

    # Test ACLED token endpoint
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
            results["acled_token_body"] = resp.text[:500]
    except Exception as exc:
        results["acled_token_error"] = str(exc)

    # Test OpenSky endpoint (simple departures query)
    try:
        now = int(time.time())
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{OPENSKY_API_URL}/flights/departure",
                params={"airport": "HKJK", "begin": now - 7200, "end": now},
                auth=(OPENSKY_USERNAME, OPENSKY_PASSWORD) if OPENSKY_USERNAME else None,
            )
            results["opensky_status"] = resp.status_code
            results["opensky_body"] = resp.text[:500]
    except Exception as exc:
        results["opensky_error"] = str(exc)

    # Test basic DNS / outbound connectivity
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get("https://httpbin.org/ip")
            results["outbound_ip"] = resp.json().get("origin", "unknown")
    except Exception as exc:
        results["outbound_error"] = str(exc)

    return results


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
