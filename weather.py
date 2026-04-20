"""
Severe meteorological and disaster event data fetcher for Africa.

Sources (all public, no authentication required):
  GDACS               — Active multi-hazard disaster alerts (Africa-filtered)
  RSMC La Réunion     — Indian Ocean tropical cyclone bulletin (NOAA text feed)
  RCC ACMAD Decadal   — 10-day climate bulletin (PDF via Jina AI reader)
  FAO DIEM            — Food/shock monitoring (ArcGIS feature service)
  ICPAC Droughtwatch  — Drought/rainfall dataset catalog (East Africa)
  ICPAC EA Hazards    — Hazard dataset catalog (East Africa)
  GloFAS              — 14-day river discharge flood forecasting (Open-Meteo, free)
  CAMS Air Quality    — 3-day African air quality / dust / smoke (Open-Meteo, free)
"""
import asyncio
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import httpx

from countries import AFRICAN_COUNTRIES

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AFRICAN_ISO3: set[str] = {c["iso3"].upper() for c in AFRICAN_COUNTRIES}

GDACS_RSS_URL = "https://www.gdacs.org/xml/rss.xml"
GDACS_CAP_URL = "https://www.gdacs.org/xml/gdacs_cap.xml"

RSMC_BULLETIN_URL = "https://tgftp.nws.noaa.gov/data/raw/wt/wtio30.fmee..txt"

ACMAD_PAGE_URL = "https://rcc.acmad.org/dacadebulletin.php"
JINA_PREFIX = "https://r.jina.ai/"

FAO_DIEM_URL = (
    "https://services5.arcgis.com/sjP4Ugu5s0dZWLjd/arcgis/rest/services"
    "/OER_Monitoring_System_View/FeatureServer/0/query"
)

ICPAC_DROUGHTWATCH_BASES = [
    "https://droughtwatch.icpac.net/api",
    "http://droughtwatch.icpac.net/api",
]
ICPAC_EA_HAZARDS_BASES = [
    "https://eahazardswatch.icpac.net/api",
    "http://eahazardswatch.icpac.net/api",
]

GDACS_ALERT_ORDER = {"red": 0, "orange": 1, "green": 2}
GDACS_EVENT_LABELS = {
    "EQ": "Earthquake", "TC": "Tropical Cyclone", "FL": "Flood",
    "VO": "Volcano", "DR": "Drought", "WF": "Wildfire",
}

GLOFAS_URL = "https://flood-api.open-meteo.com/v1/flood"
CAMS_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

# Capital coordinates for all 54 African countries (lat, lon)
CAPITAL_COORDS: dict[str, tuple[float, float]] = {
    "Algeria": (36.737, 3.086),
    "Angola": (-8.836, 13.234),
    "Benin": (6.366, 2.426),
    "Botswana": (-24.654, 25.906),
    "Burkina Faso": (12.364, -1.533),
    "Burundi": (-3.389, 29.354),
    "Cabo Verde": (14.933, -23.513),
    "Cameroon": (3.866, 11.517),
    "Central African Republic": (4.361, 18.555),
    "Chad": (12.107, 15.044),
    "Comoros": (-11.703, 43.255),
    "Democratic Republic of the Congo": (-4.325, 15.322),
    "Djibouti": (11.589, 43.145),
    "Egypt": (30.033, 31.233),
    "Equatorial Guinea": (3.750, 8.783),
    "Eritrea": (15.338, 38.931),
    "Eswatini": (-26.317, 31.133),
    "Ethiopia": (9.025, 38.747),
    "Gabon": (0.394, 9.454),
    "Gambia": (13.454, -16.579),
    "Ghana": (5.603, -0.187),
    "Guinea": (9.538, -13.677),
    "Guinea-Bissau": (11.863, -15.597),
    "Ivory Coast": (6.820, -5.275),
    "Kenya": (-1.292, 36.822),
    "Lesotho": (-29.318, 27.484),
    "Liberia": (6.300, -10.797),
    "Libya": (32.903, 13.180),
    "Madagascar": (-18.914, 47.536),
    "Malawi": (-13.966, 33.787),
    "Mali": (12.650, -8.000),
    "Mauritania": (18.079, -15.965),
    "Mauritius": (-20.162, 57.499),
    "Morocco": (34.021, -6.834),
    "Mozambique": (-25.966, 32.589),
    "Namibia": (-22.558, 17.083),
    "Niger": (13.512, 2.125),
    "Nigeria": (9.058, 7.498),
    "Republic of the Congo": (-4.264, 15.283),
    "Rwanda": (-1.940, 30.060),
    "Sao Tome and Principe": (0.336, 6.727),
    "Senegal": (14.693, -17.447),
    "Seychelles": (-4.619, 55.452),
    "Sierra Leone": (8.489, -13.234),
    "Somalia": (2.046, 45.342),
    "South Africa": (-25.747, 28.187),
    "South Sudan": (4.859, 31.571),
    "Sudan": (15.552, 32.532),
    "Tanzania": (-6.173, 35.739),
    "Togo": (6.137, 1.212),
    "Tunisia": (36.819, 10.166),
    "Uganda": (0.347, 32.583),
    "Zambia": (-15.414, 28.283),
    "Zimbabwe": (-17.829, 31.052),
}

