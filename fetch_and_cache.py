#!/usr/bin/env python3
"""
Daily cron job to fetch and cache aviation and conflict data for MCP server.
Calls underlying API helpers directly so MCP tools can respond instantly.
"""
import asyncio
import json
import logging
import math
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from airports import AFRICAN_AIRPORTS, MAJOR_AFRICAN_AIRPORTS
from countries import ACLED_NAMES
from server import (
    _fetch_opensky_airport,
    _fetch_aerodatabox_airport,
    _fetch_aviationstack_airport,
    _summarise_flights,
    _fetch_country,
    _check_trigger_1,
    _check_trigger_2,
    _check_trigger_3,
    _check_trigger_4,
    _check_trigger_5,
    get_token,
    OPENSKY_USERNAME,
    AERODATA_API_KEY,
    AVIATIONSTACK_API_KEY,
    CAPITALS,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

CACHE_DIR = Path("/data/cache") if os.path.exists("/data") else Path("cache")
CACHE_DIR.mkdir(exist_ok=True)


def _today() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


def _write_cache(prefix: str, data: dict) -> None:
    path = CACHE_DIR / f"{prefix}_{_today()}.json"
    with open(path, "w") as f:
        json.dump({"timestamp": datetime.utcnow().isoformat(), "data": data}, f)
    logging.info("Wrote %s", path)


# ---------------------------------------------------------------------------
# Aviation: traffic reductions
# ---------------------------------------------------------------------------

async def _build_reduction_report(
    airports: list[dict],
    fetch_fn,
    client: httpx.AsyncClient,
    begin_ts: int,
    end_ts: int,
    concurrency: int = 5,
) -> dict:
    sem = asyncio.Semaphore(concurrency)
    completed = [0]

    async def _fetch(airport: dict) -> tuple[dict, dict]:
        async with sem:
            result = await fetch_fn(client, airport["icao"], begin_ts, end_ts)
        completed[0] += 1
        logging.info("Fetched %s (%d/%d)", airport["icao"], completed[0], len(airports))
        return airport, result

    pairs = await asyncio.gather(*[_fetch(a) for a in airports])

    country_report: dict = {}
    airports_flagged = 0

    for airport_data, result in pairs:
        if result.get("error"):
            continue
        all_flights = result["departures"] + result["arrivals"]
        if not all_flights:
            continue
        summary = _summarise_flights(result["departures"], result["arrivals"], begin_ts, end_ts)
        if summary["reduction_pct"] is None or summary["reduction_pct"] < 25.0:
            continue
        airports_flagged += 1
        country = airport_data["country"]
        country_report.setdefault(country, {"airports": [], "total_flights": 0})
        country_report[country]["airports"].append({
            "icao": airport_data["icao"],
            "name": airport_data["name"],
            "city": airport_data["city"],
            **summary,
        })
        country_report[country]["total_flights"] += summary["total_flights"]

    return {
        "report_date": _today(),
        "period": "past 3 days",
        "reduction_threshold_pct": 25.0,
        "airports_checked": len(airports),
        "airports_flagged": airports_flagged,
        "countries_with_reductions": len(country_report),
        "results": country_report,
    }


async def cache_traffic_reductions() -> None:
    logging.info("Caching traffic reductions...")
    now_utc = datetime.now(timezone.utc)
    end_ts = int(now_utc.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
    begin_ts = end_ts - (3 * 86400)
    reports: dict = {}

    if OPENSKY_USERNAME:
        try:
            async with httpx.AsyncClient(timeout=180) as client:
                report = await _build_reduction_report(
                    MAJOR_AFRICAN_AIRPORTS,
                    _fetch_opensky_airport,
                    client, begin_ts, end_ts,
                    concurrency=10,
                )
            reports["opensky"] = report
            logging.info("OpenSky reduction report: %d airports flagged", report["airports_flagged"])
        except Exception as e:
            logging.error("OpenSky reduction cache failed: %s", e)

    if AERODATA_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=300) as client:
                report = await _build_reduction_report(
                    MAJOR_AFRICAN_AIRPORTS,
                    _fetch_aerodatabox_airport,
                    client, begin_ts, end_ts,
                    concurrency=3,
                )
            reports["aerodatabox"] = report
            logging.info("AeroDataBox reduction report: %d airports flagged", report["airports_flagged"])
        except Exception as e:
            logging.error("AeroDataBox reduction cache failed: %s", e)

    if AVIATIONSTACK_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=300) as client:
                report = await _build_reduction_report(
                    MAJOR_AFRICAN_AIRPORTS,
                    _fetch_aviationstack_airport,
                    client, begin_ts, end_ts,
                    concurrency=2,
                )
            reports["aviationstack"] = report
            logging.info("AviationStack reduction report: %d airports flagged", report["airports_flagged"])
        except Exception as e:
            logging.error("AviationStack reduction cache failed: %s", e)

    _write_cache("traffic_reductions", reports)


