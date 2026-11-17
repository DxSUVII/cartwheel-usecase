variable "database_name" {
  type    = string
  default = "CARTWELL"
}

resource "snowflake_database" "cartwell" {
  name    = var.database_name
  comment = "Cartwell raw layer, managed by Terraform"
}