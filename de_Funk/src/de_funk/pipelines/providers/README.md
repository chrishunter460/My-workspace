# Data Providers Architecture

This directory contains provider-specific implementations for different data sources. Each provider follows a consistent pattern for ingestion, making it easy to add new data sources.

## Architecture Overview

```
providers/
├── alpha_vantage/    # Alpha Vantage financial market data (v2.0 - sole securities provider)
├── chicago/          # Chicago Data Portal (Socrata API)
├── cook_county/      # Cook County Data Portal (Socrata API) - property tax & assessor data
└── bls/              # Bureau of Labor Statistics
```

> **Note**: Polygon.io was removed in v2.0. Alpha Vantage is now the exclusive provider for securities data.

### Provider Structure

Each provider follows this standard structure:

```
provider_name/
├── __init__.py
├── provider_registry.py    # Endpoint configuration
├── provider_ingestor.py    # Data fetching with pagination
└── facets/                 # Data source definitions
    ├── __init__.py
    ├── provider_base_facet.py
    └── specific_facet.py
```

## Components

### 1. Registry
**Purpose**: Maps API endpoints to configuration

**Base Class**: `datapipelines.base.registry.BaseRegistry`

**Responsibilities**:
- Load endpoint configurations from JSON
- Render paths with parameters
- Build query strings
- Manage authentication headers

### 2. Ingestor
**Purpose**: Orchestrates API calls and handles pagination

**Base Class**: `datapipelines.ingestors.base_ingestor.Ingestor`

**Responsibilities**:
- Initialize HTTP client with rate limiting
- Implement provider-specific pagination
- Fetch data through facets
- Write to Bronze layer via BronzeSink (Delta Lake format)

**Pagination Strategies by Provider**:
- **Alpha Vantage**: Single response per endpoint (no pagination needed)
- **Chicago**: Offset-based (uses `$offset` and `$limit` parameters)
- **BLS**: No pagination (returns full dataset in single response)

### 3. Facets
**Purpose**: Define what data to fetch and how to transform it

**Base Class**: `datapipelines.facets.base_facet.Facet`

**Responsibilities**:
- `calls()`: Generate API call specifications
- `normalize()`: Convert JSON to Spark DataFrame
- `postprocess()`: Transform and clean data

## Alpha Vantage Provider

### Configuration
**File**: `configs/alpha_vantage_endpoints.json`

**Endpoints**:
- `company_overview`: Company reference data with market cap, CIK
- `time_series_daily_adjusted`: Historical OHLCV prices
- `income_statement`: Income statement fundamentals
- `balance_sheet`: Balance sheet fundamentals
- `cash_flow`: Cash flow statements
- `earnings`: Quarterly and annual earnings

### Rate Limits
- **Free Tier**: 25 requests/day, 5 requests/minute
- **Premium**: 75 requests/minute

### Usage Example
```python
from datapipelines.providers.alpha_vantage.alpha_vantage_ingestor import AlphaVantageIngestor

# Initialize with Spark session and storage config
ingestor = AlphaVantageIngestor(spark, storage_cfg)

# Run comprehensive ingestion
results = ingestor.run_comprehensive(
    tickers=['AAPL', 'MSFT', 'NVDA'],
    from_date='2024-01-01',
    max_tickers=100,
    include_fundamentals=True
)
```

### Bronze Tables (Delta Lake)
- `securities_reference` - Unified reference data with market cap, CIK
- `securities_prices_daily` - Daily OHLCV prices
- `income_statements` - Income statement data
- `balance_sheets` - Balance sheet data
- `cash_flows` - Cash flow data
- `earnings` - Earnings data

## Chicago Provider

### Configuration
**File**: `Documents/Data Sources/Providers/Chicago Data Portal.md`

**Key Endpoints** (27 total across domains):
- **Finance**: `budget_appropriations`, `contracts`, `payments`
- **Public Safety**: `crimes`, `arrests`, `police_beats`
- **Transportation**: `cta_ridership_l`, `cta_ridership_bus`, `traffic_congestion`
- **Housing**: `building_permits`, `zoning_districts`
- **Regulatory**: `food_inspections`, `building_violations`, `business_licenses`
- **Economic**: `economic_indicators`, `unemployment`, `per_capita_income`

### API Details
- **Platform**: Socrata Open Data API (SODA)
- **Base URL**: `https://data.cityofchicago.org`
- **Authentication**: X-App-Token header (optional but recommended)
- **Rate Limit**: 5 req/sec with token, throttled without
- **Pagination**: Offset-based using `$offset` and `$limit`
- **Max per page**: 50,000 records

