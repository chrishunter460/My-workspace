---
type: api-provider
provider_id:                            # Unique code identifier (e.g., "alpha_vantage")
provider:                               # Human-readable name (e.g., "Alpha Vantage")

# API Configuration
api_type: rest                          # rest | soda | graphql | rpc | custom
base_url:                               # Base API URL (e.g., "https://www.alphavantage.co/query")
homepage:                               # Human-facing website for documentation

# Authentication
auth_model: api-key                     # none | api-key | oauth2 | basic
env_api_key:                            # Environment variable name (e.g., "ALPHA_VANTAGE_API_KEYS")

# Rate Limiting
rate_limit_per_sec: 1.0                 # Requests per second limit
rate_limit_comment:                     # Notes about rate limits (free vs premium tiers)

# Default Headers (applied to all endpoints)
default_headers: {}                     # e.g., {X-App-Token: "${API_KEY}"}

# Provider-specific settings (available to endpoints via 'inherit')
provider_settings: {}                   # Custom settings (e.g., {us_exchanges: [NYSE, NASDAQ]})

# Models Fed (Silver layer models this provider feeds)
models: []                              # e.g., [stocks, company, options]

# Metadata
category: public                        # public | commercial | self-hosted | internal
legal_entity_type:                      # vendor | municipal | county | federal | corporate
data_domains: []                        # Broad subject areas [securities, finance, housing]
data_tags: []                           # Descriptive tags [time-series, daily, market-data]
status: active                          # active | unstable | archived
bulk_download: false                    # Whether provider allows bulk downloads
last_verified:
last_reviewed:
notes:
---

## Description

What this provider is and what kind of data it exposes.

## API Notes

Base URL structure, authentication method, API key usage.

## Homelab Usage Notes

Cron jobs, ingest scripts, caching, retry behavior, recommended refresh cadence.

## Known Quirks

Schema drift, field name changes, downtime patterns, rate limit behavior, error response formats.
