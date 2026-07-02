---
type: domain-model-table
table: dim_geography
extends: _base.geography.geo_spatial._dim_boundary
table_type: dimension
primary_key: [geography_id]
unique_key: [geography_type, geography_code]

# [column, type, nullable, description, {options}]
schema:
  - [geography_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT(geography_type, '_', geography_code)))"}]
  - [geography_type, string, false, "Region level", {enum: [STATE, COUNTY]}]
  - [geography_code, string, false, "Standard code (FIPS)"]
  - [geography_name, string, false, "Display name"]
  - [parent_geography_id, integer, true, "Self-ref FK (county parent is state)", {fk: dim_geography.geography_id}]

  # Denormalized state fields — on EVERY row, no joins needed
  - [state_fips, string, false, "2-digit state FIPS code"]
  - [state_name, string, false, "State name"]
  - [state_abbr, string, false, "State abbreviation (IL, NY, etc.)"]

  # County fields — null for STATE rows
  - [county_fips, string, true, "5-digit county FIPS (null for states)"]
  - [county_name, string, true, "County name (null for states)"]

  # Common attributes
  - [region, string, true, "Census region"]
  - [division, string, true, "Census division"]
  - [latitude, double, true, "Centroid latitude"]
  - [longitude, double, true, "Centroid longitude"]
  - [population, long, true, "Population estimate"]
  - [land_area_sqmi, double, true, "Land area in square miles"]

measures:
  - [geography_count, count_distinct, geography_id, "Number of regions", {format: "#,##0"}]
  - [state_count, expression, "COUNT(DISTINCT CASE WHEN geography_type = 'STATE' THEN geography_id END)", "States", {format: "#,##0"}]
  - [county_count, expression, "COUNT(DISTINCT CASE WHEN geography_type = 'COUNTY' THEN geography_id END)", "Counties", {format: "#,##0"}]
  - [total_population, sum, population, "Total population", {format: "#,##0"}]
---

## Geography Dimension

Single denormalized dimension for US administrative regions. State fields are on every row — no joins required to get "what state is this county in?"

### Hierarchy

Self-referencing via `parent_geography_id`:

```
STATE (geography_type = 'STATE')
  └── COUNTY (geography_type = 'COUNTY', parent → STATE)
```

### PK Examples

| Entity | geography_code | geography_id |
|--------|---------------|-------------|
| Illinois | `17` | `ABS(HASH('STATE_17'))` |
| Cook County | `17031` | `ABS(HASH('COUNTY_17031'))` |

### Why Denormalized?

County rows carry `state_fips`, `state_name`, `state_abbr` directly. This eliminates the need for a separate `dim_state` table and the join that would accompany it. For a ~3,200 row reference dimension, the storage cost of denormalization is negligible.

### Extensibility

To add ZIP codes, census tracts, or metro areas, add a new `geography_type` enum value and populate `parent_geography_id` to link into the hierarchy.
