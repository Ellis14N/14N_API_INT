import os
import time

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

ACLED_API_URL = "https://acleddata.com/api/acled/read"
ACLED_TOKEN_URL = "https://acleddata.com/oauth/token"
ACLED_USERNAME = os.getenv("ACLED_USERNAME", "")
ACLED_PASSWORD = os.getenv("ACLED_PASSWORD", "")

mcp = FastMCP(
    "14N API Integration",
    host="0.0.0.0",
    port=int(os.getenv("PORT", "8000")),
)

_token: str = ""
_token_expiry: float = 0.0


async def get_token() -> str:
    global _token, _token_expiry
    if _token and time.time() < _token_expiry:
        return _token
    async with httpx.AsyncClient(timeout=30) as client:
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
        _token_expiry = time.time() + 23 * 3600  # refresh 1 hour before expiry
    return _token


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
        event_type: Optional event type filter (e.g. "Battles",
                    "Protests", "Riots", "Violence against civilians",
                    "Explosions/Remote violence", "Strategic developments").
        limit: Maximum number of records to return (default 5000).
    """
    token = await get_token()
    params: dict[str, str | int] = {
        "country": country,
        "event_date": f"{date_from}|{date_to}",
        "event_date_where": "BETWEEN",
        "limit": limit,
    }
    if event_type:
        params["event_type"] = event_type

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(
            ACLED_API_URL,
            params=params,
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()
        return resp.json()


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
