import argparse
import os
from datetime import datetime, timedelta

import httpx
from dotenv import load_dotenv

load_dotenv()

AERODATA_API_KEY = os.getenv("AERODATA_API_KEY", "")
AERODATA_API_HOST = "aerodatabox.p.rapidapi.com"
AERODATA_API_URL = "https://aerodatabox.p.rapidapi.com"

AVIATIONSTACK_API_KEY = os.getenv("AVIATIONSTACK_API_KEY", "")
AVIATIONSTACK_API_URL = "http://api.aviationstack.com/v1"

DEFAULT_ICAO = "HKJK"


def test_aerodatabox(icao: str = DEFAULT_ICAO) -> None:
    if not AERODATA_API_KEY:
        print("AERODATA_API_KEY is not configured.")
        return

    end_dt = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    begin_dt = end_dt - timedelta(hours=12)
    begin_s = begin_dt.strftime("%Y-%m-%dT%H:%M")
    end_s = end_dt.strftime("%Y-%m-%dT%H:%M")

    url = f"{AERODATA_API_URL}/flights/airports/icao/{icao}/{begin_s}/{end_s}"
    headers = {
        "X-RapidAPI-Key": AERODATA_API_KEY,
        "X-RapidAPI-Host": AERODATA_API_HOST,
    }

    print("=== AeroDataBox sample ===")
    print(f"URL: {url}")

    with httpx.Client(timeout=30) as client:
        resp = client.get(url, headers=headers)

    print("Status:", resp.status_code)
    if resp.status_code != 200:
        print(resp.text)
        return

    payload = resp.json()
    departures = payload.get("departures", [])
    arrivals = payload.get("arrivals", [])

    print("Departures (first 5):")
    for idx, flight in enumerate(departures[:5], start=1):
        print(f"{idx}. {flight}")

    print("Arrivals (first 5):")
    for idx, flight in enumerate(arrivals[:5], start=1):
        print(f"{idx}. {flight}")


def test_aviationstack(icao: str = DEFAULT_ICAO) -> None:
    if not AVIATIONSTACK_API_KEY:
        print("AVIATIONSTACK_API_KEY is not configured.")
        return

    iata = icao_to_iata(icao)
    if not iata:
        print(f"Missing IATA code for ICAO {icao}")
        return

    date_str = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
    print("=== AviationStack sample ===")
    print(f"IATA: {iata}, date: {date_str}")

    params = {
        "access_key": AVIATIONSTACK_API_KEY,
        "dep_iata": iata,
        "flight_date": date_str,
        "limit": 10,
    }

    url = f"{AVIATIONSTACK_API_URL}/flights"
    with httpx.Client(timeout=30) as client:
        resp = client.get(url, params=params)

    print("Status:", resp.status_code)
    if resp.status_code != 200:
        print(resp.text)
        return

    payload = resp.json()
    data = payload.get("data", [])

    print("Flights (first 5):")
    for idx, flight in enumerate(data[:5], start=1):
        print(f"{idx}. {flight}")


def icao_to_iata(icao: str) -> str | None:
    mapping = {
        "HKJK": "NBO",
        "DAAG": "ALG",
        "DBBB": "COO",
        "FNLU": "LAD",
        "FEFF": "BGF",
        "FTTJ": "NDJ",
        "HDAM": "JIB",
        "HECA": "CAI",
        "FZAA": "FIH",
        "DNMM": "LOS",
        "FCBB": "BZV",
        "HRYR": "KGL",
        # Add more ICAO->IATA mappings as needed
    }
    return mapping.get(icao.upper().strip())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test AeroDataBox and AviationStack connectivity and sample flight output.")
    parser.add_argument("--icao", default=DEFAULT_ICAO, help="ICAO code to test (default: HKJK)")
    args = parser.parse_args()

    test_aerodatabox(args.icao)
    print()
    test_aviationstack(args.icao)
