---
type: domain-model-source
source: census_us_geography
from: bronze.census.us_geography
maps_to: dim_geography
domain_source: "'census'"

aliases:
  - [geography_id, geography_id]
  - [geography_type, geography_type]
  - [geography_code, geography_code]
  - [geography_name, geography_name]
  - [parent_geography_id, parent_geography_id]
  - [state_fips, state_fips]
  - [state_name, state_name]
  - [state_abbr, state_abbr]
  - [county_fips, county_fips]
  - [county_name, county_name]
  - [region, region]
  - [division, division]
  - [latitude, latitude]
  - [longitude, longitude]
  - [population, population]
  - [land_area_sqmi, land_area_sqmi]
---

## US Geography Source

Census Bureau states and counties. Seeded via `python -m scripts.seed.seed_geography`.
