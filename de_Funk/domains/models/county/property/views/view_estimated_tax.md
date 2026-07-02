---
type: domain-model-view
view: view_estimated_tax
extends: _base.property.parcel._view_estimated_tax
view_type: derived

assumptions:
  total_rate:
    source: dim_tax_district.total_rate
    join_on: [tax_code=tax_code]
    description: "Composite tax rate from all overlapping taxing districts"

measures:
  - [total_estimated_tax, sum, estimated_tax, "Total estimated tax", {format: "$#,##0.00"}]
  - [avg_estimated_tax, avg, estimated_tax, "Average estimated tax", {format: "$#,##0.00"}]
  - [effective_tax_rate, expression, "SUM(estimated_tax) / NULLIF(SUM(equalized_value_total), 0)", "Effective tax rate", {format: "#,##0.000000"}]

status: active
---

## Estimated Tax View

Estimates property tax bills by applying composite tax rates to equalized values.

### Calculation Chain

```
_fact_assessed_values
     ↓ assessed_value_total × equalization_factor
_view_equalized_values (equalized_value_total)
     ↓ equalized_value_total × total_rate
_view_estimated_tax (estimated_tax)
```

### Source

Tax rates come from `dim_tax_district.total_rate`, which represents the composite rate from all overlapping taxing districts (school, park, library, municipality, etc.) for a given tax code.

### Usage

```sql
-- Estimated tax bill by parcel
SELECT
    p.parcel_id,
    p.township_code,
    t.estimated_tax,
    t.equalized_value_total,
    t.total_rate
FROM view_estimated_tax t
JOIN dim_parcel p ON t.parcel_id = p.parcel_id
WHERE t.year = 2024
  AND t.assessment_stage = 'CERTIFIED';
```
