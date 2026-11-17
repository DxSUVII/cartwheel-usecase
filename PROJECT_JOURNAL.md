# Cartwell Project Journal

A running record of project goals, decisions, changes, and verification. Add a dated entry whenever a meaningful step is completed so the reasoning is easy to find later.

> **Note:** Earlier results below are recorded from the project notes provided by the owner. They have not all been re-run in this workspace.

## Project at a glance

Cartwell is an e-commerce data engineering project. The source API provides products, customers, orders, and transactions in JSON, CSV, and NDJSON formats. The project includes Python extraction scripts, S3 data, and Terraform configuration for Snowflake.

Current repository references:

- [Project overview](./README.md)
- [Cartwell API documentation](./cartwell_api_docs.md)
- [Terraform Snowflake configuration](./terraform-snowflake/)
- [S3 bucket inspection script](./inspect_bucket.py)

## 2026-11-17 — Notes captured from prior project work

### Storage integration update

**Goal**  
Allow Snowflake to access the new Cartwell dataset in S3.

**What changed**  
The storage integration's allowed location was updated to:

```text
s3://cartwell-usecase-data/cartwell-usecase-dataset/raw/cartwell/
```

The previous location was reported as:

```text
s3://cartwell-usecase-data/Users/Shubham M/parquet/
```

**Why**  
The project moved from the old Parquet location to the prepared Cartwell raw dataset.

**Result reported**  
Snowflake was expected to access the new data. The verification query used was:

```sql
LIST @RAW_CARTWELL_STAGE;
```

### Terraform migration to the RAW architecture

**Goal**  
Replace the old Parquet-oriented design with the new RAW architecture.

**Changes reported**

- Removed the old Parquet stage, file format, and tables.
- Added the `LANDING` schema, `RAW` schema, JSON and CSV file formats, and six RAW tables.

**Why**  
The new requirement is one row per source record, rather than loading pre-typed Parquet tables.

**Result reported**  
Terraform apply completed successfully.

**Current configuration reference**  
The Terraform files in this repository define `LANDING.JSON_FILES` and six `RAW` tables: `CUSTOMERS`, `CUSTOMER_UPDATES`, `PRODUCTS`, `ORDERS`, `TRANSACTIONS`, and `PRICE_CHANGES`. The RAW records use a `VARIANT` `RECORD` column with source-file and load metadata.

### JSON loading decision

**Question**  
Should a full JSON file be stored in RAW, or should its records be flattened first?

**Decision**  
Load the JSON file into LANDING, then flatten its array so each source record becomes one row in RAW.

**Why**  
Some files contain a wrapper object such as `{ "count": 4, "customers": [...] }`. The target RAW design requires one row per source record.

**Flow**

```text
S3
  -> LANDING.JSON_FILES
  -> FLATTEN()
  -> RAW table (one row per source record)
```

### Data availability validation

**Goal**  
Check that source files exist for all endpoints.

**Query used**

```sql
LIST @RAW_CARTWELL_STAGE;
```

**Result reported**  
The listing contained files for `customers`, `customer_updates`, `orders`, `price_changes`, `products`, and `transactions`, with 43 files dated 2026-10-01 through 2026-11-12.

**Conclusion reported**  
The source data was complete through 2026-11-12 at the time of that check. Re-run the listing before relying on this as the current status.

### Why LANDING exists

**Question**  
Why not load wrapped JSON directly into RAW?

**Answer**  
The files can contain a wrapper object and an array of records. LANDING preserves the original file contents first; flattening then produces the required one-row-per-record RAW shape.

### Repository and dbt Cloud preparation

**Goal**  
Prepare a GitHub repository for dbt Cloud.

**Planned structure**

```text
cartwell-dbt/
  transform/   # dbt project
  airflow/     # possible future Stage 7 work
  analysis/
```

**Why `transform/`**  
The project notes say dbt Cloud should use `transform` as the project subdirectory.

**Planned work**

- Create a private GitHub repository named `cartwell-dbt`.
- Add an appropriate `.gitignore`.
- Add `transform/README.md`.
- Connect the repository to dbt Cloud.

**Open question**  
Should the GitHub repository live in a personal account or a company/organization account? See [Next Steps](./NEXT_STEPS.md).

## Entry template

Copy this for each significant change:

```markdown
## YYYY-MM-DD — Short title

### Goal
What were you trying to accomplish?

### What changed
What commands, files, or settings changed? Do not include passwords, tokens, private keys, or other secrets.

### Why
What requirement or problem motivated the change?

### Result
What happened? Include the exact validation command and outcome when applicable.

### Follow-up
Anything still to do, verify, or ask?
```
