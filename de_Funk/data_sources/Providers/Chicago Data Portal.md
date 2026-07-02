---
type: api-provider
provider_id: chicago
provider: Chicago Data Portal

# API Configuration
api_type: soda
base_url: https://data.cityofchicago.org
homepage: https://data.cityofchicago.org

# Authentication
auth_model: api-key
env_api_key: CHICAGO_API_KEYS

# Rate Limiting
rate_limit_per_sec: 5.0
rate_limit_comment: "SODA API generally allows 5 req/sec with app token. Without token: 1 req/sec throttled."

# Default Headers (API key passed as X-App-Token header)
default_headers:
  X-App-Token: "${API_KEY}"

# Provider-specific settings
provider_settings:
  default_limit: 50000
  max_limit: 1000000
  default_limit_comment: "SODA default is 1000 rows. Set $limit for bulk downloads."

# Models Fed (Silver layer)
models:
  - city_finance

# Metadata
category: public
legal_entity_type: municipal
data_domains: [finance, public-safety, transportation, housing, regulatory]
data_tags: [public, time-series, reference, municipal, geospatial]
status: active
bulk_download: true
last_verified:
last_reviewed:
notes: "City of Chicago open data - Socrata platform (SODA API)"
---

## Description

City of Chicago open data portal powered by Socrata. Provides access to municipal datasets including crime statistics, building permits, business licenses, city finances, transportation data, and geospatial boundaries. Data updated at varying cadences from daily to annually depending on dataset.

## API Notes

- **Socrata Open Data API (SODA)**: RESTful API with SoQL query language
- **Base URL Structure**: `https://data.cityofchicago.org/resource/{dataset-id}.json`
- **Alternative endpoint**: `/api/v3/views/{dataset-id}/query.json` (newer v3 API)
- **Authentication**: App token passed via `X-App-Token` header or `$$app_token` query param
- **Response Format**: JSON (default), CSV, GeoJSON available

### Query Parameters (SoQL)

| Parameter | Description | Example |
|-----------|-------------|---------|
| `$select` | Fields to return | `$select=case_number,date,primary_type` |
| `$where` | Filter conditions | `$where=date > '2024-01-01'` |
| `$order` | Sort order | `$order=date DESC` |
| `$limit` | Max rows | `$limit=50000` |
| `$offset` | Pagination offset | `$offset=50000` |
| `$q` | Full-text search | `$q=theft` |

### Rate Limits

| Tier | Requests | Notes |
|------|----------|-------|
| No token | 1/sec, throttled | Not recommended |
| App token | ~5/sec | Standard for bulk downloads |

## Homelab Usage Notes

```bash
# Ingest Chicago endpoints
python -m scripts.ingest.run_bronze_ingestion --provider chicago --endpoints crimes

# Bulk download with pagination
# Use $limit=50000 and $offset for large datasets
```

- **Bulk Strategy**: Use pagination with `$limit` and `$offset` for datasets >50K rows
- **Incremental**: Filter by date column for incremental loads
- **Geospatial**: Some datasets include lat/lon or GeoJSON; can request `.geojson` format

## Known Quirks

1. **Default 1000 row limit**: Always specify `$limit` for bulk downloads
2. **Date formats**: ISO 8601 format (`YYYY-MM-DDTHH:MM:SS`)
3. **Null handling**: Null fields omitted from JSON response (not explicit null)
4. **Floating point timestamps**: Some date fields return as floating point epoch
5. **Throttling**: Without app token, requests are heavily throttled
6. **Schema changes**: Field names occasionally change; check `$describe` endpoint
7. **Block-Level Location**: Crime data shows block-level only (privacy)

## Endpoints by Domain

### Public Safety
| Endpoint ID | Dataset ID | Description | Records |
|-------------|------------|-------------|---------|
| `crimes` | `ijzp-q8t2` | Crime incidents 2001-present | 8M+ |
| `arrests` | `dpt3-jri9` | Arrests 2014-present | - |
| `police_beats` | `aerh-rz74` | Police beat boundaries | - |
| `iucr_codes` | `c7ck-438e` | Crime classification codes | - |

### Finance
| Endpoint ID | Dataset ID | Description | Notes |
|-------------|------------|-------------|-------|
| `budget_appropriations` | varies | Annual budget data | By year |
| `contracts` | `rsxa-ify5` | City contracts | - |
| `payments` | `s4vu-giwb` | Vendor payments | - |
| `budget_revenue` | varies | Revenue projections | By year |

### Transportation
| Endpoint ID | Dataset ID | Description | Records |
|-------------|------------|-------------|---------|
| `cta_l_ridership_daily` | `t2rn-p8d7` | Daily L station entries | 1.2M+ |
| `cta_bus_ridership_daily` | `jyb9-n7fm` | Daily bus route ridership | 1.5M+ |
| `cta_l_stops` | `8pix-ypme` | L station locations | - |
| `traffic_congestion` | `t2qc-9pjd` | Traffic congestion estimates | - |

### Regulatory/Housing
| Endpoint ID | Dataset ID | Description | Records |
|-------------|------------|-------------|---------|
| `building_permits` | `ydr8-5enu` | Building permits | 700K+ |
| `food_inspections` | `4ijn-s7e5` | Restaurant inspections | 250K+ |
| `business_licenses` | `r5kz-chrr` | Business licenses | 1M+ |
| `building_violations` | `22u3-xenr` | Building code violations | - |

### Geospatial
| Endpoint ID | Dataset ID | Description |
|-------------|------------|-------------|
| `boundaries_wards` | `sp34-6z76` | Ward boundaries |
| `community_areas` | `cauq-8yn6` | Community area boundaries |

## Bronze Tables

| Table | Source Endpoint | Partitions | Key Fields |
|-------|-----------------|------------|------------|
| `chicago_crimes` | crimes | `year` | id, case_number, date, primary_type, arrest |
| `chicago_building_permits` | building_permits | `year` | permit_number, issue_date, work_type |
| `chicago_business_licenses` | business_licenses | `year` | license_id, account_number, business_activity |
| `chicago_food_inspections` | food_inspections | `year` | inspection_id, dba_name, results, violations |
| `chicago_cta_l_ridership` | cta_l_ridership_daily | `year` | station_id, date, rides |
| `chicago_cta_bus_ridership` | cta_bus_ridership_daily | `year` | route, date, rides |

## Recommended Cadence

| Data Type | Frequency | Notes |
|-----------|-----------|-------|
| Crimes | Daily | Updated daily (minus 7-day lag) |
| Building Permits | Daily | Real-time updates |
| Business Licenses | Weekly | Less frequent changes |
| Food Inspections | Daily | Updated as inspections occur |
| CTA Ridership | Daily | Previous day's data |

## Pagination

Socrata uses offset-based pagination:
```
?$limit=50000&$offset=0      # First 50,000 records
?$limit=50000&$offset=50000  # Next 50,000 records
```
Maximum `$limit` per request: **50,000 records**. Provider handles pagination automatically.