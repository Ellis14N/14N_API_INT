#!/usr/bin/env python3
"""
Daily cron job: fetch data and write cache files.
MCP tools read from these files and return instantly, staying under the 60s timeout.

Cache files written (CACHE_DIR, named by UTC date):
  acled_conflicts_YYYY-MM-DD.json — ACLED trigger report for all 54 African countries

Note: travel advisories are fetched live on demand by run_travel_advisories_report().
"""
import asyncio
import json
import logging
import math
import os
import sys
import time
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from countries import ACLED_NAMES
import travel_advisories

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

CACHE_DIR = Path("/data/cache") if os.path.exists("/data") else Path("cache")
CACHE_DIR.mkdir(exist_ok=True)

ACLED_API_URL = "https://acleddata.com/api/acled/read"
ACLED_TOKEN_URL = "https://acleddata.com/oauth/token"
ACLED_USERNAME = os.getenv("ACLED_USERNAME", "")
ACLED_PASSWORD = os.getenv("ACLED_PASSWORD", "")

DIPLOMATIC_KEYWORDS = [
    "embassy", "embassies", "consulate", "consular", "diplomatic",
    "ambassador", "high commission", "chancellery",
]

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


def _today() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


def _write_cache(prefix: str, data: dict) -> None:
    path = CACHE_DIR / f"{prefix}_{_today()}.json"
    with open(path, "w") as f:
        json.dump({"timestamp": datetime.utcnow().isoformat(), "data": data}, f)
    logging.info("Wrote %s", path)


# ---------------------------------------------------------------------------
# ACLED helpers
# ---------------------------------------------------------------------------

async def _get_acled_token() -> str:
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
        return resp.json()["access_token"]


async def _fetch_country(client: httpx.AsyncClient, token: str, country: str, date_from: str, date_to: str) -> list[dict]:
    params: dict = {
        "country": country,
        "event_date": f"{date_from}|{date_to}",
        "event_date_where": "BETWEEN",
        "limit": 5000,
    }
    resp = await client.get(ACLED_API_URL, params=params, headers={"Authorization": f"Bearer {token}"})
    if resp.status_code != 200:
        logging.error("ACLED error for %s: %s", country, resp.status_code)
        return []
    return resp.json().get("data", [])


def _haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _check_trigger_1(events):
    weekly: dict[str, int] = defaultdict(int)
    for e in events:
        try:
            d = date.fromisoformat(e["event_date"])
            weekly[d.strftime("%Y-W%W")] += 1
        except Exception:
            continue
    weeks = sorted(weekly.keys())
    for i in range(len(weeks) - 1):
        prev, curr = weekly[weeks[i]], weekly[weeks[i + 1]]
        if prev > 0 and (curr - prev) / prev >= 0.20:
            return {"weeks": [weeks[i], weeks[i + 1]], "counts": [prev, curr], "increase_pct": round((curr - prev) / prev * 100, 1)}
    return None


def _check_trigger_3(events):
    keywords = ["foreign national", "foreigner", "expatriate", "expat", "kidnap", "abduct"]
    hits = []
    for e in events:
        sub = (e.get("sub_event_type") or "").lower()
        notes = (e.get("notes") or "").lower()
        if "abduction" not in sub and "kidnap" not in sub:
            continue
        if any(k in notes for k in keywords):
            hits.append({"date": e.get("event_date"), "location": e.get("location"), "actor1": e.get("actor1"), "notes": e.get("notes", "")[:300]})
    return hits


def _check_trigger_4(events, capital):
    protest_events = [e for e in events if (e.get("event_type") or "").lower() in ("protests", "riots")]
    capital_dates = sorted({e["event_date"] for e in protest_events if capital.lower() in (e.get("location") or "").lower()})
    max_streak = streak = 1
    streak_dates: list[str] = []
    current_streak = capital_dates[:1] if capital_dates else []
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
    daily_cities: dict[str, set] = defaultdict(set)
    for e in protest_events:
        daily_cities[e["event_date"]].add(e.get("location", ""))
    multi_city_days = {d: list(c) for d, c in daily_cities.items() if len(c) >= 2}
    if max_streak < 3 and not multi_city_days:
        return None
    result: dict = {}
    if max_streak >= 3:
        result["capital_sustained"] = {"consecutive_days": max_streak, "dates": streak_dates}
    if multi_city_days:
        result["multi_city"] = multi_city_days
    return result


