"""Complete extractor: Vault -> Cartwell API -> local raw files -> S3.

No hvac needed: Vault is read over plain HTTP with `requests`.
All secrets come from Vault; nothing secret lives in code or files.

Setup (PowerShell):
    python -m pip install requests boto3
    $env:VAULT_ADDR = "http://127.0.0.1:8200"
    $env:VAULT_TOKEN = Read-Host "vault token"

Run:
    python extract_pipeline.py 2026-10-15     # or no argument = yesterday UTC

Expected Vault entries (KV v2 engine mounted at secret/):
    secret/cartwell/api  ->  token
    secret/cartwell/aws  ->  access_key_id, secret_access_key, region
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import boto3
from botocore.config import Config
import requests

# ---------- configuration (not secret) ----------
API_URL = os.environ.get("CARTWELL_URL", "http://127.0.0.1:8000")
BUCKET = os.environ.get("S3_BUCKET", "cartwell-usecase-data")
VAULT_ADDR = os.environ.get("VAULT_ADDR")
VAULT_TOKEN = os.environ.get("VAULT_TOKEN")
VAULT_MOUNT = "secret"  # the KV v2 engine path

if not VAULT_ADDR or not VAULT_TOKEN:
    raise SystemExit("Set VAULT_ADDR and VAULT_TOKEN first (see the setup lines at the top).")

# endpoint -> (needs a date?, file extension matching its real format)
ENDPOINTS = {
    "products": (False, "json"),
    "customers": (True, "json"),
    "orders": (True, "csv"),
    "transactions": (True, "ndjson"),
}


# ---------- Vault ----------
def get_secret(path: str) -> dict:
    # KV v2 read endpoint: /v1/<mount>/data/<path>
    resp = requests.get(
        f"{VAULT_ADDR}/v1/{VAULT_MOUNT}/data/{path}",
        headers={"X-Vault-Token": VAULT_TOKEN},
        timeout=10,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Vault read failed for {path}: {resp.status_code} {resp.text}")
    return resp.json()["data"]["data"]  # outer 'data' = envelope, inner = your keys


api_secret = get_secret("cartwell/api")
aws_secret = get_secret("cartwell/aws")

API_HEADERS = {"Authorization": f"Bearer {api_secret['token']}"}
s3 = boto3.client(
    "s3",
    aws_access_key_id=aws_secret["access_key_id"].strip(),
    aws_secret_access_key=aws_secret["secret_access_key"].strip(),
    region_name=aws_secret.get("region", "us-east-1"),
)


# ---------- extract ----------
def yesterday_utc() -> str:
    # The API publishes a day only after it ends in UTC, so never use local time.
    return (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")


def fetch(endpoint: str, date: str | None) -> bytes:
    params = {"date": date} if date else None
    resp = requests.get(
        f"{API_URL}/v1/{endpoint}", headers=API_HEADERS, params=params, timeout=30
    )
    if resp.status_code != 200:
        raise RuntimeError(f"{endpoint} failed: {resp.status_code} {resp.text}")
    return resp.content  # raw bytes, untouched


# ---------- load ----------
def save_local(path: Path, body: bytes) -> None:
    # Temp name then rename: a file is either complete or absent.
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(body)
    tmp.replace(path)


def upload_and_verify(path: Path, key: str) -> None:
    s3.upload_file(str(path), BUCKET, key)
    remote_size = s3.head_object(Bucket=BUCKET, Key=key)["ContentLength"]
    local_size = path.stat().st_size
    if remote_size != local_size:
        raise RuntimeError(f"size mismatch for {key}: local {local_size}, S3 {remote_size}")


def main() -> None:
    date = sys.argv[1] if len(sys.argv) > 1 else yesterday_utc()
    print(f"Extracting for date={date}")

    for endpoint, (needs_date, ext) in ENDPOINTS.items():
        body = fetch(endpoint, date if needs_date else None)
        local_path = Path("raw") / endpoint / f"date={date}" / f"{endpoint}.{ext}"
        save_local(local_path, body)
        key = local_path.as_posix()  # same path locally and in S3
        upload_and_verify(local_path, key)
        print(f"  {endpoint}: {len(body)} bytes -> s3://{BUCKET}/{key}")

    print("Done.")


if __name__ == "__main__":
    main()