"""
NOTAM fetching for African airports via Autorouter and SkyLink APIs.

Two providers, same normalized schema. Per-airport failures are recorded in
`fetch_errors` rather than aborting the run.
"""
import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Iterable

import httpx

AUTOROUTER_URL = "https://www.autorouter.aero/notam/"
# SkyLink is fronted by RapidAPI. Host header is required by the gateway.
SKYLINK_HOST = "skylink-api.p.rapidapi.com"
SKYLINK_URL = f"https://{SKYLINK_HOST}/notams"

AUTOROUTER_BATCH_SIZE = 5
AUTOROUTER_LIMIT = 100
SKYLINK_LIMIT = 50
# RapidAPI free tiers cap at ~1 req/s. Stay sequential and pace ourselves.
SKYLINK_DELAY_S = 1.2
SKYLINK_RETRY_DELAY_S = 5.0

# Major African airports (one or two per country, capitals + key hubs).
# Override per call by passing `icao_codes`.
DEFAULT_AFRICAN_AIRPORTS: list[str] = [
    "DAAG",  # Algiers, Algeria
    "FNLU",  # Luanda, Angola
    "DBBB",  # Cotonou, Benin
    "FBSK",  # Gaborone, Botswana
    "DFFD",  # Ouagadougou, Burkina Faso
    "HBBA",  # Bujumbura, Burundi
    "GVAC",  # Sal, Cape Verde
    "FKYS",  # Yaoundé, Cameroon
    "FEFF",  # Bangui, Central African Republic
    "FTTJ",  # N'Djamena, Chad
    "FMCH",  # Moroni, Comoros
    "FZAA",  # Kinshasa, DRC
    "HDAM",  # Djibouti
    "HECA",  # Cairo, Egypt
    "FGSL",  # Malabo, Equatorial Guinea
    "HHAS",  # Asmara, Eritrea
    "FDMS",  # Manzini, Eswatini
    "HAAB",  # Addis Ababa, Ethiopia
    "FOOL",  # Libreville, Gabon
    "GBYD",  # Banjul, Gambia
    "DGAA",  # Accra, Ghana
    "GUCY",  # Conakry, Guinea
    "GGOV",  # Bissau, Guinea-Bissau
    "DIAP",  # Abidjan, Ivory Coast
    "HKJK",  # Nairobi, Kenya
    "FXMM",  # Maseru, Lesotho
    "GLRB",  # Monrovia, Liberia
    "HLLT",  # Tripoli, Libya
    "FMMI",  # Antananarivo, Madagascar
    "FWKI",  # Lilongwe, Malawi
    "GABS",  # Bamako, Mali
    "GQNN",  # Nouakchott, Mauritania
    "FIMP",  # Port Louis, Mauritius
    "GMMN",  # Casablanca, Morocco
    "GMME",  # Rabat, Morocco
    "FQMA",  # Maputo, Mozambique
    "FYWH",  # Windhoek, Namibia
    "DRRN",  # Niamey, Niger
    "DNMM",  # Lagos, Nigeria
    "DNAA",  # Abuja, Nigeria
    "FCBB",  # Brazzaville, Congo
    "HRYR",  # Kigali, Rwanda
    "FPST",  # São Tomé
    "GOBD",  # Dakar, Senegal
    "FSIA",  # Mahé, Seychelles
    "GFLL",  # Freetown, Sierra Leone
    "HCMM",  # Mogadishu, Somalia
    "FAOR",  # Johannesburg, South Africa
    "FACT",  # Cape Town, South Africa
    "HJJJ",  # Juba, South Sudan
    "HSSS",  # Khartoum, Sudan
    "HTDA",  # Dar es Salaam, Tanzania
    "DXXX",  # Lomé, Togo
    "DTTA",  # Tunis, Tunisia
    "HUEN",  # Entebbe, Uganda
    "FLKK",  # Lusaka, Zambia
    "FVHA",  # Harare, Zimbabwe
]


