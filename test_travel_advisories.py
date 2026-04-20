#!/usr/bin/env python3
"""Quick test runner for travel_advisories.fetch_all_advisories"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from travel_advisories import fetch_all_advisories

COUNTRIES = [
    "Cote d'Ivoire",
    "Democratic Republic of the Congo",
    "Republic of the Congo",
    "Kenya",
]

async def main():
    for c in COUNTRIES:
        print(f"\n--- {c} ---")
        try:
            res = await fetch_all_advisories(c)
            # Extract state and dfat levels if present
            state = res.get("us_state_dept", {})
            dfat = res.get("aus_dfat", {})
            def level_text(x):
                if not x or isinstance(x, dict) and x.get("error"):
                    return x.get("error") if isinstance(x, dict) else str(x)
                return f"{x.get('level')} - {x.get('level_text')}"
            print("US State Dept:", level_text(state))
            print("Australia DFAT:", level_text(dfat))
        except Exception as e:
            print("Error:", e)

if __name__ == '__main__':
    asyncio.run(main())