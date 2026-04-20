"""
Async UNHCR displacement data fetcher.
Uses the public UNHCR Population Statistics API v1 — no authentication required.

For each country this module fetches:
  - Inflows  (coa=ISO): who is displaced INTO the country, by origin
  - Outflows (coo=ISO): where people FROM the country are displaced to

Both are aggregated to the latest available reference year, with a YoY trend
derived from the full multi-year history.
"""
import asyncio
import logging
from collections import defaultdict

import httpx

UNHCR_API_BASE = "https://api.unhcr.org/population/v1"
_MAX_PAGES = 50  # cap per request to avoid runaway pagination

_POPULATION_FIELDS = ("refugees", "asylum_seekers", "idps", "stateless", "oip")

# UNHCR uses different spellings for some African countries
_ISO_OVERRIDES: dict[str, str] = {
    "ivory coast": "CIV",
    "democratic republic of the congo": "COD",
    "republic of the congo": "COG",
    "central african republic": "CAF",
    "sao tome and principe": "STP",
    "cabo verde": "CPV",
    "gambia": "GMB",
    "eswatini": "SWZ",
    "tanzania": "TZA",
}


def _to_int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _parse_year(value) -> str | None:
    text = str(value or "").strip()
    return text if len(text) == 4 and text.isdigit() else None


async def fetch_iso_lookup(client: httpx.AsyncClient) -> dict[str, str]:
    """Return {country_name_lower: iso3} from the UNHCR countries endpoint."""
    resp = await client.get(f"{UNHCR_API_BASE}/countries/", params={"limit": 400})
    resp.raise_for_status()
    payload = resp.json()
    items = payload.get("items", []) if isinstance(payload, dict) else []
    lookup: dict[str, str] = {}
    for item in items:
        name = str(item.get("name") or "").strip()
        iso = str(item.get("iso") or "").strip().upper()
        if name and len(iso) == 3:
            lookup[name.lower()] = iso
    return lookup


def _resolve_iso(country: str, iso_lookup: dict[str, str]) -> str | None:
    key = country.lower().strip()
    if key in _ISO_OVERRIDES:
        return _ISO_OVERRIDES[key]
    return iso_lookup.get(key)


async def _fetch_paginated(
    client: httpx.AsyncClient,
    params: dict,
) -> list[dict]:
    """Fetch all pages for a /population/ query and return the combined records."""
    all_records: list[dict] = []
    page = 1
    max_pages = 1

    while page <= max_pages and page <= _MAX_PAGES:
        resp = await client.get(
            f"{UNHCR_API_BASE}/population/",
            params={**params, "page": page},
        )
        resp.raise_for_status()
        payload = resp.json()
        all_records.extend(payload.get("items", []) if isinstance(payload, dict) else [])
        max_pages = int(payload.get("maxPages", 1) or 1)
        page += 1

    return all_records


def _row_total(record: dict) -> int:
    return sum(_to_int(record.get(f, 0)) for f in _POPULATION_FIELDS)


def _build_yearly_totals(records: list[dict]) -> dict[str, int]:
    yearly: dict[str, int] = defaultdict(int)
    for r in records:
        year = _parse_year(r.get("year", ""))
        if year:
            yearly[year] += _row_total(r)
    return dict(sorted(yearly.items()))


def _build_trend(yearly: dict[str, int]) -> dict:
    years = sorted(yearly.keys())
    base: dict = {
        "basis": "yearly",
        "direction": "insufficient_data",
        "change": 0,
        "change_pct": None,
        "latest_year": years[-1] if years else None,
        "previous_year": None,
    }
    if len(years) < 2:
        return base
    latest, prev = yearly[years[-1]], yearly[years[-2]]
    change = latest - prev
    direction = "increasing" if change > 0 else ("decreasing" if change < 0 else "stable")
    return {
        **base,
        "direction": direction,
        "change": change,
        "change_pct": round(change / prev * 100, 1) if prev else None,
        "previous_year": years[-2],
    }


def _latest_year_records(records: list[dict]) -> tuple[str | None, list[dict]]:
    years = sorted({_parse_year(r.get("year", "")) for r in records if _parse_year(r.get("year", ""))})
    if not years:
        return None, []
    latest = years[-1]
    return latest, [r for r in records if _parse_year(r.get("year", "")) == latest]


