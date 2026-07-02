---

type: reference
description: "Guide for depends_on - model build ordering"
---

> **Implementation Status**: All features fully implemented.


## depends_on Guide

Declares which models must be built before this one.

### Syntax

```yaml
depends_on: [temporal, geospatial]
```

### Build Order

Models are built in dependency-resolved order:

```
Tier 0 (Foundation — no dependencies):
  temporal              depends_on: []
  geospatial            depends_on: []     (dim_geography, dim_location)

Tier 1 (Entity — depends on foundation):
  corporate.entity      depends_on: [temporal]
  municipal_entity      depends_on: [temporal, geospatial]

Tier 2 (Geospatial subdivisions — depends on foundation + entity):
  municipal_geospatial  depends_on: [geospatial, municipal_entity]
  county_geospatial     depends_on: [geospatial, municipal_entity]

Tier 3 (Domain models — depends on foundation + subdivisions):
  county_property       depends_on: [temporal, county_geospatial]
  municipal_finance     depends_on: [temporal, municipal_entity, county_property]
  municipal_*           depends_on: [temporal, municipal_geospatial]
```

### Common Dependencies

| Dependency | Why |
|------------|-----|
| `temporal` | All facts FK to dim_calendar via date_id |
| `geospatial` | Foundation geographic reference (dim_geography for admin regions, dim_location for points) |
| `municipal_entity` | Municipality identity (dim_municipality) — needed by geo subdivisions |
| `county_geospatial` | County boundaries (townships, neighborhoods) — needed by property models |
| `municipal_geospatial` | Municipal boundaries (community areas, wards, districts) — needed by city domain models |

### Cross-Domain Geographic Path

```
Municipal fact → municipal geo dim → dim_municipality → dim_geography
                 (municipality_id)   (geography_id)    (Cook County row)

County fact → dim_township → dim_geography
             (township_code) (geography_id)  (Cook County row)

Both converge at dim_geography — enabling cross-domain geographic analysis.
```

### Rules

1. No circular dependencies
2. Base templates (`_base.*`) are NOT listed - they are templates, not built models
3. Only list direct dependencies, not transitive ones
