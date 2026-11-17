variable "storage_integration_name" {
  description = "Existing storage integration created by hand in Snowsight. Terraform only refers to it by name (never recreate it: that would change its external ID and break the shared trust policy)."
  type        = string
  default     = "SHUBHAM_CARTWELL_S3_INT"
}

variable "source_data_url" {
  description = "S3 folder that holds the manager's ready-made raw files (six endpoint folders)."
  type        = string
  default     = "s3://cartwell-usecase-data/cartwell-usecase-dataset/raw/cartwell/"
}

resource "snowflake_schema" "raw" {
  database = snowflake_database.cartwell.name
  name     = "RAW"
  comment  = "Raw layer: one row per source record, exactly as received, no cleaning"
}

# JSON files arrive as one object per file with the records inside a list.
# They are loaded whole into this schema first, then split into one row per record.
resource "snowflake_schema" "landing" {
  database = snowflake_database.cartwell.name
  name     = "LANDING"
  comment  = "Landing zone: JSON files loaded whole, before being split into one row per record"
}

# One JSON format covers both plain JSON files and NDJSON (one JSON object per line).
resource "snowflake_file_format_json" "json" {
  database = snowflake_database.cartwell.name
  schema   = snowflake_schema.raw.name
  name     = "JSON_FF"
}

# CSV files have a header row, which is skipped.
resource "snowflake_file_format_csv" "csv" {
  database                     = snowflake_database.cartwell.name
  schema                       = snowflake_schema.raw.name
  name                         = "CSV_FF"
  skip_header                  = 1
  field_optionally_enclosed_by = "\""
}

resource "snowflake_stage_external_s3" "cartwell" {
  database            = snowflake_database.cartwell.name
  schema              = snowflake_schema.raw.name
  name                = "RAW_CARTWELL_STAGE"
  url                 = var.source_data_url
  storage_integration = var.storage_integration_name
  comment             = "The manager's raw files in S3, read through the storage integration"

  file_format {
    format_name = snowflake_file_format_json.json.fully_qualified_name
  }
}
