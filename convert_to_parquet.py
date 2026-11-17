"""Convert raw files in S3 (raw/) into typed Parquet files in S3 (parquet/).

Reads : Users/Shubham M/raw/<endpoint>/date=YYYY-MM-DD/<endpoint>_YYYY-MM-DD.<ext>
Writes: Users/Shubham M/parquet/<endpoint>/date=YYYY-MM-DD/<endpoint>_YYYY-MM-DD.parquet
The raw files are only ever read, never modified.

Setup (PowerShell):
    python -m pip install requests boto3 pyarrow
    $env:VAULT_ADDR = "http://127.0.0.1:8200"
    $env:VAULT_TOKEN = Read-Host "vault token"

Run:
    python convert_to_parquet.py 2026-10-15              # one date
    python convert_to_parquet.py 2026-10-01 2026-10-15   # inclusive range
    python convert_to_parquet.py 2026-10-15 --show       # also print schema + first rows
Products have no date filter, so every products snapshot found under raw/products/ is converted.
"""
from __future__ import annotations

import csv
import io
import json
import os
import sys
from datetime import date as date_type, datetime, timedelta, timezone
from decimal import Decimal

import boto3
import pyarrow as pa
import pyarrow.parquet as pq
import requests
from botocore.config import Config
from botocore.exceptions import ClientError

# ---------- configuration (not secret) ----------
BUCKET = os.environ.get("S3_BUCKET", "cartwell-usecase-data")
BASE = os.environ.get("S3_BASE", "Users/Shubham M").strip("/")
RAW = f"{BASE}/raw"
OUT = f"{BASE}/parquet"
VAULT_ADDR = os.environ.get("VAULT_ADDR")
VAULT_TOKEN = os.environ.get("VAULT_TOKEN")

if not VAULT_ADDR or not VAULT_TOKEN:
    raise SystemExit("Set VAULT_ADDR and VAULT_TOKEN first (see the top of this file).")

SHOW = "--show" in sys.argv
RUN_TS = datetime.now(timezone.utc)

# ---------- Vault + S3 ----------
def get_secret(path: str) -> dict:
    resp = requests.get(
        f"{VAULT_ADDR}/v1/secret/data/{path}",
        headers={"X-Vault-Token": VAULT_TOKEN},
        timeout=10,
    )
    if resp.status_code != 200:
        raise SystemExit(f"Vault read failed for {path}: {resp.status_code} {resp.text}")
    return resp.json()["data"]["data"]


aws = get_secret("cartwell/aws")
s3 = boto3.client(
    "s3",
    aws_access_key_id=aws["access_key_id"].strip(),
    aws_secret_access_key=aws["secret_access_key"].strip(),
    region_name=aws.get("region", "us-east-1"),
    config=Config(retries={"max_attempts": 10, "mode": "standard"},
                  connect_timeout=10, read_timeout=60),
)

# ---------- schemas: every column's type is a decision made on purpose ----------
TS = pa.timestamp("us", tz="UTC")
MONEY = pa.decimal128(12, 2)  # exact decimals for money, never floats
META = [("_source_file", pa.string()), ("_ingested_at", TS)]

SCHEMAS = {
    "orders": pa.schema([
        ("order_id", pa.string()), ("order_ts", TS), ("customer_id", pa.string()),
        ("order_status", pa.string()), ("line_number", pa.int32()),
        ("product_id", pa.string()), ("quantity", pa.int32()),
        ("unit_price", MONEY), ("line_total", MONEY), ("currency", pa.string()),
    ] + META),
    "customers": pa.schema([
        ("customer_id", pa.string()), ("first_name", pa.string()),
        ("last_name", pa.string()), ("email", pa.string()), ("phone", pa.string()),
        ("signup_at", TS),
        ("address", pa.struct([("line1", pa.string()), ("city", pa.string()),
                               ("state", pa.string()), ("pincode", pa.string())])),
        ("marketing_opt_in", pa.bool_()),
    ] + META),
    "transactions": pa.schema([
        ("transaction_id", pa.string()), ("order_id", pa.string()),
        ("txn_ts", TS), ("type", pa.string()), ("method", pa.string()),
        ("amount", MONEY), ("currency", pa.string()), ("status", pa.string()),
        ("failure_reason", pa.string()),  # nullable
    ] + META),
    "products": pa.schema([
        ("product_id", pa.string()), ("name", pa.string()),
        ("category", pa.string()), ("price", MONEY), ("currency", pa.string()),
    ] + META),
}


# ---------- parsers: raw bytes -> (list of typed rows, expected row count or None) ----------
def ts(v: str) -> datetime:
    return datetime.fromisoformat(v.replace("Z", "+00:00"))