def _check_trigger_5(events):
    hits = []
    for e in events:
        if e.get("event_type") not in {"Protests", "Riots"}:
            continue
        notes = (e.get("notes") or "").lower()
        location = (e.get("location") or "").lower()
        if any(k in notes or k in location for k in DIPLOMATIC_KEYWORDS):
            hits.append({"date": e.get("event_date"), "location": e.get("location"), "notes": e.get("notes", "")[:300]})
    return hits


async def cache_acled_report() -> None:
    if not ACLED_USERNAME or not ACLED_PASSWORD:
        logging.warning("ACLED credentials not set — skipping ACLED cache")
        return

    logging.info("Caching ACLED report for %d countries...", len(ACLED_NAMES))
    try:
        date_to = date.today()
        date_from = date_to - timedelta(days=30)
        token = await _get_acled_token()

        async with httpx.AsyncClient(timeout=300) as client:
            results = await asyncio.gather(*[
                _fetch_country(client, token, country, date_from.isoformat(), date_to.isoformat())
                for country in ACLED_NAMES
            ])

        report: dict = {}
        for country, events in zip(ACLED_NAMES, results):
            if not events:
                continue
            alerts: dict = {}
            t1 = _check_trigger_1(events)
            if t1:
                alerts["trigger_1_escalation"] = t1
            t3 = _check_trigger_3(events)
            if t3:
                alerts["trigger_3_kidnappings"] = t3
            t4 = _check_trigger_4(events, CAPITALS.get(country, ""))
            if t4:
                alerts["trigger_4_protests"] = t4
            t5 = _check_trigger_5(events)
            if t5:
                alerts["trigger_5_diplomatic"] = t5
            if alerts:
                report[country] = {"total_events_30d": len(events), "alerts": alerts}

        _write_cache("acled_conflicts", {
            "report_date": date_to.isoformat(),
            "period": f"{date_from.isoformat()} to {date_to.isoformat()}",
            "countries_with_alerts": len(report),
            "results": report,
        })
        logging.info("ACLED cache written: %d countries with alerts", len(report))
    except Exception as e:
        logging.error("ACLED cache failed: %s", e)


async def cache_travel_advisories() -> None:
    logging.info("Caching travel advisories (DFAT / State Dept / FCDO / MEAE)")
    # Get list of destinations from DFAT export when available
    async with httpx.AsyncClient(follow_redirects=True) as client:
        try:
            dfat_map = await travel_advisories.fetch_dfat_table(client)
            if dfat_map:
                countries = [v.get("name") or k for k, v in dfat_map.items()]
            else:
                countries = ACLED_NAMES
        except Exception as e:
            logging.error("Failed to fetch DFAT export: %s", e)
            countries = ACLED_NAMES

    logging.info("Fetching advisories for %d countries...", len(countries))
    try:
        advisories = await travel_advisories.fetch_advisories_for_countries(countries)
    except Exception as e:
        logging.error("Failed to fetch travel advisories: %s", e)
        advisories = {}

    _write_cache("travel_advisories", advisories)
    # Also write a 'latest' copy for quick access
    latest_path = CACHE_DIR / "travel_advisories_latest.json"
    try:
        with open(latest_path, "w") as f:
            json.dump({"timestamp": datetime.utcnow().isoformat(), "data": advisories}, f)
        logging.info("Wrote latest travel advisories cache: %s", latest_path)
    except Exception as e:
        logging.error("Failed to write latest travel advisories cache: %s", e)


async def main() -> None:
    logging.info("Starting daily cache refresh")
    await cache_acled_report()
    # Cache travel advisories for all DFAT-exported destinations (or ACLED_NAMES fallback)
    try:
        await cache_travel_advisories()
    except Exception as e:
        logging.error("Travel advisories cache failed: %s", e)
    logging.info("Cache refresh complete")


if __name__ == "__main__":
    asyncio.run(main())
