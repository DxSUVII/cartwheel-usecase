# Cartwell — Status and Next Steps

Use this page as a quick restart point before a work session or standup. Check off an item only after it is actually completed.

## Current focus: GitHub and dbt Cloud

### First decision

- [ ] Decide whether `cartwell-dbt` belongs in a personal GitHub account or a company/organization account.

### After the account is chosen

- [ ] Create a **private** GitHub repository named `cartwell-dbt`.
- [ ] Add a `.gitignore` suitable for the planned Python/dbt work.
- [ ] Create `transform/README.md` and initialize the dbt project in `transform/`.
- [ ] Connect the repository to dbt Cloud and set the project subdirectory to `transform`.
- [ ] Record the setup and verification results in [PROJECT_JOURNAL.md](./PROJECT_JOURNAL.md).

## Project facts to keep in mind

- The data source is the Cartwell Shop API. Its endpoints and formats are documented in [cartwell_api_docs.md](./cartwell_api_docs.md).
- The Terraform configuration points at `s3://cartwell-usecase-data/cartwell-usecase-dataset/raw/cartwell/`.
- The intended Snowflake design has a LANDING area for whole JSON files and six RAW tables, with one row per source record.
- A prior S3 listing was reported to show 43 files through 2026-11-12. Re-run `LIST @RAW_CARTWELL_STAGE;` to confirm current availability.
- Do not add credentials or other secrets to the repository or project notes.

## Recent decisions

| Topic | Decision | Reason |
|---|---|---|
| JSON ingestion | Load wrapped JSON to LANDING, then flatten into RAW | RAW must contain one row per source record |
| RAW table shape | Store each source record in a `VARIANT` column with load metadata | Preserve source data while meeting the row-level requirement |
| dbt project folder | Use `transform/` | Required project subdirectory for the planned dbt Cloud setup |

## Work-session checklist

- [ ] Read this page and the latest entry in [PROJECT_JOURNAL.md](./PROJECT_JOURNAL.md).
- [ ] Use [README.md](./README.md) as the repository map before choosing a workflow.
- [ ] Identify the next unchecked action.
- [ ] After work, record what changed, why, and how it was verified.
- [ ] Update checkboxes only when the corresponding action is complete.
