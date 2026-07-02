---
type: domain-model-view
view: view_township_summary
extends: _base.property.parcel._view_township_summary
view_type: rollup

measures:
  - [total_assessed_value, sum, total_assessed_value, "Total assessed value across townships", {format: "$#,##0.00"}]
  - [total_parcels, sum, parcel_count, "Total parcels across townships", {format: "#,##0"}]
  - [avg_assessed_value_per_parcel, expression, "SUM(total_assessed_value) / NULLIF(SUM(parcel_count), 0)", "Average assessed value per parcel", {format: "$#,##0.00"}]

status: active
---

## Township Summary View

Pre-aggregated assessment summary at the township level. Changes grain from parcel-level to township-level for geographic comparisons.

### Grain Change

```
_fact_assessed_values (parcel_id, year, assessment_stage)
     ↓ GROUP BY township_code, year, assessment_stage
_view_township_summary (township_code, year, assessment_stage)
```

### Output Columns

| Column | Type | Description |
|--------|------|-------------|
| township_code | string | Township identifier |
| year | integer | Assessment year |
| assessment_stage | string | MAILED, CERTIFIED, BOARD_CERTIFIED, APPEAL |
| parcel_count | integer | Number of parcels in township |
| total_assessed_value | decimal | Sum of assessed values |
| avg_assessed_value | decimal | Average assessed value |

### Usage

```sql
-- Compare townships by total assessed value
SELECT
    township_code,
    year,
    parcel_count,
    total_assessed_value,
    avg_assessed_value
FROM view_township_summary
WHERE assessment_stage = 'CERTIFIED'
  AND year = 2024
ORDER BY total_assessed_value DESC;
```
