"""Extract from the Cartwell API and write raw files straight to S3 (no local copy).

Layout (one folder per endpoint, one sub-folder per date, date also in the file name):
    Users/Shubham M/raw/orders/date=2026-10-15/orders_2026-10-15.csv

Setup (PowerShell):
    python -m pip install requests boto3
    $env:VAULT_ADDR = "http://127.0.0.1:8200"
    $env:VAULT_TOKEN = Read-Host "vault token"

Run (API server must be running):
    python extract_to_s3.py 2026-10-15            # one date
    python extract_to_s3.py 2026-10-01 2026-10-15 # inclusive date range
    python extract_to_s3.py                        # yesterday (UTC)

Secrets in Vault (KV v2 at secret/):
    cartwell/api -> token
    cartwell/aws -> access_key_id, secret_access_key, region
"""
from __future__ import annotations

import os
import sys
from datetime import date as date_type, datetime, timedelta, timezone

import boto3
import requests
from botocore.config import Config

# ---------- configuration (not secret) ----------
API_URL = os.environ.get("CARTWELL_URL", "http://127.0.0.1:8000")
BUCKET = os.environ.get("S3_BUCKET", "cartwell-usecase-data")
PREFIX = os.environ.get("S3_PREFIX", "Users/Shubham M/raw").strip("/")
VAULT_ADDR = os.environ.get("VAULT_ADDR")
VAULT_TOKEN = os.environ.get("VAULT_TOKEN")

if not VAULT_ADDR or not VAULT_TOKEN:
    raise SystemExit("Set VAULT_ADDR and VAULT_TOKEN first (see the top of this file).")

# endpoint -> (needs a date?, file extension matching its real format)
ENDPOINTS = {
    "products": (False, "json"),
    "customers": (True, "json"),
    "orders": (True, "csv"),
    "transactions": (True, "ndjson"),
}


# ---------- Vault ----------
def get_secret(path: str) -> dict:
    resp = requests.get(
        f"{VAULT_ADDR}/v1/secret/data/{path}",
        headers={"X-Vault-Token": VAULT_TOKEN},
        timeout=10,
    )
    if resp.status_code != 200:
        raise SystemExit(f"Vault read failed for {path}: {resp.status_code} {resp.text}")
    return resp.json()["data"]["data"]


api_secret = get_secret("cartwell/api")
aws_secret = get_secret("cartwell/aws")

API_HEADERS = {"Authorization": f"Bearer {api_secret['token']}"}
s3 = boto3.client(
    "s3",
    aws_access_key_id=aws_secret["access_key_id"].strip(),
    aws_secret_access_key=aws_secret["secret_access_key"].strip(),
    region_name=aws_secret.get("region", "us-east-1"),
    config=Config(retries={"max_attempts": 10, "mode": "standard"},
                  connect_timeout=10, read_timeout=60),
)


# ---------- helpers ----------
def today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def yesterday_utc() -> str:
    return (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")


def date_range(start: str, end: str) -> list[str]:
    d0, d1 = date_type.fromisoformat(start), date_type.fromisoformat(end)
    if d1 < d0:
        raise SystemExit("End date is before start date.")
    return [(d0 + timedelta(days=i)).isoformat() for i in range((d1 - d0).days + 1)]


def make_key(endpoint: str, ext: str, partition_date: str) -> str:
    key = f"{PREFIX}/{endpoint}/date={partition_date}/{endpoint}_{partition_date}.{ext}"
    # Safety guard: this script may only ever write inside its own prefix.
    if not key.startswith(PREFIX + "/"):
        raise RuntimeError(f"refusing to write outside {PREFIX}/: {key}")
    return key


# ---------- extract ----------
def fetch(endpoint: str, date: str | None) -> bytes:
    params = {"date": date} if date else None
    resp = requests.get(
        f"{API_URL}/v1/{endpoint}", headers=API_HEADERS, params=params, timeout=30
    )
    if resp.status_code != 200:
        raise RuntimeError(f"{endpoint} failed: {resp.status_code} {resp.text}")
    return resp.content  # raw bytes, untouched


# ---------- load ----------
def upload_bytes(body: bytes, key: str) -> None:
    s3.put_object(Bucket=BUCKET, Key=key, Body=body)
    remote_size = s3.head_object(Bucket=BUCKET, Key=key)["ContentLength"]
    if remote_size != len(body):
        raise RuntimeError(f"size mismatch for {key}: sent {len(body)}, S3 has {remote_size}")


def run_one_date(date: str, include_products: bool) -> None:
    print(f"Extracting for date={date}")
    for endpoint, (needs_date, ext) in ENDPOINTS.items():
        if not needs_date:
            if not include_products:
                continue
            # Products has no date filter: it is a snapshot of 'now', so it is
            # filed under the day we took the snapshot, not the data date.
            body = fetch(endpoint, None)
            key = make_key(endpoint, ext, today_utc())
        else:
            body = fetch(endpoint, date)
            key = make_key(endpoint, ext, date)
        upload_bytes(body, key)
        print(f"  {endpoint}: {len(body)} bytes -> s3://{BUCKET}/{key}")


def main() -> None:
    args = sys.argv[1:]
    if len(args) == 0:
        dates = [yesterday_utc()]
    elif len(args) == 1:
        dates = [args[0]]
    else:
        dates = date_range(args[0], args[1])

    for i, d in enumerate(dates):
        run_one_date(d, include_products=(i == 0))  # catalog once per run
    print("Done.")


if __name__ == "__main__":
    main()