CAMS_AFRICA_ZONES: list[dict] = [
    {"name": "Sahara / Sahel Dust Belt", "lat": 18.0, "lon": 10.0},
    {"name": "West Africa Coast (Dakar–Accra)", "lat": 10.0, "lon": -8.0},
    {"name": "Gulf of Guinea / Nigeria Delta", "lat": 5.0, "lon": 4.0},
    {"name": "Congo Basin", "lat": -2.0, "lon": 23.0},
    {"name": "East African Rift (Kenya–Tanzania)", "lat": -1.0, "lon": 37.0},
    {"name": "Horn of Africa", "lat": 8.0, "lon": 44.0},
    {"name": "Southern Africa (Zimbabwe–Mozambique)", "lat": -18.0, "lon": 32.0},
    {"name": "Cape / South Africa", "lat": -33.0, "lon": 18.0},
    {"name": "North Africa Coast (Morocco–Egypt)", "lat": 32.0, "lon": 15.0},
    {"name": "Nile Delta / Egypt", "lat": 30.0, "lon": 31.0},
    {"name": "Madagascar", "lat": -19.0, "lon": 47.0},
    {"name": "Ethiopia Highlands", "lat": 9.0, "lon": 39.0},
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text or "").strip()


def _ns_find(element, local_name: str) -> str | None:
    """Find child element by local name, ignoring XML namespace prefix."""
    for child in element.iter():
        if child.tag.split("}")[-1] == local_name and child.text:
            return child.text.strip()
    return None


# ---------------------------------------------------------------------------
# GDACS
# ---------------------------------------------------------------------------

async def fetch_gdacs_africa(client: httpx.AsyncClient) -> dict:
    """Fetch active GDACS disaster events affecting African countries."""
    events: list[dict] = []
    seen_ids: set[str] = set()

    for url in [GDACS_RSS_URL, GDACS_CAP_URL]:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
            items = root.findall(".//item")

            for item in items:
                iso3 = (_ns_find(item, "iso3") or "").upper()
                if iso3 not in AFRICAN_ISO3:
                    continue

                event_id = _ns_find(item, "eventid") or ""
                episode_id = _ns_find(item, "episodeid") or ""
                dedup_key = f"{event_id}-{episode_id}"
                if dedup_key in seen_ids:
                    continue
                seen_ids.add(dedup_key)

                etype = (_ns_find(item, "eventtype") or "").upper()
                alert = (_ns_find(item, "alertlevel") or "Green").capitalize()

                report_url = None
                if event_id and etype:
                    report_url = (
                        f"https://www.gdacs.org/report.aspx?eventid={event_id}"
                        + (f"&episodeid={episode_id}" if episode_id else "")
                        + f"&eventtype={etype}"
                    )

                events.append({
                    "event_type": GDACS_EVENT_LABELS.get(etype, etype or "Unknown"),
                    "alert_level": alert,
                    "country": _ns_find(item, "country"),
                    "iso3": iso3,
                    "severity": _strip_html(_ns_find(item, "severity") or ""),
                    "population_affected": _ns_find(item, "population"),
                    "from_date": _ns_find(item, "fromdate"),
                    "to_date": _ns_find(item, "todate"),
                    "title": _ns_find(item, "title"),
                    "url": report_url,
                })

            if events:
                break  # got results from RSS, skip CAP feed

        except Exception as e:
            logging.warning("GDACS feed %s failed: %s", url, e)

    events.sort(key=lambda e: GDACS_ALERT_ORDER.get(e["alert_level"].lower(), 3))

    return {
        "fetched_at": _now_iso(),
        "total_active": len(events),
        "red_alerts": sum(1 for e in events if e["alert_level"].lower() == "red"),
        "orange_alerts": sum(1 for e in events if e["alert_level"].lower() == "orange"),
        "events": events,
    }


