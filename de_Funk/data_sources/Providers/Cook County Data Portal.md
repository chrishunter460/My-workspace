---
type: api-provider
provider_id: cook_county
provider: Cook County Data Portal

# API Configuration
api_type: soda
base_url: https://datacatalog.cookcountyil.gov
homepage: https://datacatalog.cookcountyil.gov

# Authentication
auth_model: api-key
env_api_key: COOK_COUNTY_API_KEYS

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
models: []

# Metadata
category: public
legal_entity_type: county
data_domains: [finance, housing, geospatial, regulatory, property]
data_tags: [public, property-tax, assessment, parcel, county]
status: active
bulk_download: true
last_verified:
last_reviewed:
notes: "Cook County Assessor open data - Socrata platform (SODA API)"
---

## Description

Cook County Assessor's Office open data portal powered by Socrata. Provides access to property assessment data, parcel characteristics, sales history, appeals, permits, and geospatial boundaries. Primary source for Cook County (Illinois) property tax and assessment data.

Key datasets include:
- **Parcel data**: Property characteristics, assessments, sales
- **Housing**: Residential and commercial property details
- **Finance**: Tax-exempt parcels, assessed values, appeals
- **Geospatial**: Parcel boundaries, neighborhoods, addresses

## API Notes

- **Socrata Open Data API (SODA)**: RESTful API with SoQL query language
- **Base URL Structure**: `https://datacatalog.cookcountyil.gov/resource/{dataset-id}.json`
- **Alternative endpoint**: `/api/v3/views/{dataset-id}/query.json` (newer v3 API)
- **Authentication**: App token passed via `X-App-Token` header or `$$app_token` query param
- **Response Format**: JSON (default), CSV, GeoJSON available

### Query Parameters (SoQL)

| Parameter | Description | Example |
|-----------|-------------|---------|
| `$select` | Fields to return | `$select=pin,township_code,class` |
| `$where` | Filter conditions | `$where=year > 2020` |
| `$order` | Sort order | `$order=sale_date DESC` |
| `$limit` | Max rows | `$limit=50000` |
| `$offset` | Pagination offset | `$offset=50000` |
| `$q` | Full-text search | `$q=residential` |

### Rate Limits

| Tier | Requests | Notes |
|------|----------|-------|
| No token | 1/sec, throttled | Not recommended |
| App token | ~5/sec | Standard for bulk downloads |

## Homelab Usage Notes

```bash
# Ingest Cook County endpoints
python -m scripts.ingest.run_bronze_ingestion --provider cook_county --endpoints parcel_sales

# Bulk download with pagination
# Use $limit=50000 and $offset for large datasets
```

- **PIN Handling**: Always zero-pad PINs to 14 digits - datasets may lose leading zeros
- **Bulk Strategy**: Use pagination with `$limit` and `$offset` for datasets >50K rows
- **Incremental**: Filter by year or date column for incremental loads
- **Geospatial**: Parcel boundaries available in GeoJSON format

## Known Quirks

1. **PIN Zero-Padding**: PINs must be zero-padded to 14 digits; downloads may strip leading zeros
2. **Default 1000 row limit**: Always specify `$limit` for bulk downloads
3. **Monthly updates**: Most datasets updated monthly with lag
4. **Year-based partitioning**: Many datasets partitioned by assessment year
5. **Class code changes**: Property class codes can change across time
6. **Incomplete current year**: Current year data incomplete until assessment roll certified
7. **Float-as-String for Integers**: Year values may come as "2025.0" - requires double→int cast

## PIN (Parcel Index Number) Format

Cook County uses a 14-digit PIN to uniquely identify each parcel:
```
XX-XX-XXX-XXX-XXXX
 |  |   |   |   |
 |  |   |   |   +-- Parcel suffix
 |  |   |   +------ Block number
 |  |   +---------- Section number
 |  +-------------- Township
 +----------------- Volume
```
Always zero-pad PINs to 14 digits: `pin.zfill(14)`

## Endpoints by Domain

### Finance
| Endpoint ID | Dataset ID | Description | Records |
|-------------|------------|-------------|---------|
| `parcel_sales` | `wvhk-k5uv` | Property sales 1999-present | 2.5M+ |
| `assessed_values` | `uzyt-m557` | Annual assessed values | 20M+ |
| `tax_exempt_parcels` | `4i5r-5quw` | Tax-exempt properties | - |

### Housing
| Endpoint ID | Dataset ID | Description | Records |
|-------------|------------|-------------|---------|
| `residential_characteristics` | `bcnq-qi2z` | Single/multi-family characteristics | 1.5M+ |
| `condo_characteristics` | `8c7e-zxxx` | Condominium unit details | - |
| `commercial_valuation` | `4i5r-5quw` | Commercial property data | - |

### Geospatial
| Endpoint ID | Dataset ID | Description | Records |
|-------------|------------|-------------|---------|
| `parcel_universe` | `tx2p-k2g9` | All parcels with base info | 1.8M+ |
| `neighborhood_boundaries` | `pcdw-pxtg` | Assessor neighborhood boundaries | - |
| `parcel_addresses` | `3723-97qp` | Parcel address lookups | - |
| `parcel_proximity` | varies | Proximity to amenities | - |

### Regulatory
| Endpoint ID | Dataset ID | Description |
|-------------|------------|-------------|
| `assessor_appeals` | `y7vc-dvez` | Assessment appeals filed |
| `bor_appeal_decisions` | `7pny-nedm` | Board of Review decisions |
| `permits` | varies | Building permits |

## Bronze Tables

| Table | Source Endpoint | Partitions | Key Fields |
|-------|-----------------|------------|------------|
| `cook_county_parcel_sales` | parcel_sales | `year` | pin, sale_date, sale_price, deed_type |
| `cook_county_assessed_values` | assessed_values | `year` | pin, year, mailed_bldg, mailed_land, mailed_tot |
| `cook_county_parcel_universe` | parcel_universe | - | pin, class, township_code, nbhd_code |
| `cook_county_residential_chars` | residential_characteristics | `year` | pin, year, bldg_sf, land_sf, age, rooms |

## Property Classes

| Class | Description |
|-------|-------------|
| 2-XX | Residential (single-family, multi-family) |
| 3-XX | Multi-family (7+ units) |
| 5-XX | Commercial |
| 6-XX | Industrial |
| 7-XX | Vacant land |
| 8-XX | Tax-exempt |

Full reference: [Cook County Class Codes](https://prodassets.cookcountyassessor.com/s3fs-public/form_documents/classcode.pdf)

## Recommended Cadence

| Data Type | Frequency | Notes |
|-----------|-----------|-------|
| Parcel Sales | Monthly | Sales reported on lag |
| Assessed Values | Quarterly | Major updates during triennial reassessment |
| Characteristics | Quarterly | Updated as parcels resurveyed |
| Appeals | Monthly | Updated as appeals filed/decided |

## Geographic Coverage

Cook County, Illinois includes:
- **City of Chicago** (major portion)
- **130+ suburban municipalities**
- **~1.8 million parcels**
- **5.2 million residents** (2nd most populous US county)