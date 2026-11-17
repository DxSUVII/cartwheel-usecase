terraform {
  required_providers {
    snowflake = {
      source  = "snowflakedb/snowflake"
      version = "~> 2.23"
    }
  }
}

# The login comes from SNOWFLAKE_* environment variables, never from files.
provider "snowflake" {
  # snowflake_table is still a preview feature in this provider version.
  preview_features_enabled = ["snowflake_table_resource"]
}