# ---------------------------------------------------------------------------
# RSMC La Réunion
# ---------------------------------------------------------------------------

async def fetch_rsmc_bulletin(client: httpx.AsyncClient) -> dict:
    """Fetch and parse the latest RSMC La Réunion tropical cyclone bulletin."""
    resp = await client.get(RSMC_BULLETIN_URL)
    resp.raise_for_status()
    text = resp.text.replace("\r", "")

    if not re.search(r"RSMC\s*/\s*TROPICAL\s*CYCLONE\s*CENTER\s*/\s*LA\s+REUNION", text, re.IGNORECASE):
        return {
            "fetched_at": _now_iso(),
            "available": False,
            "note": "No active RSMC La Réunion cyclone bulletin.",
        }

    def _field(pattern: str) -> str | None:
        m = re.search(pattern, text, re.IGNORECASE)
        return m.group(1).strip() if m else None

    max_wind_kt = _field(r"5\.A\s+MAX\s+AVERAGE\s+WIND\s+SPEED[^:]*:\s*(\d+)\s*KT")
    pressure = _field(r"4\.A\s+CENTRAL\s+PRESSURE:\s*(\d+)\s*HPA")
    movement_dir = _field(r"MOVEMENT:\s*([^\n\d]+)\s*\d+\s*KT")
    movement_spd = _field(r"MOVEMENT:\s*[^\n\d]+\s*(\d+)\s*KT")
    system_type = _field(r"1\.A\s+([^\n]+)")
    warning_num = _field(r"0\.A\s+WARNING\s+NUMBER:\s*([\s\S]*?)\n1\.A")
    position = _field(r"WITHIN\s+30\s+NM\s+RADIUS\s+OF\s+POINT\s+([^\n]+)")

    wind = int(max_wind_kt) if max_wind_kt and max_wind_kt.isdigit() else 0
    if wind >= 64 or re.search(r"intense|cyclone", system_type or "", re.IGNORECASE):
        severity = "High"
    elif wind >= 34:
        severity = "Moderate"
    else:
        severity = "Low"

    return {
        "fetched_at": _now_iso(),
        "available": True,
        "warning_number": warning_num,
        "system_type": system_type,
        "current_position": position,
        "max_wind_kt": max_wind_kt,
        "central_pressure_hpa": pressure,
        "movement": f"{movement_dir.strip()} at {movement_spd} kt" if movement_dir and movement_spd else None,
        "severity": severity,
        "url": RSMC_BULLETIN_URL,
    }


# ---------------------------------------------------------------------------
# RCC ACMAD Decadal Bulletin
# ---------------------------------------------------------------------------

async def fetch_acmad_decadal(client: httpx.AsyncClient) -> dict:
    """Fetch RCC ACMAD decadal bulletin via Jina AI PDF reader."""
    try:
        resp = await client.get(ACMAD_PAGE_URL)
        resp.raise_for_status()
        html = resp.text
    except Exception as e:
        return {"fetched_at": _now_iso(), "available": False, "error": str(e)}

    def _find_pdf(pattern: str) -> str | None:
        m = re.search(pattern, html, re.IGNORECASE)
        if not m:
            return None
        href = m.group(1)
        if href.startswith("http"):
            return href
        return f"https://rcc.acmad.org/{href.lstrip('/')}"

    pdf_url = (
        _find_pdf(r'href=["\']([^"\']*Bull_dek\.pdf[^"\']*)["\']')
        or _find_pdf(r'href=["\']([^"\']*HIGHLIHTS_DEKAD\.pdf[^"\']*)["\']')
        or _find_pdf(r'src=["\']([^"\']*HIGHLIHTS_DEKAD\.pdf[^"\']*)["\']')
    )

    if not pdf_url:
        return {
            "fetched_at": _now_iso(),
            "available": False,
            "note": "No bulletin PDF found on ACMAD page.",
            "source_url": ACMAD_PAGE_URL,
        }

    # Read PDF via Jina AI public reader
    normalized = re.sub(r"^https?://", "", pdf_url)
    jina_url = f"{JINA_PREFIX}http://{normalized}"
    try:
        resp = await client.get(jina_url, timeout=httpx.Timeout(60.0))
        resp.raise_for_status()
        digest = resp.text[:5000]
    except Exception as e:
        return {
            "fetched_at": _now_iso(),
            "available": False,
            "error": f"PDF read failed: {e}",
            "pdf_url": pdf_url,
        }

    period_m = re.search(r"REPORTING\s*PERIOD\s*:?\s*([^\n\.]{3,60})", digest, re.IGNORECASE)
    issue_m = re.search(r"ISSUE\s*DATE\s*:?\s*([^\n\.]{3,40})", digest, re.IGNORECASE)

    signal_lines = [
        line.strip() for line in digest.split("\n")
        if line.strip() and re.search(
            r"outlook|rainfall|precipitation|temperature|dry|wet|flood|drought|above.average|below.average",
            line, re.IGNORECASE
        )
    ][:10]

    return {
        "fetched_at": _now_iso(),
        "available": True,
        "reporting_period": period_m.group(1).strip() if period_m else None,
        "issue_date": issue_m.group(1).strip() if issue_m else None,
        "highlights": signal_lines,
        "pdf_url": pdf_url,
        "source_url": ACMAD_PAGE_URL,
    }


