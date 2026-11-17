# Cartwell Data Engineering Project

This repository contains a small Cartwell shop-data pipeline: API extraction scripts, local raw samples, S3 integration code, and Terraform configuration for Snowflake. This README is the starting point; use the linked docs for endpoint details and the journal for the history behind decisions.

## Project map

| Path | Purpose |
|---|---|
| [cartwell_api_docs.md](./cartwell_api_docs.md) | API endpoints, formats, dates, and response examples |
| [cartwell_api.py](./cartwell_api.py) | Local Cartwell API server |
| [extract.py](./extract.py) | Fetch API responses and save them under local `raw/` |
| [extract_pipeline.py](./extract_pipeline.py) | Read API and AWS credentials from Vault, save local files, upload them to S3, and compare uploaded/local sizes |
| [extract_to_s3.py](./extract_to_s3.py) | Fetch API responses and upload them directly to S3 |
| [inspect_bucket.py](./inspect_bucket.py) | Read-only S3 bucket and prefix inspection using credentials from Vault |
| [terraform-snowflake/](./terraform-snowflake/) | Terraform resources for the Snowflake database, schemas, stage, file formats, and tables |
| [raw/](./raw/) | Local raw-data examples organized by endpoint and date |
| [PROJECT_JOURNAL.md](./PROJECT_JOURNAL.md) | Project goals, decisions, and verification notes |
| [NEXT_STEPS.md](./NEXT_STEPS.md) | Current checklist and next actions |

## Data flow and architecture

The project has two related workflows:

### API extraction workflow

The local API provides products, customers, orders, and transactions. The extractor scripts preserve the response bytes and use the source format: JSON, CSV, or NDJSON.

```text
Cartwell API
  -> extract.py
  -> local raw/<endpoint>/date=<date>/
```

Or, using the Vault-backed S3 scripts:

```text
Cartwell API + Vault credentials
  -> extract_pipeline.py or extract_to_s3.py
  -> S3
```

The scripts are alternatives with different behavior and destination layouts; check their headers and configuration before choosing one.

### Snowflake RAW workflow

The current Terraform configuration uses the prepared dataset path:

```text
s3://cartwell-usecase-data/cartwell-usecase-dataset/raw/cartwell/
```

It defines a `RAW` schema with six tables and a `LANDING` schema with `JSON_FILES`. The intended JSON flow is to load a whole wrapped JSON file into LANDING, flatten its records, then write one source record per row in RAW. CSV and JSON file formats and an external S3 stage are also defined in Terraform.

**Important:** `extract_to_s3.py` defaults to the `Users/Shubham M/raw` prefix, while `extract_pipeline.py` uploads keys under `raw/`. Those defaults are different from Terraform's prepared dataset path above. Do not assume either extractor populates the Terraform stage's location; confirm the destination and data layout before running or changing a pipeline.

The API extractor scripts currently list four endpoints, whereas the Snowflake RAW tables cover six data categories. The additional categories in the prepared dataset are `CUSTOMER_UPDATES` and `PRICE_CHANGES`.

## Running the local API extractor

Start the API server in one PowerShell terminal:

```powershell
python cartwell_api.py
```

In another terminal, set the API token and run an extraction:

```powershell
$env:CARTWELL_TOKEN = Read-Host "Cartwell API token"
python extract.py 2026-10-15
```

With no date argument, `extract.py` uses yesterday in UTC. The API server and endpoint behavior are documented in [cartwell_api_docs.md](./cartwell_api_docs.md).

## Vault-backed scripts

The S3 and Snowflake helper scripts expect `VAULT_ADDR` and `VAULT_TOKEN` in the environment. The extraction scripts read API/AWS credentials from Vault; the Snowflake connection check reads its key-pair credentials from Vault. See each script's header for the required Vault paths and setup.

Do not put passwords, API tokens, AWS keys, private keys, or Vault tokens in source code or Markdown files.

## Before publishing to GitHub

Review `.gitignore` before pushing. The current root `.gitignore` only excludes `.terraform-docker/`; make sure local `.env` files, Terraform state, private keys, and generated artifacts are excluded as appropriate. Never push credentials or state containing sensitive information.

## Project memory

- Read [PROJECT_JOURNAL.md](./PROJECT_JOURNAL.md) to understand what was changed and why.
- Read [NEXT_STEPS.md](./NEXT_STEPS.md) to resume the current work.
- Add a dated journal entry after a meaningful change, including the validation performed and any remaining follow-up.