# ---------------------------------------------------------------------------
# Categorisation
# ---------------------------------------------------------------------------

# Concise human-readable definition for each category. Shipped inside each
# cache file so any consumer (the analyst prompt, dashboards, ad-hoc readers)
# can render the same wording without duplicating it.
CATEGORY_DEFINITIONS: dict[str, str] = {
    "CLOSURE":     "Airport or runway fully closed.",
    "MAINTENANCE": "Works, upgrades, construction, or resurfacing.",
    "RESTRICTION": "Partial closure, reduced hours, weight limits, suspended procedures, prohibited areas, or traffic delays.",
    "NAVIGATION":  "ILS, VOR, or nav aid outage.",
    "OBSTACLE":    "Crane or temporary structure.",
    "SERVICES":    "Fuel availability, ATC changes, or fire/rescue level changes.",
    "OTHER":       "Does not fit the categories above.",
}

#
# Categories (uppercase, fixed taxonomy):
#   CLOSURE      — airport or runway fully closed
#   MAINTENANCE  — works, upgrades, construction, resurfacing
#   RESTRICTION  — partial closure, reduced hours, weight limits
#   NAVIGATION   — ILS, VOR, nav aid outages
#   OBSTACLE     — cranes, temporary structures
#   SERVICES     — fuel availability, ATC changes, fire/rescue levels
#   OTHER        — anything that does not fit the above
#
# Two-stage classifier: prefer ICAO Q-code (subject + condition) when present,
# fall back to keyword scan of the NOTAM text.

# Q-code condition codes (positions 4-5)
_Q_COND_CLOSED       = {"LC", "LN", "LF"}                  # closed
_Q_COND_MAINTENANCE  = {"LW", "AC", "LG"}                  # work in progress / withdrawn for maint
_Q_COND_RESTRICTION  = {"LR", "LT", "LE", "AH", "LX", "CM"}  # restricted, limited, hours changed
_Q_COND_OUTAGE       = {"LP", "LH", "LU", "LL", "DC", "CG"}  # unserviceable / degraded
_Q_COND_ERECTED      = {"CE"}                                # erected (obstacle)

# Q-code subject groups (positions 2-3)
_Q_SUBJ_RUNWAY = {"MR", "MS", "MU", "MW", "MA", "MB", "MK", "MP"}
_Q_SUBJ_TAXIWAY = {"MT", "MX", "MY"}
_Q_SUBJ_NAV = {
    # Generic radio nav (N..)
    "NA", "NB", "NC", "ND", "NF", "NL", "NM", "NN",
    "NO", "NT", "NV", "NX",
    # ILS family + markers (I..)
    "IC", "ID", "IG", "II", "IL", "IM", "IN", "IO",
    "IS", "IT", "IU", "IW", "IX", "IY",
}
_Q_SUBJ_OBSTACLE = {"OB", "OL", "OR"}
_Q_SUBJ_SERVICE = {
    # Facilities / fuel
    "FA", "FB", "FC", "FE", "FF", "FG", "FH", "FI", "FJ", "FK",
    "FL", "FM", "FO", "FP", "FR", "FS", "FT", "FU", "FW", "FZ",
    # Comms / surveillance
    "CA", "CB", "CC", "CD", "CE", "CG", "CL", "CM", "CP", "CR", "CS", "CT",
    # ATM
    "AA", "AC", "AD", "AE", "AF", "AG", "AH", "AL", "AN", "AO",
    "AP", "AR", "AS", "AT", "AU", "AV", "AW", "AX", "AY", "AZ",
}


