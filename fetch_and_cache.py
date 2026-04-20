#!/usr/bin/env python3
"""
Daily cron job: fetch data and write cache files.
MCP tools read from these files and return instantly, staying under the 60s timeout.

Cache files written (CACHE_DIR, named by UTC date):
  travel_advisories_YYYY-MM-DD.json — advisory levels for all 54 African countries
"""
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from countries import ACLED_NAMES
from travel_advisories import fetch_advisories_for_countries

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


async def cache_travel_advisories() -> None:
    logging.info("Caching travel advisories for %d countries...", len(ACLED_NAMES))
    try:
        data = await fetch_advisories_for_countries(ACLED_NAMES)
        _write_cache("travel_advisories", data)
        logging.info("Travel advisories cached: %d countries", len(data))
    except Exception as e:
        logging.error("Travel advisories cache failed: %s", e)


async def main() -> None:
    logging.info("Starting daily cache refresh")
    await cache_travel_advisories()
    logging.info("Cache refresh complete")


if __name__ == "__main__":
    asyncio.run(main())
