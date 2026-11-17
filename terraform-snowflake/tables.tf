locals {
  # The six RAW tables. Every one has the same four columns.
  raw_tables = toset([
    "CUSTOMERS",
    "CUSTOMER_UPDATES",
    "PRODUCTS",
    "ORDERS",
    "TRANSACTIONS",
    "PRICE_CHANGES",
  ])
}

resource "snowflake_table" "raw" {
  for_each = local.raw_tables

  database = snowflake_database.cartwell.name
  schema   = snowflake_schema.raw.name
  name     = each.key
  comment  = "Raw ${lower(each.key)}: one row per source record, as received"

  column {
    name = "RECORD"
    type = "VARIANT"
  }
  column {
    name = "_SOURCE_FILE"
    type = "VARCHAR"
  }
  column {
    name = "_LOAD_DATE"
    type = "DATE"
  }
  column {
    name = "_LOADED_AT"
    type = "TIMESTAMP_LTZ"
  }
}

# Whole JSON files, one row per file. Not part of the six RAW tables.
resource "snowflake_table" "landing_json_files" {
  database = snowflake_database.cartwell.name
  schema   = snowflake_schema.landing.name
  name     = "JSON_FILES"
  comment  = "One row per JSON file, before it is split into records"

  column {
    name = "CONTENT"
    type = "VARIANT"
  }
  column {
    name = "_SOURCE_FILE"
    type = "VARCHAR"
  }
  column {
    name = "_LOAD_DATE"
    type = "DATE"
  }
  column {
    name = "_LOADED_AT"
    type = "TIMESTAMP_LTZ"
  }
}
