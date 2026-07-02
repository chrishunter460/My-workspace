---
type: domain-model-table
table: dim_location
table_type: dimension
primary_key: [location_id]

schema:
  - [location_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT(location_type, '_', location_code)))"}]
  - [location_type, string, false, "country, state, county, city, zip"]
  - [location_code, string, false, "Unique code within type"]
  - [location_name, string, false, "Display name"]
  - [country_code, string, true, "ISO country code"]
  - [state_code, string, true, "FIPS state code"]
  - [county_code, string, true, "FIPS county code"]
  - [city_code, string, true, "City name (denormalized string, not FK)"]
  - [zip_code, string, true, "ZIP/postal code"]
  - [latitude, double, true, "Centroid latitude"]
  - [longitude, double, true, "Centroid longitude"]
  - [geom_wkt, string, true, "Geometry WKT"]
  - [population, long, true, "Population estimate"]
  - [land_area_sqmi, double, true, "Land area in square miles"]

measures:
  - [location_count, count_distinct, location_id, "Number of locations", {format: "#,##0"}]
  - [total_population, sum, population, "Total population", {format: "#,##0"}]
---

## Location Dimension

Master location dimension supporting multiple geographic levels.
