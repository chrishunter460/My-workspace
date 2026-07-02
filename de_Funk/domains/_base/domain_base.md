---
type: reference
model: domain_base_overview
version: 1.0
description: "Overview of the domain-base template system"
---

## Domain Base System

The `_base/` directory contains reusable templates that define **what** canonical schemas look like. They are never materialized directly - only inherited by concrete domain-models.

### Template Hierarchy

```
_base_/                          ROOT ABSTRACTIONS
  entity.md                      Any identifiable thing
  event.md                       Any timestamped occurrence

accounting/                      FINANCIAL ACCOUNTING
  chart_of_accounts.md           Account classification (extends entity)
  fund.md                        Fiscal accounting pools (extends entity)
  financial_event.md             Generic financial occurrence (extends event) ← NPV, spending_velocity
    ledger_entry.md              Payments/payroll/contracts (extends financial_event)
      financial_statement.md     Periodic reporting by chart of accounts (extends ledger_entry)

corporate/                       CORPORATE REPORTING
  earnings.md                    EPS reports and analyst estimates (extends event)

finance/                         MARKET FINANCE
  securities.md                  Tradable securities (extends entity)
  corporate_action.md            Dividends, splits, mergers (extends event)

entity/                          ORGANIZATIONAL
  legal.md                       Legal entities (extends entity)
  company.md                     Public/private corporations (extends legal)
  municipality.md                Cities, counties, districts (extends legal)
  organizational_entity.md       Departments, divisions (extends entity)

geography/                       SPATIAL
  geo_location.md                Point locations (extends entity)
  geo_spatial.md                 Boundaries/polygons (extends entity)

property/                        REAL ESTATE
  parcel.md                      Land records/assessments (extends entity)

public_safety/                   LAW ENFORCEMENT
  crime.md                       Crime incidents (extends event)

housing/                         CONSTRUCTION
  permit.md                      Building permits (extends event)

operations/                      CONSTITUENT SERVICES
  service_request.md             311-type requests (extends event)

regulatory/                      COMPLIANCE
  inspection.md                  Inspections/violations/licenses (extends event)

transportation/                  TRANSIT & TRAFFIC
  transit.md                     Public transit stations/ridership (extends event)
  traffic.md                     Road segment speed/congestion (extends event)

temporal/                        TIME
  calendar.md                    Daily calendar dimension
```

### Design Principles

1. **Base is pure** - Only canonical fields, never source-specific names
2. **Tabular format** - canonical_fields and edges use array notation to reduce nesting
3. **Nullable contract** - Fields marked `nullable: true` may be null; domain-models must handle this
4. **Schema is authoritative** - Derived expressions live in table schema, not graph nodes
5. **Integer PKs** - All surrogate keys are `ABS(HASH(...))` integers
6. **date_id everywhere** - All facts FK to `temporal.dim_calendar` via integer date_id
7. **legal_entity_id** - All event facts FK to owning legal entity (company, municipality, county)
8. **location_id** - All event facts optionally FK to `geo_location._dim_location` (nullable — not all events have geography)
9. **Shared measures** - Account-type measures on financial_statement work for corporate AND municipal models
10. **auto_edges** - Standard FK edges (date_id→calendar, location_id→location) are declared once in root event base and auto-applied to all fact tables

### Canonical Fields Format

```yaml
canonical_fields:
  - [field_name, type, nullable: bool, description: "meaning"]
```

### auto_edges (Inherited FK Edges)

Declared once in root event base, applied to every fact with matching columns:

```yaml
auto_edges:
  - [date_id, temporal.dim_calendar, [date_id=date_id], many_to_one, temporal]
  - [location_id, geo_location._dim_location, [location_id=location_id], many_to_one, geo_location]
```

Child bases only declare domain-specific edges (facility, crime_type, etc.). Facts with non-standard date columns (`sale_date_id`, `report_date_id`) keep explicit edges.

### Explicit Edge Format

```yaml
graph:
  edges:
    # [edge_name, from, to, on, type, cross_model]
    - [sale_to_calendar, _fact_sales, temporal.dim_calendar, [sale_date_id=date_id], many_to_one, temporal]
```

### How Models Use Bases

```yaml
# In models/municipal/chicago/finance.md
type: domain-model
extends: _base.accounting.ledger_entry

# Aliases map source fields to canonical fields
aliases:
  - ["vendor_name", payee]
  - ["amount", transaction_amount]

# Sources handle multi-endpoint unions
sources:
  - [vendor_payments, bronze.chicago.chicago_payments, VENDOR_PAYMENT]
  - [employee_salaries, bronze.chicago.chicago_salaries, PAYROLL]
```