# ---------------------------------------------------------------------------
# FAO DIEM
# ---------------------------------------------------------------------------

async def fetch_fao_diem_africa(client: httpx.AsyncClient) -> dict:
    """Fetch FAO DIEM monitoring records for African countries (most recent per country)."""
    iso3_list = "','".join(sorted(AFRICAN_ISO3))
    params = {
        "f": "json",
        "where": f"admin0_isocode IN ('{iso3_list}')",
        "outFields": (
            "admin0_name_en,admin0_isocode,round,validation_date,"
            "shocks_highlights,crop_highlights,"
            "shocks_recommendations,crop_recommendations,country_brief_link"
        ),
        "orderByFields": "validation_date DESC",
        "resultRecordCount": 200,
        "returnGeometry": "false",
    }

    try:
        resp = await client.get(FAO_DIEM_URL, params=params)
        resp.raise_for_status()
        payload = resp.json()
    except Exception as e:
        return {"fetched_at": _now_iso(), "available": False, "error": str(e)}

    by_country: dict[str, dict] = {}
    for feat in payload.get("features", []):
        attrs = feat.get("attributes", {})
        iso = (attrs.get("admin0_isocode") or "").upper()
        if iso in by_country:
            continue  # already have most recent
        val_ts = attrs.get("validation_date")
        val_date = None
        if val_ts:
            try:
                val_date = datetime.utcfromtimestamp(val_ts / 1000).strftime("%Y-%m-%d")
            except Exception:
                pass
        by_country[iso] = {
            "country": attrs.get("admin0_name_en"),
            "iso3": iso,
            "round": attrs.get("round"),
            "validation_date": val_date,
            "shocks_highlights": _strip_html(attrs.get("shocks_highlights") or ""),
            "crop_highlights": _strip_html(attrs.get("crop_highlights") or ""),
            "shocks_recommendations": _strip_html(attrs.get("shocks_recommendations") or ""),
            "crop_recommendations": _strip_html(attrs.get("crop_recommendations") or ""),
            "brief_url": attrs.get("country_brief_link"),
        }

    return {
        "fetched_at": _now_iso(),
        "available": True,
        "countries_with_data": len(by_country),
        "countries": by_country,
    }


# ---------------------------------------------------------------------------
# ICPAC (East Africa only — Droughtwatch + EA Hazards Watch)
# ---------------------------------------------------------------------------

async def _icpac_fetch(client: httpx.AsyncClient, bases: list[str], path: str) -> list:
    errors: list[str] = []
    for base in bases:
        try:
            resp = await client.get(f"{base}{path}")
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list) and data:
                return data
            errors.append(f"{base}: empty or non-list response")
        except Exception as e:
            errors.append(f"{base}: {e}")
    raise RuntimeError("; ".join(errors))


async def fetch_icpac_droughtwatch(client: httpx.AsyncClient) -> dict:
    """Fetch ICPAC Droughtwatch dataset catalog."""
    try:
        categories = await _icpac_fetch(client, ICPAC_DROUGHTWATCH_BASES, "/categories/")
        datasets = await _icpac_fetch(client, ICPAC_DROUGHTWATCH_BASES, "/datasets/")
        return {
            "fetched_at": _now_iso(),
            "available": True,
            "coverage": "East Africa (Burundi, Comoros, Djibouti, Eritrea, Ethiopia, Kenya, Rwanda, Somalia, South Sudan, Sudan, Tanzania, Uganda)",
            "category_count": len(categories),
            "dataset_count": len(datasets),
            "categories": categories,
            "datasets": datasets,
        }
    except Exception as e:
        return {"fetched_at": _now_iso(), "available": False, "error": str(e)}