def money(v) -> Decimal:
    return Decimal(str(v)).quantize(Decimal("0.01"))


def parse_orders(raw: bytes):
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    rows = [{
        "order_id": r["order_id"], "order_ts": ts(r["order_ts"]),
        "customer_id": r["customer_id"], "order_status": r["order_status"],
        "line_number": int(r["line_number"]), "product_id": r["product_id"],
        "quantity": int(r["quantity"]), "unit_price": money(r["unit_price"]),
        "line_total": money(r["line_total"]), "currency": r["currency"],
    } for r in reader]
    return rows, None


def parse_customers(raw: bytes):
    payload = json.loads(raw)
    rows = [{**c, "signup_at": ts(c["signup_at"])} for c in payload["customers"]]
    return rows, payload["count"]


def parse_transactions(raw: bytes):
    rows = []
    for line in raw.decode("utf-8-sig").splitlines():
        if not line.strip():
            continue
        t = json.loads(line)
        rows.append({**t, "txn_ts": ts(t["txn_ts"]), "amount": money(t["amount"])})
    return rows, None


def parse_products(raw: bytes):
    payload = json.loads(raw)
    rows = [{**p, "price": money(p["price"])} for p in payload["products"]]
    return rows, payload["count"]


PARSERS = {
    "orders": parse_orders, "customers": parse_customers,
    "transactions": parse_transactions, "products": parse_products,
}
EXT = {"orders": "csv", "customers": "json", "transactions": "ndjson", "products": "json"}


# ---------- convert one file ----------
def convert(endpoint: str, raw_key: str, out_key: str) -> None:
    try:
        raw = s3.get_object(Bucket=BUCKET, Key=raw_key)["Body"].read()
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            raise SystemExit(f"Raw file missing: {raw_key}. Run the extractor for that date first.")
        raise

    rows, expected = PARSERS[endpoint](raw)
    if expected is not None and expected != len(rows):
        raise RuntimeError(f"{raw_key}: source says {expected} rows, parsed {len(rows)}")

    for r in rows:  # lineage columns: where did this row come from, and when
        r["_source_file"] = raw_key
        r["_ingested_at"] = RUN_TS

    table = pa.Table.from_pylist(rows, schema=SCHEMAS[endpoint])  # fails loudly on a type mismatch
    buf = io.BytesIO()
    pq.write_table(table, buf, compression="snappy")
    body = buf.getvalue()

    s3.put_object(Bucket=BUCKET, Key=out_key, Body=body)
    remote = s3.head_object(Bucket=BUCKET, Key=out_key)["ContentLength"]
    if remote != len(body):
        raise RuntimeError(f"size mismatch for {out_key}: sent {len(body)}, S3 has {remote}")

    note = "  (empty day, schema only)" if table.num_rows == 0 else ""
    print(f"  {endpoint}: {len(raw)} raw bytes, {table.num_rows} rows -> "
          f"{len(body)} parquet bytes -> s3://{BUCKET}/{out_key}{note}")
    if SHOW:
        print(table.schema)
        for row in table.slice(0, 2).to_pylist():
            print("   ", row)


# ---------- orchestration ----------
def date_range(start: str, end: str) -> list[str]:
    d0, d1 = date_type.fromisoformat(start), date_type.fromisoformat(end)
    if d1 < d0:
        raise SystemExit("End date is before start date.")
    return [(d0 + timedelta(days=i)).isoformat() for i in range((d1 - d0).days + 1)]


def products_snapshots() -> list[str]:
    keys = []
    prefix = f"{RAW}/products/"
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=BUCKET, Prefix=prefix):
        keys += [o["Key"] for o in page.get("Contents", []) if o["Key"].endswith(".json")]
    return keys


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) == 0:
        dates = [(datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")]
    elif len(args) == 1:
        dates = [args[0]]
    else:
        dates = date_range(args[0], args[1])

    for d in dates:
        print(f"Converting date={d}")
        for endpoint in ("customers", "orders", "transactions"):
            convert(endpoint,
                    f"{RAW}/{endpoint}/date={d}/{endpoint}_{d}.{EXT[endpoint]}",
                    f"{OUT}/{endpoint}/date={d}/{endpoint}_{d}.parquet")

    print("Converting products snapshots")
    for raw_key in products_snapshots():
        snap = raw_key.split("date=")[1].split("/")[0]
        convert("products", raw_key, f"{OUT}/products/date={snap}/products_{snap}.parquet")
    print("Done.")


if __name__ == "__main__":
    main()