def _classify_by_qcode(qcode: str) -> str | None:
    if not qcode or len(qcode) < 5 or qcode[0].upper() != "Q":
        return None
    subject = qcode[1:3].upper()
    condition = qcode[3:5].upper()

    # Obstacles win on subject — physical hazards regardless of condition
    if subject in _Q_SUBJ_OBSTACLE:
        return "OBSTACLE"
    if condition in _Q_COND_ERECTED and subject in _Q_SUBJ_OBSTACLE:
        return "OBSTACLE"

    # Closure: runway/taxiway closed → CLOSURE; nav closed → NAVIGATION; service closed → SERVICES
    if condition in _Q_COND_CLOSED:
        if subject in _Q_SUBJ_RUNWAY or subject in _Q_SUBJ_TAXIWAY:
            return "CLOSURE"
        if subject in _Q_SUBJ_NAV:
            return "NAVIGATION"
        if subject in _Q_SUBJ_SERVICE:
            return "SERVICES"
        return "CLOSURE"

    # Outage of a nav aid is NAVIGATION; outage of a service is SERVICES
    if condition in _Q_COND_OUTAGE:
        if subject in _Q_SUBJ_NAV:
            return "NAVIGATION"
        return "SERVICES"

    if condition in _Q_COND_MAINTENANCE:
        return "MAINTENANCE"
    if condition in _Q_COND_RESTRICTION:
        return "RESTRICTION"

    # Subject-only fallbacks
    if subject in _Q_SUBJ_NAV:
        return "NAVIGATION"
    if subject in _Q_SUBJ_SERVICE:
        return "SERVICES"
    return None


_KW_RUNWAY      = ("rwy", "runway", "twy", "taxiway", "apron")
_KW_NAV         = (" ils", "ils ", " vor", "vor ", " ndb", "ndb ", " dme", "dme ",
                   "rnav", "gnss", "gbas", "sbas", "localizer", "glide path",
                   "loc/dme", "papi", "vasis")
_KW_OBSTACLE    = ("crane", "obstacle", "obstruction", "scaffold", "temporary structure")
_KW_SERVICE     = ("fuel", "jet a1", "jet-a1", "avgas", " atc", "atc ", "afis",
                   "fire fighting", "fire-fighting", "rescue", "rff ", "customs",
                   "immigration", "ground service")
_KW_CLOSURE     = ("closed", "clsd", "shut down", "shutdown", "u/s", "out of service",
                   "unserviceable", "not available", "withdrawn", "ln to all aircraft")
_KW_MAINTENANCE = ("maintenance", "maint ", " maint", "wip ", "work in progress",
                   "construction", "resurfacing", "repaving", "repair", "upgrade",
                   "grading", "renovation")
_KW_RESTRICTION = ("restricted", "restriction", "limited", "limitation", "reduced",
                   "displaced thr", "shortened", "weight limit", "mtow",
                   "operational hours", "hours changed", "hr changed",
                   "suspended", "prohibited area", "subj to dla", "subject to delay")


def _classify_by_keywords(text: str) -> str:
    if not text:
        return "OTHER"
    # Pad with spaces so leading/trailing-space patterns word-match at the boundaries
    t = " " + text.lower() + " "

    has_rwy         = any(k in t for k in _KW_RUNWAY)
    has_nav         = any(k in t for k in _KW_NAV)
    has_obstacle    = any(k in t for k in _KW_OBSTACLE)
    has_service     = any(k in t for k in _KW_SERVICE)
    has_closure     = any(k in t for k in _KW_CLOSURE)
    has_maintenance = any(k in t for k in _KW_MAINTENANCE)
    has_restriction = any(k in t for k in _KW_RESTRICTION)

    # "u/s" / "out of service" / "unserviceable" is nav-aid jargon — if a nav aid
    # is named alongside it, the nav aid is the subject (even if RWY also appears)
    nav_outage_terms = ("u/s", "out of service", "unserviceable")
    if has_nav and any(k in t for k in nav_outage_terms):
        return "NAVIGATION"

    # Runway / taxiway is the primary subject — let the verb decide the category
    if has_rwy:
        if has_closure:
            return "CLOSURE"
        if has_maintenance:
            return "MAINTENANCE"
        if has_restriction:
            return "RESTRICTION"
    # Otherwise let the noun lead
    if has_nav:
        return "NAVIGATION"
    if has_obstacle:
        return "OBSTACLE"
    if has_service:
        return "SERVICES"
    # Verb-only fallbacks
    if has_closure:
        return "CLOSURE"
    if has_maintenance:
        return "MAINTENANCE"
    if has_restriction:
        return "RESTRICTION"
    return "OTHER"


