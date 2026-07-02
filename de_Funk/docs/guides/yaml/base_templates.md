---
type: reference
description: "Guide for domains/_base/ — reusable base templates that domain models inherit from"
---

# Base Templates (`domains/_base/`)

> Base templates define canonical field sets that domain models inherit via `extends:`. They are the shared schema vocabulary — ensuring `company_id` means the same thing across all domains that reference a company.

## What Are Base Templates?

A base template is a markdown file in `domains/_base/` that defines:
- **Canonical fields** — standard column definitions (name, type, nullable, description)
- **Default measures** — reusable measure definitions
- **Default edges** — common join patterns

Domain models inherit these via `extends:` in their `model.md`:

```yaml
# domains/models/corporate/entity/model.md
extends: [_base.entity.company]
```

This merges the base template's fields into the domain model's tables, so `dim_company` gets all the canonical company fields without redeclaring them.

## Directory Structure

```
domains/_base/
├── _base_/
│   ├── entity.md              # Universal entity fields (id, name, status)
│   └── event.md               # Universal event fields (date_id, created_at)
├── accounting/
│   ├── chart_of_accounts.md   # Account code, type, subtype, hierarchy
│   ├── financial_event.md     # Amount, currency, fiscal_year
│   ├── financial_statement.md # Statement type, period, report fields
│   ├── fund.md                # Fund code, type, description
│   └── ledger_entry.md        # Entry id, payee, transaction fields
├── corporate/
│   └── earnings.md            # EPS, revenue, estimates
├── entity/
│   ├── company.md             # CIK, ticker, sector, industry, market_cap
│   ├── legal.md               # Legal entity fields
│   ├── municipality.md        # City/county fields, FIPS codes
│   └── organizational_entity.md # Org unit hierarchy
├── finance/
│   ├── corporate_action.md    # Dividends, splits, mergers
│   └── securities.md          # Security id, ticker, exchange, asset_type
├── geography/
│   ├── geo_location.md        # Lat, lng, address
│   └── geo_spatial.md         # Boundary id, type, code, WKT geometry
├── housing/
│   └── permit.md              # Permit number, type, status, dates
├── operations/
│   └── service_request.md     # Request id, type, status, dates
├── property/
│   ├── commercial.md          # Commercial property fields
│   ├── industrial.md          # Industrial property fields
│   ├── parcel.md              # PIN, address, class, assessed value
│   ├── residential.md         # Residential characteristics
│   └── tax_district.md        # Tax district boundaries
├── public_safety/
│   └── crime.md               # Case number, IUCR, description, location
├── regulatory/
│   └── inspection.md          # Inspection type, result, risk level
├── temporal/
│   └── calendar.md            # Date fields (year, month, quarter, weekday)
└── transportation/
    ├── traffic.md             # Congestion, speed, segment
    └── transit.md             # Station, route, ridership
```

## How Inheritance Works

### Single Inheritance

```yaml
# domains/models/temporal/model.md
extends: _base.temporal.calendar
```

The model gets all fields from `domains/_base/temporal/calendar.md`.

### Multiple Inheritance

```yaml
# domains/models/corporate/finance/model.md
extends: [_base.accounting.financial_statement, _base.corporate.earnings]
```

Fields from both bases are merged. If both define the same field, the later one wins.

### Table-Level Inheritance

Tables can also extend bases:

```yaml
# domains/models/municipal/geospatial/tables/dim_community_area.md
extends: _base.geography.geo_spatial
```

This gives `dim_community_area` the standard geographic fields (`boundary_id`, `boundary_type`, `geom_wkt`, etc.) plus any table-specific fields.

## Writing a Base Template

```yaml
# domains/_base/my_domain/my_base.md
---
type: domain-base
model: _base.my_domain.my_base
version: 1.0
description: "Canonical fields for my domain concept"

canonical_fields:
  - [my_id, integer, false, "Primary identifier", {derived: "ABS(HASH(source_key))"}]
  - [my_name, string, true, "Display name"]
  - [my_status, string, true, "Active/inactive", {enum: [active, inactive]}]
  - [date_id, integer, false, "FK to dim_calendar", {fk: temporal.dim_calendar.date_id}]
---

## My Base Template

Description of what this base represents and when to use it.
```

### Field Format

Each canonical field is an array: `[name, type, nullable, description, options]`

| Position | Required | What |
|---|---|---|
| 0 | Yes | Column name |
| 1 | Yes | Type (string, integer, double, long, boolean, date, timestamp) |
| 2 | Yes | Nullable (true/false) |
| 3 | Yes | Description |
| 4 | No | Options dict: `{derived: "SQL expr", fk: "domain.table.col", enum: [...], format: "..."}` |

## Which Models Use Which Bases

| Base | Used By |
|---|---|
| `_base.entity.company` | corporate.entity |
| `_base.entity.municipality` | municipal.entity |
| `_base.finance.securities` | securities.master, securities.stocks |
| `_base.temporal.calendar` | temporal |
| `_base.geography.geo_spatial` | geospatial, municipal.geospatial, county.geospatial |
| `_base.accounting.financial_statement` | corporate.finance |
| `_base.public_safety.crime` | municipal.public_safety |
| `_base.regulatory.inspection` | municipal.regulatory |
| `_base.operations.service_request` | municipal.operations |
| `_base.housing.permit` | municipal.housing |
| `_base.transportation.transit` | municipal.transportation |
| `_base.property.parcel` | county.property |

## Extending vs Overriding

When a domain model `extends` a base, the base fields are **merged** into the model's tables:
- Base fields come first
- Model-specific fields are added after
- If both define the same field name, the model's definition wins (override)
- Nullable fields from the base can be made non-nullable by the model

The merge is handled by `config/domain/extends.py:deep_merge()`.
