"""
NOTAM fetching for African airports via Autorouter, SkyLink, and ASECNA.

Three providers, same normalized schema. Per-airport failures are recorded in
`fetch_errors` rather than aborting the run.
"""
import asyncio
from html import unescape as _html_unescape
import json
import logging
import re
import time
from datetime import datetime, timezone
from typing import Iterable

import httpx

# Autorouter — OAuth2 client_credentials, token TTL 1 hour. Wiki:
#   https://www.autorouter.aero/wiki/api/authentication/
#   https://www.autorouter.aero/wiki/api/notams
AUTOROUTER_API_BASE = "https://api.autorouter.aero/v1.0"
AUTOROUTER_URL = f"{AUTOROUTER_API_BASE}/notam"
AUTOROUTER_TOKEN_URL = f"{AUTOROUTER_API_BASE}/oauth2/token"

# SkyLink is fronted by RapidAPI. Host header is required by the gateway.
SKYLINK_HOST = "skylink-api.p.rapidapi.com"
SKYLINK_URL = f"https://{SKYLINK_HOST}/notams"

# Kill switch — when True, all SkyLink calls (cron + live MCP tool) are skipped.
# Flip to False to resume. Used to avoid burning the monthly RapidAPI quota.
SKYLINK_SUSPENDED = True

AUTOROUTER_BATCH_SIZE = 5
AUTOROUTER_LIMIT = 100
SKYLINK_LIMIT = 50
# RapidAPI free tiers cap at ~1 req/s. Stay sequential and pace ourselves.
SKYLINK_DELAY_S = 1.2
SKYLINK_RETRY_DELAY_S = 5.0

# ASECNA — public portal, no API key, POST form, HTML response.
ASECNA_URL = "https://ais.asecna.aero/en/ntm/notam.php"
ASECNA_DELAY_S = 0.5   # polite pacing; no documented rate limit
ASECNA_MAX_ROWS = 400

# Recency filter: keep only NOTAMs whose effective_start is within ±N days of
# now. Drops both stale (long-running) NOTAMs and far-future scheduled ones.
RECENT_WINDOW_DAYS = 7

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