def categorize_notam(text: str, qcode: str | None = None) -> str:
    cat = _classify_by_qcode(qcode) if qcode else None
    if cat:
        return cat
    return _classify_by_keywords(text or "")


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------

def _to_iso(value) -> str:
    """Coerce assorted date inputs to ISO 8601 UTC, or 'PERM' for permanent."""
    if value is None or value == "":
        return ""
    if isinstance(value, str):
        s = value.strip()
        if s.upper() in ("PERM", "PERMANENT"):
            return "PERM"
        # NOTAM raw 10-digit YYMMDDHHMM
        m = re.fullmatch(r"(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})", s)
        if m:
            yy, mm, dd, hh, mn = (int(x) for x in m.groups())
            year = 2000 + yy
            try:
                return datetime(year, mm, dd, hh, mn, tzinfo=timezone.utc).isoformat()
            except ValueError:
                return s
        # ISO-ish — try to parse and normalise
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat()
        except ValueError:
            return s
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(int(value), tz=timezone.utc).isoformat()
        except (ValueError, OSError, OverflowError):
            return ""
    return str(value)


def _compute_active_upcoming(start_iso: str, end_iso: str) -> tuple[bool, bool]:
    now = datetime.now(timezone.utc)
    start = None
    if start_iso and start_iso != "PERM":
        try:
            start = datetime.fromisoformat(start_iso)
        except ValueError:
            start = None
    end = None
    if end_iso == "PERM":
        end = None  # treat as open-ended
    elif end_iso:
        try:
            end = datetime.fromisoformat(end_iso)
        except ValueError:
            end = None

    is_upcoming = bool(start and start > now)
    started = (start is None) or (start <= now)
    ended = bool(end and end < now)
    is_active = started and not ended and not is_upcoming
    return is_active, is_upcoming


# ---------------------------------------------------------------------------
# Autorouter
# ---------------------------------------------------------------------------

def _normalize_autorouter(item: dict, fallback_icao: str = "") -> dict | None:
    """Map an Autorouter NOTAM record to the canonical schema."""
    if not isinstance(item, dict):
        return None
    icao = (
        item.get("LocationIndicator")
        or item.get("icao")
        or item.get("itema")
        or item.get("Icao")
        or fallback_icao
        or ""
    ).strip().upper()

    notam_id = (
        item.get("Ident")
        or item.get("id")
        or item.get("NotamID")
        or item.get("notamid")
        or ""
    )

    type_raw = (item.get("Type") or item.get("type") or "").strip().upper()
    type_code = type_raw[0] if type_raw and type_raw[0] in ("N", "R", "C") else type_raw

    start = _to_iso(
        item.get("StartValidity")
        or item.get("startvalidity")
        or item.get("itemb")
        or item.get("ValidFrom")
    )
    end_raw = (
        item.get("EndValidity")
        or item.get("endvalidity")
        or item.get("itemc")
        or item.get("ValidTo")
    )
    if isinstance(end_raw, str) and end_raw.strip().upper() in ("PERM", "PERMANENT"):
        end = "PERM"
    else:
        end = _to_iso(end_raw)

    text = (
        item.get("Text")
        or item.get("All")
        or item.get("iteme")
        or item.get("text")
        or item.get("raw")
        or ""
    )
    qcode = item.get("QCode") or item.get("qcode") or item.get("Q") or None

    is_active, is_upcoming = _compute_active_upcoming(start, end)
    return {
        "airport_icao": icao,
        "notam_id": str(notam_id),
        "type": type_code,
        "effective_start": start,
        "effective_end": end,
        "text": text,
        "category": categorize_notam(text, qcode),
        "is_active": is_active,
        "is_upcoming": is_upcoming,
        "source": "autorouter",
    }


