import os

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

ACLED_API_URL = "https://api.acleddata.com/acled/read"
ACLED_API_KEY = os.getenv("ACLED_API_KEY", "")
ACLED_EMAIL = os.getenv("ACLED_EMAIL", "")

mcp = FastMCP(
    "14N API Integration",
    host="0.0.0.0",
    port=int(os.getenv("PORT", "8000")),
)


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
    params: dict[str, str | int] = {
        "key": ACLED_API_KEY,
        "email": ACLED_EMAIL,
        "country": country,
        "event_date": f"{date_from}|{date_to}",
        "event_date_where": "BETWEEN",
        "limit": limit,
    }
    if event_type:
        params["event_type"] = event_type

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(ACLED_API_URL, params=params)
        resp.raise_for_status()
        return resp.json()


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
