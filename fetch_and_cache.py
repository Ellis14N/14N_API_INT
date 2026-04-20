#!/usr/bin/env python3
"""
Daily cron job: fetch aviation data from all three APIs and write cache files.
MCP tools read from these files and return instantly, staying under the 60s timeout.

Cache files written (CACHE_DIR, named by UTC date):
  traffic_reductions_YYYY-MM-DD.json   — airports where volume dropped >25% (OpenSky, AeroDataBox, AviationStack)
  aviation_disruptions_YYYY-MM-DD.json — airports with cancelled/delayed flights (AeroDataBox, AviationStack only;
                                         OpenSky does not expose flight status fields)
"""
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from airports import AFRICAN_AIRPORTS, MAJOR_AFRICAN_AIRPORTS
from server import (
    _fetch_opensky_airport,
    _fetch_aerodatabox_airport,
    _fetch_aviationstack_airport,
    _summarise_flights,
    OPENSKY_USERNAME,
    AERODATA_API_KEY,
    AVIATIONSTACK_API_KEY,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

CACHE_DIR = Path("/data/cache") if os.path.exists("/data") else Path("cache")
CACHE_DIR.mkdir(exist_ok=True)
TOP_N = 20


def _today() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


def _write_cache(prefix: str, data: dict) -> None:
    path = CACHE_DIR / f"{prefix}_{_today()}.json"
    with open(path, "w") as f:
        json.dump({"timestamp": datetime.utcnow().isoformat(), "data": data}, f)
    logging.info("Wrote %s", path)


def _window_ts() -> tuple[int, int]:
    now_utc = datetime.now(timezone.utc)
    end_ts = int(now_utc.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
    return end_ts - (3 * 86400), end_ts


async def _scan_airports(fetch_fn, airports: list[dict], begin_ts: int, end_ts: int, concurrency: int) -> list[tuple[dict, dict]]:
    sem = asyncio.Semaphore(concurrency)
    completed = [0]

    async def _fetch(airport: dict) -> tuple[dict, dict]:
        async with sem:
            async with httpx.AsyncClient(timeout=180) as client:
                result = await fetch_fn(client, airport["icao"], begin_ts, end_ts)
        completed[0] += 1
        logging.info("%s %s (%d/%d)", fetch_fn.__name__, airport["icao"], completed[0], len(airports))
        return airport, result

    return await asyncio.gather(*[_fetch(a) for a in airports])


# ---------------------------------------------------------------------------
# Traffic reductions (all three providers)
# ---------------------------------------------------------------------------

def _build_reduction_report(pairs: list[tuple[dict, dict]], begin_ts: int, end_ts: int) -> dict:
    above_threshold = []
    all_airports = []

    for airport_data, result in pairs:
        if result.get("error"):
            continue
        summary = _summarise_flights(result["departures"], result["arrivals"], begin_ts, end_ts)
        if not summary["operating"] or summary["reduction_pct"] is None:
            continue
        entry = {
            "icao": airport_data["icao"],
            "name": airport_data["name"],
            "city": airport_data["city"],
            "country": airport_data["country"],
            **summary,
        }
        all_airports.append(entry)
        if summary["reduction_pct"] >= 25.0:
            above_threshold.append(entry)

    above_threshold.sort(key=lambda x: x["reduction_pct"], reverse=True)
    top_by_reduction = sorted(all_airports, key=lambda x: x["reduction_pct"], reverse=True)[:TOP_N]

    return {
        "report_date": _today(),
        "period": "past 3 days",
        "airports_checked": len(pairs),
        "airports_above_threshold": len(above_threshold),
        "above_25pct_reduction": above_threshold,
        "top_by_reduction_pct": top_by_reduction,
    }


async def cache_traffic_reductions() -> None:
    logging.info("Caching traffic reductions...")
    begin_ts, end_ts = _window_ts()
    reports: dict = {}

    if OPENSKY_USERNAME:
        try:
            pairs = await _scan_airports(_fetch_opensky_airport, MAJOR_AFRICAN_AIRPORTS, begin_ts, end_ts, concurrency=10)
            reports["opensky"] = _build_reduction_report(pairs, begin_ts, end_ts)
            logging.info("OpenSky: %d airports above threshold", reports["opensky"]["airports_above_threshold"])
        except Exception as e:
            logging.error("OpenSky reductions failed: %s", e)

    if AERODATA_API_KEY:
        try:
            pairs = await _scan_airports(_fetch_aerodatabox_airport, MAJOR_AFRICAN_AIRPORTS, begin_ts, end_ts, concurrency=3)
            reports["aerodatabox"] = _build_reduction_report(pairs, begin_ts, end_ts)
            logging.info("AeroDataBox: %d airports above threshold", reports["aerodatabox"]["airports_above_threshold"])
        except Exception as e:
            logging.error("AeroDataBox reductions failed: %s", e)

    if AVIATIONSTACK_API_KEY:
        try:
            pairs = await _scan_airports(_fetch_aviationstack_airport, MAJOR_AFRICAN_AIRPORTS, begin_ts, end_ts, concurrency=2)
            reports["aviationstack"] = _build_reduction_report(pairs, begin_ts, end_ts)
            logging.info("AviationStack: %d airports above threshold", reports["aviationstack"]["airports_above_threshold"])
        except Exception as e:
            logging.error("AviationStack reductions failed: %s", e)

    _write_cache("traffic_reductions", reports)


# ---------------------------------------------------------------------------
# Disruptions — cancelled / delayed flights (AeroDataBox + AviationStack only;
# OpenSky does not expose flight status fields)
# ---------------------------------------------------------------------------

def _build_disruption_report(pairs: list[tuple[dict, dict]]) -> dict:
    above_threshold = []
    all_disrupted = []

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
        if disrupted == 0:
            continue
        disruption_pct = round(disrupted / total * 100, 1)
        entry = {
            "icao": airport_data["icao"],
            "name": airport_data["name"],
            "city": airport_data["city"],
            "country": airport_data["country"],
            "total_flights": total,
            "cancelled": cancelled,
            "delayed": delayed,
            "total_disruptions": disrupted,
            "disruption_pct": disruption_pct,
        }
        all_disrupted.append(entry)
        if disruption_pct >= 25.0:
            above_threshold.append(entry)

    above_threshold.sort(key=lambda x: x["disruption_pct"], reverse=True)
    top_by_count = sorted(all_disrupted, key=lambda x: x["total_disruptions"], reverse=True)[:TOP_N]
    top_by_pct = sorted(all_disrupted, key=lambda x: x["disruption_pct"], reverse=True)[:TOP_N]

    return {
        "report_date": _today(),
        "period": "past 3 days",
        "airports_checked": len(pairs),
        "airports_above_threshold": len(above_threshold),
        "above_25pct_disruption": above_threshold,
        "top_by_disruption_count": top_by_count,
        "top_by_disruption_pct": top_by_pct,
    }


async def cache_aviation_disruptions() -> None:
    logging.info("Caching aviation disruptions...")
    begin_ts, end_ts = _window_ts()
    reports: dict = {}

    if AERODATA_API_KEY:
        try:
            pairs = await _scan_airports(_fetch_aerodatabox_airport, MAJOR_AFRICAN_AIRPORTS, begin_ts, end_ts, concurrency=3)
            reports["aerodatabox"] = _build_disruption_report(pairs)
            logging.info("AeroDataBox disruptions: %d above threshold", reports["aerodatabox"]["airports_above_threshold"])
        except Exception as e:
            logging.error("AeroDataBox disruptions failed: %s", e)

    if AVIATIONSTACK_API_KEY:
        try:
            pairs = await _scan_airports(_fetch_aviationstack_airport, MAJOR_AFRICAN_AIRPORTS, begin_ts, end_ts, concurrency=2)
            reports["aviationstack"] = _build_disruption_report(pairs)
            logging.info("AviationStack disruptions: %d above threshold", reports["aviationstack"]["airports_above_threshold"])
        except Exception as e:
            logging.error("AviationStack disruptions failed: %s", e)

    _write_cache("aviation_disruptions", reports)


# ---------------------------------------------------------------------------

async def main() -> None:
    logging.info("Starting daily aviation cache refresh")
    await cache_traffic_reductions()
    await cache_aviation_disruptions()
    logging.info("Cache refresh complete")


if __name__ == "__main__":
    asyncio.run(main())