async def _fetch_autorouter_batch(
    client: httpx.AsyncClient,
    icao_batch: list[str],
    start_validity: int | None,
    end_validity: int | None,
) -> list[dict]:
    params: dict[str, str | int] = {
        "itemas": json.dumps(icao_batch),
        "limit": AUTOROUTER_LIMIT,
    }
    if start_validity is not None:
        params["startvalidity"] = int(start_validity)
    if end_validity is not None:
        params["endvalidity"] = int(end_validity)

    resp = await client.get(AUTOROUTER_URL, params=params)
    resp.raise_for_status()
    payload = resp.json()
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("notams", "data", "results", "items"):
            if isinstance(payload.get(key), list):
                return payload[key]
    return []


async def fetch_autorouter_notams(
    icao_codes: Iterable[str],
    start_validity: int | None = None,
    end_validity: int | None = None,
) -> dict:
    """Fetch NOTAMs from Autorouter, batching ICAO codes 5 per request."""
    codes = [c.strip().upper() for c in icao_codes if c and c.strip()]
    notams: list[dict] = []
    fetch_errors: list[dict] = []
    seen: set[tuple[str, str]] = set()

    async with httpx.AsyncClient(timeout=60, headers={"User-Agent": "14N-API-INT/1.0"}) as client:
        for i in range(0, len(codes), AUTOROUTER_BATCH_SIZE):
            batch = codes[i:i + AUTOROUTER_BATCH_SIZE]
            try:
                items = await _fetch_autorouter_batch(client, batch, start_validity, end_validity)
            except Exception as e:
                logging.warning("Autorouter batch %s failed: %s", batch, e)
                for icao in batch:
                    fetch_errors.append({"icao": icao, "error": f"{type(e).__name__}: {e}"})
                continue

            for raw in items:
                norm = _normalize_autorouter(raw)
                if not norm or not norm["airport_icao"]:
                    continue
                # Filter to requested batch (defensive — some APIs return neighbours)
                if norm["airport_icao"] not in batch:
                    continue
                key = (norm["airport_icao"], norm["notam_id"])
                if key in seen:
                    continue
                seen.add(key)
                notams.append(norm)

    return _build_report(notams, codes, fetch_errors, source="autorouter")


# ---------------------------------------------------------------------------
# SkyLink
# ---------------------------------------------------------------------------

def _normalize_skylink(item: dict, fallback_icao: str) -> dict | None:
    if not isinstance(item, dict):
        return None
    icao = (
        item.get("icao")
        or item.get("airport_icao")
        or item.get("location")
        or fallback_icao
        or ""
    ).strip().upper()

    notam_id = (
        item.get("notam_id")
        or item.get("id")
        or item.get("ident")
        or ""
    )

    type_raw = (item.get("type") or item.get("notam_type") or "").strip().upper()
    type_code = type_raw[0] if type_raw and type_raw[0] in ("N", "R", "C") else type_raw

    start = _to_iso(
        item.get("effective_start")
        or item.get("start")
        or item.get("valid_from")
    )
    end_raw = (
        item.get("effective_end")
        or item.get("end")
        or item.get("valid_to")
    )
    if isinstance(end_raw, str) and end_raw.strip().upper() in ("PERM", "PERMANENT"):
        end = "PERM"
    else:
        end = _to_iso(end_raw)

    text = item.get("text") or item.get("body") or item.get("raw") or ""
    qcode = item.get("qcode") or item.get("q_code") or None

    is_active, is_upcoming = _compute_active_upcoming(start, end)
    return {
        "airport_icao": icao,
        "notam_id": str(notam_id),
        "type": type_code,
        "effective_start": start,
        "effective_end": end,
        "text": text,
        "category": categorize_notam(text, qcode),
        "is_active": is_active,
        "is_upcoming": is_upcoming,
        "source": "skylink",
    }