# ---------------------------------------------------------------------------
# Aviation: disruptions (cancelled / delayed)
# ---------------------------------------------------------------------------

async def cache_aviation_disruptions() -> None:
    logging.info("Caching aviation disruptions...")
    now_utc = datetime.now(timezone.utc)
    end_ts = int(now_utc.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
    begin_ts = end_ts - (3 * 86400)

    if not AVIATIONSTACK_API_KEY and not AERODATA_API_KEY:
        logging.warning("No aviation API keys configured — skipping disruption cache")
        return

    # AviationStack has disruption status fields; prefer it for this cache
    fetch_fn = _fetch_aviationstack_airport if AVIATIONSTACK_API_KEY else _fetch_aerodatabox_airport
    concurrency = 2 if AVIATIONSTACK_API_KEY else 3

    sem = asyncio.Semaphore(concurrency)
    completed = [0]
    airports = MAJOR_AFRICAN_AIRPORTS

    async def _fetch(airport: dict) -> tuple[dict, dict]:
        async with sem:
            async with httpx.AsyncClient(timeout=120) as client:
                result = await fetch_fn(client, airport["icao"], begin_ts, end_ts)
        completed[0] += 1
        logging.info("Disruptions %s (%d/%d)", airport["icao"], completed[0], len(airports))
        return airport, result

    pairs = await asyncio.gather(*[_fetch(a) for a in airports])

    country_report: dict = {}
    airports_flagged = 0

    for airport_data, result in pairs:
        if result.get("error"):
            continue
        all_flights = result["departures"] + result["arrivals"]
        if not all_flights:
            continue
        total = len(all_flights)
        cancelled = sum(1 for f in all_flights if "cancel" in (f.get("status") or "").lower())
        delayed = sum(1 for f in all_flights if "delay" in (f.get("status") or "").lower())
        disrupted = cancelled + delayed
        if total == 0 or disrupted / total * 100 < 25.0:
            continue
        airports_flagged += 1
        country = airport_data["country"]
        country_report.setdefault(country, {"airports": [], "total_disruptions": 0})
        country_report[country]["airports"].append({
            "icao": airport_data["icao"],
            "name": airport_data["name"],
            "city": airport_data["city"],
            "total_flights": total,
            "cancelled_flights": cancelled,
            "delayed_flights": delayed,
            "total_disruptions": disrupted,
            "disruption_pct": round(disrupted / total * 100, 1),
        })
        country_report[country]["total_disruptions"] += disrupted

    data = {
        "report_date": _today(),
        "period": "past 3 days",
        "disruption_threshold_pct": 25.0,
        "airports_checked": len(airports),
        "airports_flagged": airports_flagged,
        "countries_with_disruptions": len(country_report),
        "results": country_report,
    }

    _write_cache("aviation_disruptions", data)


# ---------------------------------------------------------------------------
# ACLED: conflict triggers across 54 African countries
# ---------------------------------------------------------------------------

async def cache_acled_conflicts() -> None:
    logging.info("Caching ACLED conflicts...")
    today = date.today()
    date_from = (today - timedelta(days=30)).isoformat()
    date_to = today.isoformat()

    try:
        token = await get_token()
    except Exception as e:
        logging.error("ACLED auth failed: %s", e)
        return

    async with httpx.AsyncClient(timeout=180) as client:
        tasks = [_fetch_country(client, token, country, date_from, date_to) for country in ACLED_NAMES]
        results = await asyncio.gather(*tasks)

    country_events: dict = dict(zip(ACLED_NAMES, results))
    report: dict = {}

    for country, events in country_events.items():
        if not events:
            continue
        alerts: dict = {}
        t1 = _check_trigger_1(events)
        if t1:
            alerts["trigger_1_escalation"] = t1
        t3 = _check_trigger_3(events)
        if t3:
            alerts["trigger_3_kidnappings"] = t3
        capital = CAPITALS.get(country, "")
        t4 = _check_trigger_4(events, capital)
        if t4:
            alerts["trigger_4_protests"] = t4
        t5 = _check_trigger_5(events)
        if t5:
            alerts["trigger_5_diplomatic"] = t5
        if alerts:
            report[country] = {
                "total_events_30d": len(events),
                "alerts": alerts,
            }

    data = {
        "report_date": date_to,
        "period": f"{date_from} to {date_to}",
        "countries_with_alerts": len(report),
        "facility_coords_used": None,
        "results": report,
    }

    _write_cache("acled_conflicts", data)
    logging.info("ACLED: %d countries with alerts", len(report))


# ---------------------------------------------------------------------------

async def main() -> None:
    logging.info("Starting daily cache refresh")
    await cache_acled_conflicts()
    await cache_traffic_reductions()
    await cache_aviation_disruptions()
    logging.info("Cache refresh complete")


if __name__ == "__main__":
    asyncio.run(main())
