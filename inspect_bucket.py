"""Inspect the S3 bucket: who am I, can I reach it, what folders and files exist.
Credentials come from Vault (secret/cartwell/aws). Read-only: it never writes or deletes.

Setup (PowerShell):
    $env:VAULT_ADDR = "http://127.0.0.1:8200"
    $env:VAULT_TOKEN = Read-Host "vault token"

Usage:
    python inspect_bucket.py                      # top level of the bucket
    python inspect_bucket.py raw/                 # one level inside raw/
    python inspect_bucket.py raw/orders/          # drill down
    python inspect_bucket.py raw/ --all           # everything under raw/, every file
"""
from __future__ import annotations

import os
import sys

import boto3
import requests
from botocore.config import Config
from botocore.exceptions import ClientError, EndpointConnectionError

BUCKET = os.environ.get("S3_BUCKET", "cartwell-usecase-data")
VAULT_ADDR = os.environ.get("VAULT_ADDR")
VAULT_TOKEN = os.environ.get("VAULT_TOKEN")

if not VAULT_ADDR or not VAULT_TOKEN:
    raise SystemExit("Set VAULT_ADDR and VAULT_TOKEN first (see the top of this file).")


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
creds = dict(
    aws_access_key_id=aws["access_key_id"].strip(),
    aws_secret_access_key=aws["secret_access_key"].strip(),
    region_name=aws.get("region", "us-east-1"),
)
cfg = Config(retries={"max_attempts": 10, "mode": "standard"}, connect_timeout=10, read_timeout=60)
s3 = boto3.client("s3", config=cfg, **creds)
sts = boto3.client("sts", config=cfg, **creds)


def explain(err: ClientError, action: str) -> None:
    code = err.response["Error"]["Code"]
    hints = {
        "AccessDenied": "The key is valid but not allowed to do this. Ask the bucket owner to add the permission.",
        "InvalidAccessKeyId": "The access key ID is wrong or deleted.",
        "SignatureDoesNotMatch": "The secret key does not match the key ID (typo, or a pair mismatch).",
        "NoSuchBucket": "The bucket name is wrong or in another account.",
        "403": "Forbidden: the key has no permission on this bucket.",
        "404": "Bucket not found.",
    }
    print(f"  FAILED ({action}): {code}. {hints.get(code, err.response['Error'].get('Message', ''))}")


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    show_all = "--all" in sys.argv
    prefix = args[0] if args else ""

    # 1) Who am I? (needs no special permission)
    print("1) Identity")
    try:
        who = sts.get_caller_identity()
        print(f"  Account: {who['Account']}")
        print(f"  ARN:     {who['Arn']}")
    except ClientError as e:
        explain(e, "get_caller_identity")
        return

    # 2) Can I reach the bucket?
    print(f"\n2) Bucket access: {BUCKET}")
    try:
        s3.head_bucket(Bucket=BUCKET)
        print("  OK, bucket reachable.")
    except ClientError as e:
        explain(e, "head_bucket")
        return
    except EndpointConnectionError:
        print("  FAILED: cannot reach S3 (network, VPN, proxy or firewall).")
        return

    # 3) Browse. Delimiter="/" makes S3 group keys into 'folders' (common prefixes).
    #    S3 has no real folders: a 'folder' is just a shared start of the key names.
    print(f"\n3) Contents of s3://{BUCKET}/{prefix}" + ("  (recursive)" if show_all else ""))
    kwargs = {"Bucket": BUCKET, "Prefix": prefix}
    if not show_all:
        kwargs["Delimiter"] = "/"

    folders, files, total = [], [], 0
    try:
        for page in s3.get_paginator("list_objects_v2").paginate(**kwargs):
            folders += [p["Prefix"] for p in page.get("CommonPrefixes", [])]
            for obj in page.get("Contents", []):
                files.append(obj)
                total += obj["Size"]
    except ClientError as e:
        explain(e, "list_objects_v2")
        return

    for f in folders:
        print(f"  [folder] {f}")
    for obj in files:
        print(f"  {obj['Size']:>10}  {obj['LastModified']:%Y-%m-%d %H:%M:%S}  {obj['Key']}")

    print(f"\n  {len(folders)} folder(s), {len(files)} file(s), {total} bytes")
    if not folders and not files:
        print("  Nothing under this prefix (it may be empty, or the prefix is wrong).")
    elif folders:
        print("  Tip: run again with one of the folders above to go one level deeper.")


if __name__ == "__main__":
    main()