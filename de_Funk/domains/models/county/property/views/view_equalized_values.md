---
type: domain-model-view
view: view_equalized_values
extends: _base.property.parcel._view_equalized_values
view_type: derived

assumptions:
  equalization_factor:
    source: dim_tax_district.equalization_factor
    join_on: [township_code=township_code, year=tax_year]
    description: "Cook County equalization factors by township and year"

measures:
  - [total_equalized_value, sum, equalized_value_total, "Total equalized value", {format: "$#,##0.00"}]
  - [avg_equalized_value, avg, equalized_value_total, "Average equalized value", {format: "$#,##0.00"}]
  - [equalization_delta, expression, "SUM(equalized_value_total - assessed_value_total)", "Total equalization adjustment", {format: "$#,##0.00"}]

status: active
---

## Equalized Values View

Applies Cook County equalization factors to assessed values by township and year.

### Calculation

```
equalized_value_total = assessed_value_total × equalization_factor
```

The equalization factor adjusts assessed values to reflect the state equalization level. Different townships have different factors depending on assessment ratios relative to the state standard.

### Source

Equalization factors are joined from `dim_tax_district` by `township_code` and `year`. If no match is found, the base template default of `1.0` applies (no adjustment).

### Usage

```sql
-- Compare raw vs equalized values by township
SELECT
    township_code,
    year,
    SUM(assessed_value_total) as raw_assessed,
    SUM(equalized_value_total) as equalized,
    AVG(equalization_factor) as avg_factor
FROM view_equalized_values
GROUP BY township_code, year;
```