### Usage Example (v2.6+)
```python
from datapipelines.providers.chicago import create_chicago_provider
from pathlib import Path

# Create provider
provider = create_chicago_provider(api_cfg, storage_cfg, spark, docs_path=Path("Documents"))

# Ingest single endpoint
result = provider.ingest_endpoint("crimes", max_records=10000)
print(f"Ingested {result.record_count} records")

# Ingest all active endpoints
results = provider.ingest_all(max_records_per_endpoint=10000)
for eid, result in results.items():
    print(f"{eid}: {'✓' if result.success else '✗'} {result.record_count} records")

# Query with filters
result = provider.fetch_dataset(
    "crimes",
    query_params={"$where": "year >= 2023", "$order": "date DESC"},
    max_records=5000
)
```

### Bronze Tables (Delta Lake)
- `chicago_crimes` - Crime incidents
- `chicago_building_permits` - Building permits
- `chicago_business_licenses` - Business licenses
- `chicago_budget_appropriations` - Annual budget data
- See `Documents/Data Sources/Endpoints/Chicago Data Portal/` for full list

## Cook County Provider

### Configuration
**File**: `Documents/Data Sources/Providers/Cook County Data Portal.md`

**Key Endpoints** (13 total across domains):
- **Finance**: `parcel_sales`, `assessed_values`, `tax_exempt_parcels`
- **Housing**: `residential_characteristics`, `condo_characteristics`, `commercial_valuation`
- **Geospatial**: `parcel_universe`, `neighborhood_boundaries`, `parcel_addresses`
- **Regulatory**: `permits`, `assessor_appeals`, `bor_appeal_decisions`

### API Details
- **Platform**: Socrata Open Data API (SODA)
- **Base URL**: `https://datacatalog.cookcountyil.gov`
- **Authentication**: X-App-Token header (optional but recommended)
- **Rate Limit**: 5 req/sec with token
- **Pagination**: Offset-based using `$offset` and `$limit`
- **PIN Format**: 14-digit zero-padded (transforms applied automatically)

### Usage Example (v2.6+)
```python
from datapipelines.providers.cook_county import create_cook_county_provider
from pathlib import Path

# Create provider
provider = create_cook_county_provider(api_cfg, storage_cfg, spark, docs_path=Path("Documents"))

# Ingest property data endpoints
results = provider.ingest_all(
    endpoint_ids=["parcel_sales", "assessed_values", "residential_characteristics"],
    max_records_per_endpoint=50000
)

# Fetch specific parcels by PIN
result = provider.fetch_parcel_data(
    pins=["12345678901234", "12345678901235"],
    year=2023
)
```

### Bronze Tables (Delta Lake)
- `cook_county_parcel_sales` - Property sales transactions
- `cook_county_assessed_values` - Annual assessed values
- `cook_county_parcel_universe` - All parcels with characteristics
- `cook_county_residential_chars` - Single/multi-family characteristics
- See `Documents/Data Sources/Endpoints/Cook County Data Portal/` for full list

## BLS Provider

### Configuration
**File**: `configs/bls_endpoints.json`

**Endpoints**:
- `timeseries`: Get time series data by series ID
- `series_info`: Get series metadata

**Key Series IDs**:
- `LNS14000000`: Unemployment Rate
- `CES0000000001`: Total Nonfarm Employment
- `CUUR0000SA0`: Consumer Price Index (CPI)
- `WPUFD4`: Producer Price Index (PPI)
- `PRS85006092`: Labor Productivity
- `CES0500000003`: Average Hourly Earnings
- `JTS00000000JOL`: Job Openings
- `JTS00000000QUR`: Quits Rate

### API Details
- **Base URL**: `https://api.bls.gov/publicAPI/v2`
- **Authentication**: Registration key in request body
- **Rate Limit**: 500 requests/day with registration
- **Method**: POST with JSON body
- **Pagination**: None (returns complete time series)

### Usage Example
```python
from datapipelines.providers.bls.bls_ingestor import BLSIngestor
from datapipelines.providers.bls.facets.unemployment_facet import UnemploymentFacet

ingestor = BLSIngestor(ctx.bls_cfg, ctx.storage_cfg, ctx.spark)
facet = UnemploymentFacet(ctx.spark, start_year="2020", end_year="2023")
batches = ingestor._fetch_calls(facet.calls())
df = facet.normalize(batches)
```

## Adding a New Provider

