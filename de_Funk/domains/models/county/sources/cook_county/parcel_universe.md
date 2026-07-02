---
type: domain-model-source
source: parcel_universe
extends: _base.property.parcel
maps_to: dim_parcel
from: bronze.cook_county_parcel_universe
domain_source: "'cook_county'"

aliases:
  # Common fields — available in bronze.cook_county_parcel_universe
  - [parcel_id, "LPAD(CAST(pin AS STRING), 14, '0')"]
  - [parcel_code, "LPAD(CAST(pin AS STRING), 14, '0')"]
  - [property_class, class]
  - [township_code, township_code]
  - [municipality, municipality]
  - [school_district, school_district]
  - [park_district, park_district]
  - [latitude, latitude]
  - [longitude, longitude]
  - [year, year]

  # Fields not available in this Bronze source — NULL placeholders
  - [neighborhood_code, "CAST(NULL AS STRING)"]
  - [year_built, "CAST(NULL AS INT)"]
  - [land_sqft, "CAST(NULL AS DOUBLE)"]
  - [building_sqft, "CAST(NULL AS DOUBLE)"]
  - [tax_code, "CAST(NULL AS STRING)"]

  # Residential fields — not available in this Bronze source
  - [bedrooms, "CAST(NULL AS INT)"]
  - [bathrooms, "CAST(NULL AS DOUBLE)"]
  - [stories, "CAST(NULL AS INT)"]
  - [garage_spaces, "CAST(NULL AS INT)"]
  - [basement, "CAST(NULL AS STRING)"]
  - [exterior_wall, "CAST(NULL AS STRING)"]

  # Commercial fields — not available in this Bronze source
  - [commercial_sqft, "CAST(NULL AS DOUBLE)"]
  - [commercial_units, "CAST(NULL AS INT)"]
  - [residential_units, "CAST(NULL AS INT)"]
  - [space_type, "CAST(NULL AS STRING)"]
  - [floors, "CAST(NULL AS INT)"]

  # Industrial fields — not available in this Bronze source
  - [industrial_sqft, "CAST(NULL AS DOUBLE)"]
  - [loading_docks, "CAST(NULL AS INT)"]
  - [ceiling_height, "CAST(NULL AS DOUBLE)"]
  - [zoning_class, "CAST(NULL AS STRING)"]
---

## Parcel Universe

Complete inventory of all Cook County parcels. Bronze columns: `pin`, `year`, `township_code`, `class`, `municipality`, `school_district`, `park_district`, `latitude`, `longitude`. Detailed property characteristics (bedrooms, sqft, etc.) are not available in this dataset and are mapped as NULL placeholders for schema compatibility with the base template.
