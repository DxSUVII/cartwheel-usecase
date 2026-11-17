"""Step 1: connect to the Cartwell API and save RAW responses to disk.
S3 upload comes next; for now the local folder plays the role of the raw zone.

Usage:
    export CARTWELL_TOKEN="paste-token-here"
    python extract.py                  # defaults to yesterday (UTC)
    python extract.py 2026-10-15       # a specific date
"""
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

BASE_URL = os.environ.get("CARTWELL_URL", "http://127.0.0.1:8000")
TOKEN = os.environ["CARTWELL_TOKEN"]  # crashes loudly if missing; no hardcoding
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

# endpoint -> (needs_date, file extension matching its real format)
ENDPOINTS = {
    "products": (False, "json"),
    "customers": (True, "json"),
    "orders": (True, "csv"),
    "transactions": (True, "ndjson"),
}


def yesterday_utc() -> str:
    # The API publishes a day only after it ends in UTC, so never use local time.
    return (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")


def fetch(endpoint: str, date: str | None) -> bytes:
    params = {"date": date} if date else None
    resp = requests.get(
        f"{BASE_URL}/v1/{endpoint}", headers=HEADERS, params=params, timeout=30
    )
    if resp.status_code != 200:
        # The API returns JSON errors, so the message tells you what went wrong.
        raise RuntimeError(f"{endpoint} failed: {resp.status_code} {resp.text}")
    return resp.content  # raw bytes, untouched: "data in its true form"


def main() -> None:
    date = sys.argv[1] if len(sys.argv) > 1 else yesterday_utc()
    print(f"Extracting for date={date}")

    for endpoint, (needs_date, ext) in ENDPOINTS.items():
        body = fetch(endpoint, date if needs_date else None)
        folder = Path("raw") / endpoint / f"date={date}"
        folder.mkdir(parents=True, exist_ok=True)
        out = folder / f"{endpoint}.{ext}"
        out.write_bytes(body)
        print(f"  {endpoint}: {len(body)} bytes -> {out}")


if __name__ == "__main__":
    main()