# ASECNA member-state airports only (subset of DEFAULT_AFRICAN_AIRPORTS).
# Querying non-member airports returns empty — no point sending those requests.
ASECNA_AIRPORTS: list[str] = [
    "DBBB",  # Cotonou, Benin
    "DFFD",  # Ouagadougou, Burkina Faso
    "FKYS",  # Yaoundé, Cameroon
    "FEFF",  # Bangui, Central African Republic
    "FTTJ",  # N'Djamena, Chad
    "FMCH",  # Moroni, Comoros
    "FCBB",  # Brazzaville, Congo
    "DIAP",  # Abidjan, Ivory Coast
    "FGSL",  # Malabo, Equatorial Guinea
    "FOOL",  # Libreville, Gabon
    "GBYD",  # Banjul, Gambia
    "GGOV",  # Bissau, Guinea-Bissau
    "FMMI",  # Antananarivo, Madagascar
    "GABS",  # Bamako, Mali
    "GQNN",  # Nouakchott, Mauritania
    "DRRN",  # Niamey, Niger
    "GOBD",  # Dakar, Senegal
    "DXXX",  # Lomé, Togo
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
    """Coerce assorted date inputs to ISO 8601 UTC, or 'PERM' for permanent.

    Recognised string formats:
      - "PERM" / "PERMANENT" → "PERM"
      - 12-digit YYYYMMDDHHMM (SkyLink format)
      - 10-digit YYMMDDHHMM (legacy NOTAM ICAO format)
      - ISO 8601
    Trailing "EST" / "EST." (NOTAM "estimated" marker) is stripped before parsing.
    """
    if value is None or value == "":
        return ""
    if isinstance(value, str):
        s = value.strip().upper()
        if s in ("PERM", "PERMANENT"):
            return "PERM"
        # Strip NOTAM-specific suffixes like "EST" (estimated end time)
        s = re.sub(r"\s*EST\.?$", "", s)
        # 12-digit YYYYMMDDHHMM (what SkyLink returns)
        m = re.fullmatch(r"(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})", s)
        if m:
            yyyy, mm, dd, hh, mn = (int(x) for x in m.groups())
            try:
                return datetime(yyyy, mm, dd, hh, mn, tzinfo=timezone.utc).isoformat()
            except ValueError:
                return s
        # 10-digit YYMMDDHHMM (legacy NOTAM ICAO format)
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


def _is_within_recent_window(start_iso: str, window_days: int) -> bool:
    """True if effective_start is within ±window_days of now (UTC).

    NOTAMs with no parseable start time are excluded — we can't tell if
    they're recent. PERM applies only to the end, so start is still parsed
    normally for filtering.
    """
    if not start_iso or start_iso == "PERM":
        return False
    try:
        start = datetime.fromisoformat(start_iso)
    except ValueError:
        return False
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    return abs((start - now).total_seconds()) <= window_days * 86400


def _passes_recency_filter(notam: dict, window_days: int) -> bool:
    """Keep a NOTAM if it is currently active OR its effective_start is
    within ±window_days of now.

    The OR captures three operationally relevant states:
      - currently active (any duration — long-running NOTAMs are kept)
      - recently activated within the window
      - about to start within the window
    """
    if notam.get("is_active"):
        return True
    return _is_within_recent_window(notam.get("effective_start", ""), window_days)


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

# Token cache (process-lifetime). Token TTL is 1 hour per the wiki; we treat
# anything within 60s of expiry as stale to avoid clock-skew 401s.
_autorouter_token: str = ""
_autorouter_token_expiry: float = 0.0
_autorouter_token_lock: asyncio.Lock | None = None


def _autorouter_token_invalidate() -> None:
    global _autorouter_token, _autorouter_token_expiry
    _autorouter_token = ""
    _autorouter_token_expiry = 0.0


async def _get_autorouter_token(
    client: httpx.AsyncClient,
    client_id: str,
    client_secret: str,
) -> str:
    """OAuth2 client_credentials. client_id is the account email, client_secret the password."""
    global _autorouter_token, _autorouter_token_expiry, _autorouter_token_lock
    if _autorouter_token_lock is None:
        _autorouter_token_lock = asyncio.Lock()
    async with _autorouter_token_lock:
        if _autorouter_token and time.time() < _autorouter_token_expiry - 60:
            return _autorouter_token
        resp = await client.post(
            AUTOROUTER_TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
        )
        resp.raise_for_status()
        payload = resp.json()
        _autorouter_token = payload["access_token"]
        _autorouter_token_expiry = time.time() + int(payload.get("expires_in", 3600))
        return _autorouter_token


def _normalize_autorouter(item: dict, batch: list[str] | None = None) -> dict | None:
    """Map an Autorouter NOTAM record (per /v1.0/notam wiki) to the canonical schema.

    Wiki-documented fields:
      itema (list[str])  — applicable ICAO codes
      iteme (str)        — raw NOTAM text
      type  (str)        — N | R | C
      series (str), number (int), year (int) — used to build the standard ident
      code23 (str), code45 (str) — split Q-code; reconstructed as Qxxxx
      startvalidity / endvalidity (int) — Unix epoch; default end is 2^32-1 = "PERM"
      id (int)           — autorouter internal stable ID, used for de-dup
    """
    if not isinstance(item, dict):
        return None

    # Pick the ICAO that matches our requested batch when possible
    itema = item.get("itema") or []
    icao = ""
    if isinstance(itema, list) and itema:
        upper = [str(c).strip().upper() for c in itema if c]
        if batch:
            matches = [c for c in upper if c in batch]
            icao = matches[0] if matches else (upper[0] if upper else "")
        else:
            icao = upper[0] if upper else ""

    # NOTAM standard ident: <series><number>/<YY> — fall back to internal id
    series = item.get("series") or ""
    number = item.get("number")
    year = item.get("year")
    if series and number is not None and year is not None:
        notam_id = f"{series}{number}/{str(year)[-2:]}"
    else:
        notam_id = str(item.get("id") or "")

    type_raw = (str(item.get("type") or "")).strip().upper()
    type_code = type_raw[0] if type_raw and type_raw[0] in ("N", "R", "C") else type_raw

    start = _to_iso(item.get("startvalidity"))
    end_raw = item.get("endvalidity")
    # Wiki: default endvalidity is 2^32-1 (≈ year 2106). Treat as permanent.
    if isinstance(end_raw, (int, float)) and int(end_raw) >= (2**32 - 100):
        end = "PERM"
    else:
        end = _to_iso(end_raw)

    text = item.get("iteme") or ""

    # Q-code is split: code23 = subject (chars 2-3), code45 = condition (chars 4-5)
    code23 = (item.get("code23") or "").upper()
    code45 = (item.get("code45") or "").upper()
    qcode = f"Q{code23}{code45}" if (code23 or code45) else None

    is_active, is_upcoming = _compute_active_upcoming(start, end)
    return {
        "airport_icao": icao,
        "notam_id": notam_id,
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
    token: str,
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

    resp = await client.get(
        AUTOROUTER_URL,
        params=params,
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    payload = resp.json()
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        # Wiki: top-level `rows` is the array; keep other keys as defensive fallbacks.
        for key in ("rows", "notams", "data", "results", "items"):
            if isinstance(payload.get(key), list):
                return payload[key]
    return []


async def fetch_autorouter_notams(
    icao_codes: Iterable[str],
    client_id: str,
    client_secret: str,
    start_validity: int | None = None,
    end_validity: int | None = None,
    window_days: int = RECENT_WINDOW_DAYS,
) -> dict:
    """Fetch NOTAMs from Autorouter, batching ICAO codes 5 per request.

    `client_id` is the account email and `client_secret` is the password (per
    Autorouter's OAuth2 client_credentials flow).

    `window_days` (default 7) drives the operational-relevance filter: a NOTAM
    is kept if it is currently active OR its effective_start is within ±N days
    of now. This captures recently activated, currently active, and upcoming
    NOTAMs in one filter.
    """
    if not client_id or not client_secret:
        return {
            "error": "AUTOROUTER_CLIENT_ID / AUTOROUTER_CLIENT_SECRET not configured",
            "message": "Set AUTOROUTER_CLIENT_ID (account email) and AUTOROUTER_CLIENT_SECRET (account password) in the environment.",
        }

    codes = [c.strip().upper() for c in icao_codes if c and c.strip()]
    notams: list[dict] = []
    fetch_errors: list[dict] = []
    seen: set[tuple[str, str]] = set()

    async with httpx.AsyncClient(timeout=60, headers={"User-Agent": "14N-API-INT/1.0"}) as client:
        try:
            token = await _get_autorouter_token(client, client_id, client_secret)
        except Exception as e:
            err = f"Autorouter auth failed: {type(e).__name__}: {e}"
            logging.error(err)
            for icao in codes:
                fetch_errors.append({"icao": icao, "error": err})
            return _build_report([], codes, fetch_errors, source="autorouter")

        async def _fetch_with_retry(batch: list[str]) -> list[dict]:
            """Run a batch; on 401 refresh token once and retry."""
            nonlocal token
            try:
                return await _fetch_autorouter_batch(
                    client, batch, token, start_validity, end_validity,
                )
            except httpx.HTTPStatusError as e:
                if e.response.status_code != 401:
                    raise
                _autorouter_token_invalidate()
                token = await _get_autorouter_token(client, client_id, client_secret)
                return await _fetch_autorouter_batch(
                    client, batch, token, start_validity, end_validity,
                )

        for i in range(0, len(codes), AUTOROUTER_BATCH_SIZE):
            batch = codes[i:i + AUTOROUTER_BATCH_SIZE]
            try:
                items = await _fetch_with_retry(batch)
            except Exception as e:
                logging.warning("Autorouter batch %s failed: %s", batch, e)
                for icao in batch:
                    fetch_errors.append({"icao": icao, "error": f"{type(e).__name__}: {e}"})
                continue

            for raw in items:
                norm = _normalize_autorouter(raw, batch=batch)
                if not norm or not norm["airport_icao"]:
                    continue
                # Filter to requested batch (defensive — itema may include neighbours)
                if norm["airport_icao"] not in batch:
                    continue
                # Keep if currently active OR effective_start is within ±window_days
                if not _passes_recency_filter(norm, window_days):
                    continue
                key = (norm["airport_icao"], norm["notam_id"])
                if key in seen:
                    continue
                seen.add(key)
                notams.append(norm)

    return _build_report(notams, codes, fetch_errors, source="autorouter", window_days=window_days)


# ---------------------------------------------------------------------------
# SkyLink
# ---------------------------------------------------------------------------

def _normalize_skylink(item: dict, fallback_icao: str) -> dict | None:
    """Map a SkyLink NOTAM record (RapidAPI listing) to the canonical schema.

    SkyLink returns each NOTAM as:
      {
        "raw": "!FAOR A1231/2026 ... 202604180400 202604180600",
        "notam_id": "A1231/2026",
        "type": "N" | "R" | "C",
        "location": "FAOR",
        "effective":  "YYYYMMDDHHMM",          # 12-digit
        "expiration": "YYYYMMDDHHMM" | "...EST" | "PERM",
        "body": "..."                           # NOTAM text without headers
      }
    """
    if not isinstance(item, dict):
        return None

    icao = (
        item.get("location")
        or item.get("icao")
        or item.get("airport_icao")
        or fallback_icao
        or ""
    ).strip().upper()

    notam_id = item.get("notam_id") or item.get("id") or item.get("ident") or ""

    type_raw = (item.get("type") or item.get("notam_type") or "").strip().upper()
    type_code = type_raw[0] if type_raw and type_raw[0] in ("N", "R", "C") else type_raw

    start = _to_iso(item.get("effective"))
    end_raw = item.get("expiration")
    if isinstance(end_raw, str) and end_raw.strip().upper() in ("PERM", "PERMANENT"):
        end = "PERM"
    else:
        end = _to_iso(end_raw)

    # Prefer `body` (NOTAM text without ident/header) over `raw` (full line including ID + dates)
    text = item.get("body") or item.get("raw") or item.get("text") or ""
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
    window_days: int = RECENT_WINDOW_DAYS,
) -> dict:
    """Fetch NOTAMs from SkyLink, one airport per request, capped concurrency.

    `window_days` (default 7) drives the operational-relevance filter: a NOTAM
    is kept if it is currently active OR its effective_start is within ±N days
    of now. This captures recently activated, currently active, and upcoming
    NOTAMs in one filter.
    """
    if SKYLINK_SUSPENDED:
        logging.warning("SkyLink calls suspended (SKYLINK_SUSPENDED=True) — returning empty payload")
        return {
            "error": "SkyLink calls suspended",
            "message": "SkyLink fetching is currently suspended via the SKYLINK_SUSPENDED kill switch in notams.py to conserve RapidAPI quota. Flip the constant to False to resume.",
        }
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
            # Keep if currently active OR effective_start is within ±window_days
            if not _passes_recency_filter(norm, window_days):
                continue
            key = (norm["airport_icao"], norm["notam_id"])
            if key in seen:
                continue
            seen.add(key)
            notams.append(norm)

    return _build_report(notams, codes, fetch_errors, source="skylink", window_days=window_days)


# ---------------------------------------------------------------------------
# ASECNA
# ---------------------------------------------------------------------------


def _asecna_strip_html(fragment: str) -> str:
    """Replace <BR> with newlines, remove all other tags, unescape HTML entities."""
    s = re.sub(r'<[Bb][Rr]\s*/?>', '\n', fragment)
    s = re.sub(r'<[^>]+>', '', s)
    return _html_unescape(s)


def _parse_asecna_page(html: str) -> list[str]:
    """Extract raw NOTAM text blocks from an ASECNA HTML response."""
    blocks = re.findall(
        r'<div\s+id=["\']notam["\'][^>]*>(.*?)</div>',
        html,
        re.IGNORECASE | re.DOTALL,
    )
    result = []
    for block in blocks:
        text = _asecna_strip_html(block)
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text).strip()
        if text:
            result.append(text)
    return result


def _normalize_asecna(raw_text: str, fallback_icao: str) -> dict | None:
    """Map a single ASECNA NOTAM text block to the canonical schema.

    ASECNA NOTAM structure (after HTML-stripping):
      GOOOYNYX
      (A0220/26 NOTAMR A1276/25
      Q)GOOO/QMAHG/IV/BO/A/000/999/1440N01704W 005
      A)GOBD B)2026-03-06 15:13:00  C)2026-06-02 23:59:00 EST
      E)GRASS CUTTING IN PROGRESS...
    """
    id_m = re.search(r'\(([A-Z]\d{4}/\d{2,4})\s+NOTAM([NRC])', raw_text)
    if not id_m:
        return None
    notam_id = id_m.group(1)
    type_code = id_m.group(2)

    # Q-code: second slash-delimited field, e.g. "GOOO/QMAHG/IV/..."
    q_m = re.search(r'\bQ\)(\S+)', raw_text)
    qcode = None
    if q_m:
        parts = q_m.group(1).split('/')
        if len(parts) >= 2 and parts[1].upper().startswith('Q'):
            qcode = parts[1].upper()

    # A) — affected aerodrome
    a_m = re.search(r'\bA\)\s*([A-Z]{4})\b', raw_text)
    icao = a_m.group(1) if a_m else fallback_icao.strip().upper()

    # B) — start datetime  "YYYY-MM-DD HH:MM:SS" (UTC)
    b_m = re.search(r'\bB\)\s*(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})', raw_text)
    start_iso = _to_iso(f"{b_m.group(1)}T{b_m.group(2)}+00:00") if b_m else ""

    # C) — end datetime; "0000-00-00 … PERM" means permanent
    c_m = re.search(r'\bC\)\s*(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})(\s+\S+)?', raw_text)
    if c_m:
        date_p, time_p = c_m.group(1), c_m.group(2)
        suffix = (c_m.group(3) or "").strip().upper()
        if 'PERM' in suffix or date_p.startswith('0000'):
            end_iso = "PERM"
        else:
            end_iso = _to_iso(f"{date_p}T{time_p}+00:00")
    else:
        end_iso = ""

    # E) — free-text body (may be multi-line); strip trailing ")" from NOTAM envelope
    e_m = re.search(r'\bE\)\s*(.+?)(?:\)\s*$|\Z)', raw_text, re.DOTALL)
    if e_m:
        body = re.sub(r'\s+', ' ', e_m.group(1)).strip()
    else:
        body = ""

    is_active, is_upcoming = _compute_active_upcoming(start_iso, end_iso)
    return {
        "airport_icao": icao,
        "notam_id": notam_id,
        "type": type_code,
        "effective_start": start_iso,
        "effective_end": end_iso,
        "text": body,
        "category": categorize_notam(body, qcode),
        "is_active": is_active,
        "is_upcoming": is_upcoming,
        "source": "asecna",
    }


async def _fetch_asecna_one(
    client: httpx.AsyncClient,
    icao: str,
) -> tuple[str, list[str] | Exception]:
    """POST to ASECNA portal for one ICAO code; return parsed text blocks."""
    data = {
        "qr_bni":      "TOUT",
        "qr_qfir":     "TOUT",
        "qr_firx":     icao,
        "qr_num":      "",
        "qr_perm":     "",
        "qr_datearrd": "",
        "qr_datearrf": "",
        "qr_datevald": "",
        "qr_datevalf": "",
        "qr_texte":    "",
        "qr_maxrows":  str(ASECNA_MAX_ROWS),
        "submit":      "Consulter",
    }
    try:
        resp = await client.post(ASECNA_URL, data=data)
        resp.raise_for_status()
        return icao, _parse_asecna_page(resp.text)
    except Exception as e:
        return icao, e


async def fetch_asecna_notams(
    icao_codes: Iterable[str] | None = None,
    window_days: int = RECENT_WINDOW_DAYS,
) -> dict:
    """Fetch NOTAMs from the ASECNA public portal (no API key required).

    Covers airports in ASECNA member states (18 francophone African countries +
    Madagascar). Requests are sequential with light pacing. Per-airport failures
    are recorded under `fetch_errors` rather than aborting the run.

    Args:
        icao_codes: ICAO codes to query. Defaults to ASECNA_AIRPORTS (~18 airports).
        window_days: Keep NOTAMs that are currently active OR whose effective_start
            is within ±N days of now (default 7).
    """
    codes = [c.strip().upper() for c in (icao_codes or ASECNA_AIRPORTS) if c and c.strip()]
    notams: list[dict] = []
    fetch_errors: list[dict] = []
    seen: set[tuple[str, str]] = set()

    headers = {"User-Agent": "14N-API-INT/1.0"}
    async with httpx.AsyncClient(timeout=30, headers=headers) as client:
        for i, icao in enumerate(codes):
            if i > 0:
                await asyncio.sleep(ASECNA_DELAY_S)
            icao_out, outcome = await _fetch_asecna_one(client, icao)
            if isinstance(outcome, Exception):
                fetch_errors.append({"icao": icao_out, "error": f"{type(outcome).__name__}: {outcome}"})
                continue
            for raw_text in outcome:
                norm = _normalize_asecna(raw_text, fallback_icao=icao_out)
                if not norm or not norm["airport_icao"]:
                    continue
                if not _passes_recency_filter(norm, window_days):
                    continue
                key = (norm["airport_icao"], norm["notam_id"])
                if key in seen:
                    continue
                seen.add(key)
                notams.append(norm)

    return _build_report(notams, codes, fetch_errors, source="asecna", window_days=window_days)


# ---------------------------------------------------------------------------
# Report shaping
# ---------------------------------------------------------------------------

def _build_report(
    notams: list[dict],
    airports_queried: list[str],
    fetch_errors: list[dict],
    source: str,
    window_days: int = RECENT_WINDOW_DAYS,
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
        "recency_window_days": window_days,
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
