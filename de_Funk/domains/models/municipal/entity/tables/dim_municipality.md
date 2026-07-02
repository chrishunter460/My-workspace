---
type: domain-model-table
table: dim_municipality
extends: _base.entity.municipality._dim_municipality
table_type: dimension
primary_key: [municipality_id]
unique_key: [municipality_name, municipality_type]

# Seeded dimension — not built from source data.
# Each municipality in the federation gets a row here.
seed: true

# [column, type, nullable, description, {options}]
schema:
  - [municipality_id, integer, false, "PK (= legal_entity_id on all fact tables)", {derived: "ABS(HASH(CONCAT(municipality_type, '_', municipality_name)))"}]
  - [municipality_name, string, false, "Official name"]
  - [municipality_type, string, false, "CITY, COUNTY, TOWNSHIP, SPECIAL_DISTRICT"]
  - [fips_code, string, true, "Federal FIPS code"]
  - [state, string, true, "State"]
  - [population, integer, true, "Population estimate"]
  - [latitude, double, true, "Centroid latitude"]
  - [longitude, double, true, "Centroid longitude"]
  - [county_fips, string, true, "5-digit county FIPS (for geography linkage)"]
  - [geography_id, integer, true, "FK to geospatial.dim_geography (county-level)", {fk: geospatial.dim_geography.geography_id, derived: "ABS(HASH(CONCAT('COUNTY_', county_fips)))"}]
  - [is_active, boolean, false, "Currently operating", {default: true}]

data:
  - municipality_id: "ABS(HASH(CONCAT('CITY_', 'Chicago')))"
    municipality_name: "Chicago"
    municipality_type: CITY
    fips_code: "1714000"
    state: IL
    population: 2746388
    latitude: 41.8781
    longitude: -87.6298
    county_fips: "17031"
    geography_id: "ABS(HASH(CONCAT('COUNTY_', '17031')))"
    is_active: true
---

## Municipality Dimension

Seeded entity dimension for each jurisdiction in the municipal finance federation. This gives `legal_entity_id` a concrete target to FK to.

### Why Seeded?

Municipality records don't come from bronze data — they're reference data about the jurisdictions we track. Each municipality gets one row, seeded at build time (phase 1).

### legal_entity_id Resolution

All municipal fact tables set `legal_entity_id = ABS(HASH(CONCAT('CITY_', 'Chicago')))`. This FK resolves to `dim_municipality.municipality_id`, enabling:

```sql
SELECT m.municipality_name, SUM(le.transaction_amount) as total_payments
FROM fact_ledger_entries le
JOIN dim_municipality m ON le.legal_entity_id = m.municipality_id
GROUP BY m.municipality_name;
```