async def _fetch_skylink_one(
    client: httpx.AsyncClient,
    icao: str,
) -> tuple[str, list[dict] | Exception]:
    """Fetch a single airport. Retries once on 429 honouring Retry-After."""
    url = f"{SKYLINK_URL}/{icao}"
    params = {"limit": SKYLINK_LIMIT}
    for attempt in (1, 2):
        try:
            resp = await client.get(url, params=params)
        except Exception as e:
            return icao, e
        if resp.status_code == 429 and attempt == 1:
            retry_after = resp.headers.get("retry-after")
            try:
                wait = float(retry_after) if retry_after else SKYLINK_RETRY_DELAY_S
            except ValueError:
                wait = SKYLINK_RETRY_DELAY_S
            await asyncio.sleep(min(wait, 30.0))
            continue
        try:
            resp.raise_for_status()
            payload = resp.json()
        except Exception as e:
            return icao, e
        if isinstance(payload, list):
            return icao, payload
        if isinstance(payload, dict):
            for key in ("notams", "data", "results", "items"):
                if isinstance(payload.get(key), list):
                    return icao, payload[key]
        return icao, []
    return icao, RuntimeError("retry exhausted")


async def fetch_skylink_notams(
    icao_codes: Iterable[str],
    api_key: str,
) -> dict:
    """Fetch NOTAMs from SkyLink, one airport per request, capped concurrency."""
    if not api_key:
        return {
            "error": "SKYLINK_API_KEY not configured",
            "message": "Set SKYLINK_API_KEY in the environment to enable SkyLink NOTAM fetching.",
        }

    codes = [c.strip().upper() for c in icao_codes if c and c.strip()]
    notams: list[dict] = []
    fetch_errors: list[dict] = []
    seen: set[tuple[str, str]] = set()

    headers = {
        "X-RapidAPI-Key": api_key,
        "X-RapidAPI-Host": SKYLINK_HOST,
        "Accept": "application/json",
        "User-Agent": "14N-API-INT/1.0",
    }
    # Sequential with pacing — RapidAPI free tier ~1 req/s. ~57 airports * 1.2s ≈ 70s.
    results: list[tuple[str, list[dict] | Exception]] = []
    async with httpx.AsyncClient(timeout=30, headers=headers) as client:
        for i, icao in enumerate(codes):
            if i > 0:
                await asyncio.sleep(SKYLINK_DELAY_S)
            results.append(await _fetch_skylink_one(client, icao))

    for icao, outcome in results:
        if isinstance(outcome, Exception):
            fetch_errors.append({"icao": icao, "error": f"{type(outcome).__name__}: {outcome}"})
            continue
        for raw in outcome:
            norm = _normalize_skylink(raw, fallback_icao=icao)
            if not norm or not norm["airport_icao"]:
                continue
            key = (norm["airport_icao"], norm["notam_id"])
            if key in seen:
                continue
            seen.add(key)
            notams.append(norm)

    return _build_report(notams, codes, fetch_errors, source="skylink")


# ---------------------------------------------------------------------------
# Report shaping
# ---------------------------------------------------------------------------

def _build_report(
    notams: list[dict],
    airports_queried: list[str],
    fetch_errors: list[dict],
    source: str,
) -> dict:
    by_category: dict[str, int] = {}
    by_airport: dict[str, int] = {}
    active = 0
    upcoming = 0
    for n in notams:
        by_category[n["category"]] = by_category.get(n["category"], 0) + 1
        by_airport[n["airport_icao"]] = by_airport.get(n["airport_icao"], 0) + 1
        if n["is_active"]:
            active += 1
        if n["is_upcoming"]:
            upcoming += 1

    return {
        "report_date": datetime.now(timezone.utc).date().isoformat(),
        "source": source,
        "airports_queried": airports_queried,
        "airports_with_data": sorted(by_airport.keys()),
        "fetch_errors": fetch_errors,
        "category_definitions": CATEGORY_DEFINITIONS,
        "summary": {
            "total_notams": len(notams),
            "active": active,
            "upcoming": upcoming,
            "by_category": by_category,
            "by_airport": by_airport,
        },
        "notams": notams,
    }
