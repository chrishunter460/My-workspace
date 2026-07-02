---
type: domain-model-table
table: dim_tax_district
extends: _base.property.tax_district._dim_tax_district
table_type: dimension
primary_key: [tax_district_id]
unique_key: [tax_code]

schema:
  - [tax_district_id, integer, false, "PK", {derived: "ABS(HASH(tax_code))"}]
  - [tax_code, string, false, "Tax district code", {unique: true}]
  - [tax_district_name, string, true, "District name"]
  - [municipality, string, true, "Municipality name"]
  - [total_rate, "decimal(10,6)", true, "Combined tax rate"]
  - [equalization_factor, "decimal(10,6)", true, "State equalization factor (by township/year)"]

measures:
  - [district_count, count_distinct, tax_district_id, "Number of tax districts", {format: "#,##0"}]
  - [avg_tax_rate, avg, total_rate, "Average tax rate", {format: "#,##0.000000"}]
---

## Tax District Dimension

Cook County tax districts linking parcels to tax rates. Bridges county property assessments to municipal property tax ledger entries via `tax_code`.
