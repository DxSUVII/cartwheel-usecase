"""One-time helper: store the project's secrets in Vault.
Every secret is typed at a hidden prompt, so nothing lands in shell history,
environment variables or files.

    pip install hvac
    python store_secrets.py
"""
from getpass import getpass

import hvac

VAULT_ADDR = "http://127.0.0.1:8200"

client = hvac.Client(url=VAULT_ADDR, token=getpass("Vault token: "))
if not client.is_authenticated():
    raise SystemExit("Vault rejected the token, or Vault is sealed. Check `vault status`.")

# A non-dev Vault does not create the KV engine for you.
if "secret/" not in client.sys.list_mounted_secrets_engines()["data"]:
    client.sys.enable_secrets_engine(
        backend_type="kv", path="secret", options={"version": "2"}
    )
    print("Enabled KV v2 at secret/")

kv = client.secrets.kv.v2

kv.create_or_update_secret(
    path="cartwell/api",
    secret={"token": getpass("Cartwell API token: ")},
    mount_point="secret",
)
kv.create_or_update_secret(
    path="cartwell/aws",
    secret={
        "access_key_id": getpass("AWS access key id: "),
        "secret_access_key": getpass("AWS secret access key: "),
        "region": "us-east-1",
    },
    mount_point="secret",
)

# Verify by listing names only; never print the values.
print("Stored:", client.secrets.kv.v2.list_secrets(path="cartwell", mount_point="secret")["data"]["keys"])