async def fetch_icpac_ea_hazards(client: httpx.AsyncClient) -> dict:
    """Fetch ICPAC EA Hazards Watch dataset catalog."""
    try:
        datasets = await _icpac_fetch(client, ICPAC_EA_HAZARDS_BASES, "/datasets")
        categories = sorted({
            ds.get("category") for ds in datasets
            if isinstance(ds, dict) and ds.get("category")
        })
        return {
            "fetched_at": _now_iso(),
            "available": True,
            "coverage": "East Africa",
            "category_count": len(categories),
            "dataset_count": len(datasets),
            "categories": categories,
            "datasets": datasets,
        }
    except Exception as e:
        return {"fetched_at": _now_iso(), "available": False, "error": str(e)}


# ---------------------------------------------------------------------------
# GloFAS (Open-Meteo Flood API)
# ---------------------------------------------------------------------------

def _classify_flood(ratio: float | None, discharge: float | None) -> str:
    if discharge is None or discharge < 10:
        return "Low"
    if ratio is not None and ratio >= 1.4:
        return "High"
    if ratio is not None and ratio >= 1.15:
        return "Watch"
    if ratio is None and discharge >= 40:
        return "Watch"
    return "Low"


async def _query_glofas_point(client: httpx.AsyncClient, lat: float, lon: float) -> dict | None:
    try:
        resp = await client.get(
            GLOFAS_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "daily": "river_discharge,river_discharge_mean,river_discharge_max",
                "forecast_days": 14,
            },
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


async def fetch_glofas_africa(client: httpx.AsyncClient) -> dict:
    """Fetch 14-day GloFAS river discharge flood forecasts for all African capitals."""
    PROBE_OFFSET = 1.2
    results: list[dict] = []

    async def _probe_country(country: str, lat: float, lon: float) -> dict:
        probes = [
            (lat, lon),
            (lat + PROBE_OFFSET, lon),
            (lat - PROBE_OFFSET, lon),
            (lat, lon + PROBE_OFFSET),
            (lat, lon - PROBE_OFFSET),
        ]
        tasks = [_query_glofas_point(client, p[0], p[1]) for p in probes]
        responses = await asyncio.gather(*tasks)

        max_discharge = None
        max_ratio = None
        for r in responses:
            if not r or "daily" not in r:
                continue
            daily = r["daily"]
            discharges = [v for v in (daily.get("river_discharge") or []) if v is not None]
            means = [v for v in (daily.get("river_discharge_mean") or []) if v is not None]
            maxes = [v for v in (daily.get("river_discharge_max") or []) if v is not None]
            if not discharges:
                continue
            peak = max(discharges)
            if max_discharge is None or peak > max_discharge:
                max_discharge = peak
            if means and maxes:
                mean_val = sum(means) / len(means)
                max_val = max(maxes)
                if mean_val > 0:
                    ratio = max_val / mean_val
                    if max_ratio is None or ratio > max_ratio:
                        max_ratio = ratio

        risk = _classify_flood(max_ratio, max_discharge)
        entry: dict = {
            "country": country,
            "risk_level": risk,
            "peak_discharge_m3s": round(max_discharge, 1) if max_discharge is not None else None,
            "discharge_ratio": round(max_ratio, 2) if max_ratio is not None else None,
        }
        return entry

    tasks = [_probe_country(c, lat, lon) for c, (lat, lon) in CAPITAL_COORDS.items()]
    all_results = await asyncio.gather(*tasks, return_exceptions=True)

    for r in all_results:
        if isinstance(r, Exception):
            logging.warning("GloFAS probe failed: %s", r)
        elif r:
            results.append(r)

    results.sort(key=lambda x: {"High": 0, "Watch": 1, "Low": 2}.get(x["risk_level"], 3))
    high = sum(1 for r in results if r["risk_level"] == "High")
    watch = sum(1 for r in results if r["risk_level"] == "Watch")

    return {
        "fetched_at": _now_iso(),
        "available": True,
        "high_risk_count": high,
        "watch_count": watch,
        "countries": results,
    }