### Step 1: Create Directory Structure
```bash
mkdir -p datapipelines/providers/newprovider/facets
touch datapipelines/providers/newprovider/__init__.py
touch datapipelines/providers/newprovider/facets/__init__.py
```

### Step 2: Create Configuration
Create `configs/newprovider_endpoints.json`:
```json
{
  "credentials": { "api_keys": ["YOUR_KEY"] },
  "base_urls": { "core": "https://api.example.com" },
  "headers": { "Authorization": "Bearer ${API_KEY}" },
  "rate_limit_per_sec": 1.0,
  "endpoints": {
    "endpoint_name": {
      "base": "core",
      "method": "GET",
      "path_template": "/path/to/{resource}",
      "required_params": ["resource"],
      "default_query": { "limit": 1000 },
      "response_key": "results",
      "default_path_params": {}
    }
  }
}
```

### Step 3: Create Registry
`newprovider/newprovider_registry.py`:
```python
from datapipelines.base.registry import BaseRegistry

class NewProviderRegistry(BaseRegistry):
    """Registry for NewProvider API endpoints."""
    pass
```

### Step 4: Create Ingestor
`newprovider/newprovider_ingestor.py`:
```python
from datapipelines.providers.newprovider.newprovider_registry import NewProviderRegistry
from datapipelines.base.http_client import HttpClient
from datapipelines.base.key_pool import ApiKeyPool
from datapipelines.ingestors.bronze_sink import BronzeSink
from datapipelines.ingestors.base_ingestor import Ingestor

class NewProviderIngestor(Ingestor):
    def __init__(self, provider_cfg, storage_cfg, spark):
        super().__init__(storage_cfg=storage_cfg)
        self.registry = NewProviderRegistry(provider_cfg)
        self.http = HttpClient(
            self.registry.base_urls,
            self.registry.headers,
            self.registry.rate_limit,
            ApiKeyPool((provider_cfg.get("credentials") or {}).get("api_keys") or [], 90)
        )
        self.sink = BronzeSink(storage_cfg)
        self.spark = spark

    def _fetch_calls(self, calls, response_key="results", max_pages=None, enable_pagination=True):
        # Implement provider-specific pagination logic here
        pass
```

### Step 5: Create Base Facet
`newprovider/facets/newprovider_base_facet.py`:
```python
from datapipelines.facets.base_facet import Facet

class NewProviderFacet(Facet):
    def __init__(self, spark, **kwargs):
        super().__init__(spark)
        # Provider-specific initialization

    def calls(self):
        raise NotImplementedError
```

### Step 6: Create Specific Facets
`newprovider/facets/dataset_facet.py`:
```python
from pyspark.sql import functions as F
from datapipelines.providers.newprovider.facets.newprovider_base_facet import NewProviderFacet

class DatasetFacet(NewProviderFacet):
    SPARK_CASTS = {
        "field1": "string",
        "field2": "double"
    }

    def calls(self):
        yield {"ep_name": "endpoint_name", "params": {}}

    def postprocess(self, df):
        return df.select(
            F.col("field1").cast("string"),
            F.col("field2").cast("double")
        ).dropDuplicates()
```

## Bronze Layer Output

**Format**: Delta Lake tables (v2.3+) with schema evolution

BronzeSink writes data as Delta Lake tables with:
- `mergeSchema=true` for automatic schema evolution
- `overwriteSchema=true` for partition changes on overwrite

## Testing

### Test Provider Integration
```bash
# Run the full pipeline with Alpha Vantage
python -m scripts.ingest.run_full_pipeline --from 2024-01-01 --max-tickers 10
```

### Test Individual Provider
```bash
# Test Alpha Vantage ingestion
python -m scripts.test_alpha_vantage_ingestion --tickers AAPL MSFT
```

## Common Issues

### Issue: Import errors
**Solution**: Update imports to use provider paths under `datapipelines/providers/`

### Issue: Rate limiting errors
**Solution**: Adjust `rate_limit_per_sec` in endpoint config or add more API keys

### Issue: Schema merge failures with Delta Lake
**Solution**: BronzeSink automatically handles this with `mergeSchema=true`. If issues persist, delete the affected Delta table and re-ingest.

## Resources

- **Alpha Vantage API**: https://www.alphavantage.co/documentation/
- **Chicago Data Portal**: https://data.cityofchicago.org
- **Cook County Data Portal**: https://datacatalog.cookcountyil.gov
- **Socrata Developer Docs**: https://dev.socrata.com/docs/endpoints.html
- **BLS API**: https://www.bls.gov/developers/api_signature_v2.htm
