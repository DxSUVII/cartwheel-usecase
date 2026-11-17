"""Test the Snowflake connection (key-pair auth). Credentials come from Vault.

Vault entry needed (KV v2, secret/):  cartwell/snowflake
    account            e.g. myorg-myaccount           (NOT the full URL)
    user               the Snowflake user the public key is attached to
    role               e.g. SYSADMIN or the role you were given
    warehouse          e.g. COMPUTE_WH
    private_key_b64    base64 of the private key file (single line, see steps)
    private_key_passphrase   only if the key is encrypted (leave out otherwise)

Setup (PowerShell):
    python -m pip install snowflake-connector-python cryptography requests
    $env:VAULT_ADDR = "http://127.0.0.1:8200"
    $env:VAULT_TOKEN = Read-Host "vault token"
    python test_snowflake.py
"""
from __future__ import annotations

import base64
import os

import requests
import snowflake.connector
from cryptography.hazmat.primitives import serialization

VAULT_ADDR = os.environ.get("VAULT_ADDR")
VAULT_TOKEN = os.environ.get("VAULT_TOKEN")
if not VAULT_ADDR or not VAULT_TOKEN:
    raise SystemExit("Set VAULT_ADDR and VAULT_TOKEN first.")


def get_secret(path: str) -> dict:
    resp = requests.get(
        f"{VAULT_ADDR}/v1/secret/data/{path}",
        headers={"X-Vault-Token": VAULT_TOKEN},
        timeout=10,
    )
    if resp.status_code != 200:
        raise SystemExit(f"Vault read failed for {path}: {resp.status_code} {resp.text}")
    return resp.json()["data"]["data"]


sf = get_secret("cartwell/snowflake")

# The connector wants the private key as unencrypted DER bytes.
pem = base64.b64decode(sf["private_key_b64"])
passphrase = sf.get("private_key_passphrase") or None
private_key = serialization.load_pem_private_key(
    pem, password=passphrase.encode() if passphrase else None
)
key_der = private_key.private_bytes(
    encoding=serialization.Encoding.DER,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
)

conn = snowflake.connector.connect(
    account=sf["account"].strip(),
    user=sf["user"].strip(),
    private_key=key_der,
    role=sf.get("role"),
    warehouse=sf.get("warehouse"),
    login_timeout=30,
)

try:
    cur = conn.cursor()
    cur.execute(
        "select current_account(), current_region(), current_user(), "
        "current_role(), current_warehouse(), current_version()"
    )
    labels = ["account", "region", "user", "role", "warehouse", "version"]
    for label, value in zip(labels, cur.fetchone()):
        print(f"  {label:<10} {value}")

    cur.execute("show databases")
    names = [row[1] for row in cur.fetchall()]
    print(f"\n  databases visible to this role: {names}")
finally:
    conn.close()
print("\nConnection OK.")