def _sum_population_types(records: list[dict]) -> dict[str, int]:
    totals = {f: 0 for f in _POPULATION_FIELDS}
    for r in records:
        for f in _POPULATION_FIELDS:
            totals[f] += _to_int(r.get(f, 0))
    return totals


def _aggregate_by_partner(records: list[dict], partner_key: str) -> dict[str, int]:
    """Sum total displaced by a partner country field (coo_name or coa_name)."""
    by_partner: dict[str, int] = defaultdict(int)
    for r in records:
        name = str(r.get(partner_key) or "").strip()
        if not name or name == "-":
            name = "Unknown"
        by_partner[name] += _row_total(r)
    return dict(by_partner)


def _top_partners(by_partner: dict[str, int], top_n: int = 5) -> list[dict]:
    ranked = sorted(by_partner.items(), key=lambda x: x[1], reverse=True)
    grand_total = sum(by_partner.values())
    return [
        {
            "country": name,
            "total": total,
            "pct": round(total / grand_total * 100, 1) if grand_total else 0.0,
        }
        for name, total in ranked[:top_n]
        if total > 0
    ]


async def get_country_displacement(
    client: httpx.AsyncClient,
    country: str,
    iso_lookup: dict[str, str],
) -> dict:
    """
    Fetch and return inflow + outflow displacement summary for one country.
    Raises ValueError if ISO code cannot be resolved.
    """
    iso = _resolve_iso(country, iso_lookup)
    if not iso:
        raise ValueError(f"ISO code not found for: {country}")

    base = {"cf_type": "ISO", "limit": 1000}

    inflow_records, outflow_records = await asyncio.gather(
        _fetch_paginated(client, {**base, "coa": iso, "coo_all": "true"}),
        _fetch_paginated(client, {**base, "coo": iso, "coa_all": "true"}),
    )

    ref_year_in, latest_in = _latest_year_records(inflow_records)
    ref_year_out, latest_out = _latest_year_records(outflow_records)

    inflow_by_origin = _aggregate_by_partner(latest_in, "coo_name")
    outflow_by_dest = _aggregate_by_partner(latest_out, "coa_name")

    inflow_total = sum(inflow_by_origin.values())
    outflow_total = sum(outflow_by_dest.values())

    return {
        "country": country,
        "country_code": iso,
        "reference_year": ref_year_in or ref_year_out,
        "inflow": {
            "total": inflow_total,
            "population_types": _sum_population_types(latest_in),
            "trend": _build_trend(_build_yearly_totals(inflow_records)),
            "top_origins": _top_partners(inflow_by_origin),
        },
        "outflow": {
            "total": outflow_total,
            "population_types": _sum_population_types(latest_out),
            "trend": _build_trend(_build_yearly_totals(outflow_records)),
            "top_destinations": _top_partners(outflow_by_dest),
        },
    }


async def fetch_unhcr_africa_report(countries: list[str]) -> dict:
    """
    Fetch UNHCR displacement data for all African countries concurrently.
    Returns a continent-wide summary with per-country inflow/outflow breakdowns.
    """
    timeout = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=5.0)
    sem = asyncio.Semaphore(8)

    async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
        try:
            iso_lookup = await fetch_iso_lookup(client)
        except Exception as e:
            logging.error("UNHCR ISO lookup failed: %s", e)
            iso_lookup = {}

        async def _fetch_one(country: str) -> tuple[str, dict]:
            async with sem:
                try:
                    data = await get_country_displacement(client, country, iso_lookup)
                    return country, data
                except Exception as e:
                    logging.warning("UNHCR fetch failed for %s: %s", country, e)
                    return country, {"error": str(e)}

        results = await asyncio.gather(*[_fetch_one(c) for c in countries])

    countries_data: dict[str, dict] = {}
    total_inflow = 0
    total_outflow = 0
    for country, data in results:
        countries_data[country] = data
        if "error" not in data:
            total_inflow += data["inflow"]["total"]
            total_outflow += data["outflow"]["total"]

    return {
        "continent_totals": {
            "total_inflow": total_inflow,
            "total_outflow": total_outflow,
        },
        "countries": countries_data,
    }