# ---------------------------------------------------------------------------
# CAMS Air Quality (Open-Meteo Air Quality API)
# ---------------------------------------------------------------------------

def _classify_aqi(aqi: float | None) -> str:
    if aqi is None:
        return "Unknown"
    if aqi >= 100:
        return "High"
    if aqi >= 50:
        return "Watch"
    return "Low"


async def fetch_cams_africa(client: httpx.AsyncClient) -> dict:
    """Fetch 3-day CAMS air quality forecasts across 12 predefined Africa monitoring zones."""
    month = datetime.now(timezone.utc).month
    is_harmattan = month in (11, 12, 1, 2, 3)

    async def _fetch_zone(zone: dict) -> dict:
        try:
            resp = await client.get(
                CAMS_URL,
                params={
                    "latitude": zone["lat"],
                    "longitude": zone["lon"],
                    "hourly": "european_aqi,pm2_5,pm10,dust",
                    "forecast_days": 3,
                },
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            return {"zone": zone["name"], "available": False, "error": str(e)}

        hourly = data.get("hourly", {})
        aqi_vals = [v for v in (hourly.get("european_aqi") or []) if v is not None]
        pm25_vals = [v for v in (hourly.get("pm2_5") or []) if v is not None]
        dust_vals = [v for v in (hourly.get("dust") or []) if v is not None]

        peak_aqi = max(aqi_vals) if aqi_vals else None
        peak_pm25 = max(pm25_vals) if pm25_vals else None
        peak_dust = max(dust_vals) if dust_vals else None

        signals: list[str] = []
        if peak_dust is not None and peak_dust >= 120:
            signals.append("saharan_dust")
        if is_harmattan and peak_dust is not None and peak_dust >= 30:
            signals.append("harmattan")
        if peak_pm25 is not None and peak_pm25 >= 35 and (peak_dust is None or peak_dust < 95):
            signals.append("wildfire_smoke")

        return {
            "zone": zone["name"],
            "available": True,
            "risk_level": _classify_aqi(peak_aqi),
            "peak_aqi": round(peak_aqi, 1) if peak_aqi is not None else None,
            "peak_pm2_5_ugm3": round(peak_pm25, 1) if peak_pm25 is not None else None,
            "peak_dust_ugm3": round(peak_dust, 1) if peak_dust is not None else None,
            "signals": signals,
        }

    zone_results = await asyncio.gather(*[_fetch_zone(z) for z in CAMS_AFRICA_ZONES], return_exceptions=True)

    zones: list[dict] = []
    for r in zone_results:
        if isinstance(r, Exception):
            logging.warning("CAMS zone fetch failed: %s", r)
        else:
            zones.append(r)

    zones.sort(key=lambda x: {"High": 0, "Watch": 1, "Low": 2, "Unknown": 3}.get(x.get("risk_level", "Unknown"), 3))
    high = sum(1 for z in zones if z.get("risk_level") == "High")
    watch = sum(1 for z in zones if z.get("risk_level") == "Watch")

    return {
        "fetched_at": _now_iso(),
        "available": True,
        "high_risk_zones": high,
        "watch_zones": watch,
        "harmattan_season": is_harmattan,
        "zones": zones,
    }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def fetch_weather_africa_report() -> dict:
    """Fetch all severe meteorological and disaster event data for Africa concurrently (8 sources)."""
    timeout = httpx.Timeout(connect=10.0, read=45.0, write=10.0, pool=5.0)

    # SSL verification disabled to handle ICPAC certificate issues (same as original script)
    async with httpx.AsyncClient(follow_redirects=True, timeout=timeout, verify=False) as client:
        results = await asyncio.gather(
            fetch_gdacs_africa(client),
            fetch_rsmc_bulletin(client),
            fetch_acmad_decadal(client),
            fetch_fao_diem_africa(client),
            fetch_icpac_droughtwatch(client),
            fetch_icpac_ea_hazards(client),
            fetch_glofas_africa(client),
            fetch_cams_africa(client),
            return_exceptions=True,
        )

    keys = ["gdacs", "rsmc_reunion", "acmad_decadal", "fao_diem", "icpac_droughtwatch", "icpac_ea_hazards", "glofas", "cams_air_quality"]

    output: dict = {}
    for key, result in zip(keys, results):
        if isinstance(result, Exception):
            logging.warning("%s fetch failed: %s", key, result)
            output[key] = {"fetched_at": _now_iso(), "available": False, "error": str(result)}
        else:
            output[key] = result

    return output
