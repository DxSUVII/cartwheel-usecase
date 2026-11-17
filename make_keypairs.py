"""Generate one RSA key pair per Snowflake service user: Terraform, loader (Python), dbt.

Private keys (.p8) go to a folder OUTSIDE your project, so they can never be committed to Git.
Public keys go into set_public_keys.sql, which you run in Snowsight. Public keys are not secret.
The script never prints a private key and refuses to overwrite keys that already exist.

    python -m pip install cryptography
    python make_keypairs.py                       # keys go to C:\\Users\\<you>\\cartwell-keys
    python make_keypairs.py D:\\some\\other\\folder
"""
from __future__ import annotations

import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

USERS = {
    "tf": "CARTWELL_TF_USER",
    "loader": "CARTWELL_LOADER_USER",
    "dbt": "CARTWELL_DBT_USER",
}

out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "cartwell-keys"
out_dir.mkdir(parents=True, exist_ok=True)

already = [f"{name}_rsa_key.p8" for name in USERS if (out_dir / f"{name}_rsa_key.p8").exists()]
if already:
    raise SystemExit(f"Refusing to overwrite existing keys in {out_dir}: {', '.join(already)}")

sql_lines = []
for short_name, snowflake_user in USERS.items():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    private_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()

    # Snowflake wants the public key body only: no BEGIN/END lines, no line breaks.
    public_body = "".join(public_pem.strip().splitlines()[1:-1])

    (out_dir / f"{short_name}_rsa_key.p8").write_bytes(private_pem)
    sql_lines.append(f"ALTER USER {snowflake_user} SET RSA_PUBLIC_KEY = '{public_body}';")

(out_dir / "set_public_keys.sql").write_text("\n".join(sql_lines) + "\n")

print(f"Created in {out_dir}:")
for short_name in USERS:
    print(f"  {short_name}_rsa_key.p8   (private key: keep secret, never commit)")
print("  set_public_keys.sql        (public keys: run this in Snowsight)")
