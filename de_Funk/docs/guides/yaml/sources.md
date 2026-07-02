---

type: reference
description: "Guide for source files and hashing conventions"
---

> **Implementation Status**: All features fully implemented.


## sources Guide

Source files map bronze (raw ingested) data to a domain model's canonical schema. Each source file represents one bronze endpoint feeding one target table.

### Source File Structure

```yaml
---

type: domain-model-source
source: payments                          # Source identifier
extends: _base.accounting.ledger_entry    # Base template this source maps to
maps_to: fact_ledger_entries              # Target table in the model
from: bronze.chicago_payments             # Bronze table reference
entry_type: VENDOR_PAYMENT                # Discriminator value (if applicable)
domain_source: "'chicago'"                # Origin domain (required for federation)

# [canonical_field, source_expression]
aliases:
  - [source_id, voucher_number]
  - [payee, vendor_name]
  - [transaction_amount, amount]
---


## Payments
Description of the data source.
```

### Required Keys

| Key | Type | Description |
|-----|------|-------------|
| `type` | string | Always `domain-model-source` |
| `source` | string | Source identifier (e.g., `payments`) |
| `extends` | string | Base template this source maps to |
| `maps_to` | string | Target table in the model |
| `from` | string | Bronze table reference (e.g., `bronze.chicago_payments`) |
| `domain_source` | string | Origin domain literal (e.g., `"'chicago'"`) |
| `aliases` | list | `[canonical_field, source_expression]` pairs |

### Optional Keys

| Key | Type | Description |
|-----|------|-------------|
| `entry_type` | string | Discriminator for ledger entries (e.g., `VENDOR_PAYMENT`, `PAYROLL`, `CONTRACT`) |
| `event_type` | string | Discriminator for event-based sources (e.g., `APPROPRIATION`, `REVENUE`) |
| `transform` | string | `unpivot` for wide-to-long transformations |
| `unpivot_aliases` | list | Column-to-account mappings for unpivot sources |

---


### Alias Conventions

Aliases map source (bronze) columns to canonical (silver) columns:

```yaml
aliases:
  # Direct column mapping
  - [canonical_name, bronze_column_name]

  # Expression mapping
  - [date_id, "CAST(DATE_FORMAT(date, 'yyyyMMdd') AS INT)"]

  # Literal value
  - [is_active, "true"]

  # Hash-derived surrogate key
  - [entry_id, "ABS(HASH(CONCAT('VENDOR_PAYMENT', '_', voucher_number)))"]
```

**Rules:**
- Left side is always the canonical column name (from the base template)
- Right side is a SQL expression evaluated against the bronze table
- Unmapped canonical fields get `NULL` (valid for nullable fields)
- `TBD` is acceptable for nullable fields where the mapping is not yet determined

---


### Surrogate Key Hashing Convention

All surrogate primary keys in the system use the pattern:

```
ABS(HASH(CONCAT(prefix, '_', natural_key)))
```

This produces a deterministic integer PK from a string natural key.

#### Why This Pattern?

1. **Deterministic**: Same inputs always produce the same hash, enabling idempotent builds (rebuild = same PKs)
2. **Integer output**: All PKs are integers for join efficiency (faster than string joins)
3. **Prefix prevents collisions**: Different entity types use different prefixes, so `HASH('CITY_Chicago')` != `HASH('COMPANY_Chicago')` even though both have "Chicago"
4. **Federation-safe**: When UNIONing rows from different sources, prefixed hashes ensure PKs don't collide

#### Standard Prefix Patterns

| Domain | Prefix | Example | Result |
|--------|--------|---------|--------|
| **Company entity** | `COMPANY_` | `ABS(HASH(CONCAT('COMPANY_', ticker)))` | `company_id` |
| **Municipal entity** | `CITY_` | `ABS(HASH(CONCAT('CITY_', 'Chicago')))` | `municipality_id` |
| **County entity** | `COUNTY_` | `ABS(HASH(CONCAT('COUNTY_', 'Cook County')))` | `municipality_id` |
| **Community area** | `CHICAGO_CA_` | `ABS(HASH(CONCAT('CHICAGO_CA_', area_number)))` | `community_area_id` |
| **Ward** | `CHICAGO_WARD_` | `ABS(HASH(CONCAT('CHICAGO_WARD_', ward_number)))` | `ward_id` |
| **Patrol district** | `CHICAGO_DIST_` | `ABS(HASH(CONCAT('CHICAGO_DIST_', dist_num)))` | `district_id` |
| **Patrol beat** | `CHICAGO_BEAT_` | `ABS(HASH(CONCAT('CHICAGO_BEAT_', beat_num)))` | `beat_id` |
| **Security** | (no prefix) | `ABS(HASH(ticker))` | `security_id` |
| **Ledger entry** | `entry_type` value | `ABS(HASH(CONCAT('VENDOR_PAYMENT', '_', voucher_number)))` | `entry_id` |
| **Event** | `event_type + source_id` | `ABS(HASH(CONCAT(event_type, '_', source_id)))` | `event_id` |

#### Prefix Naming Convention

- **Entity prefixes**: `{ENTITY_TYPE}_` (e.g., `COMPANY_`, `CITY_`, `COUNTY_`)
- **Geographic prefixes**: `{CITY}_{GEO_TYPE}_` (e.g., `CHICAGO_CA_`, `CHICAGO_WARD_`)
- **Transaction prefixes**: Use the `entry_type` discriminator value (e.g., `VENDOR_PAYMENT`, `PAYROLL`)
- **Event prefixes**: Use the `event_type` discriminator value

#### When Source Lacks a Natural Key

If the bronze data has a synthetic ID (e.g., auto-increment), cast it:

```yaml
aliases:
  - [violation_id, "ABS(HASH(CAST(id AS STRING)))"]
```

#### Composite Keys

For entities identified by multiple columns:

```yaml
aliases:
  - [crime_type_id, "ABS(HASH(CONCAT(iucr, '_', COALESCE(fbi_code, 'UNK'))))"]
  - [earnings_id, "ABS(HASH(CONCAT(legal_entity_id, '_', report_date_id)))"]
```

---


### Discriminator Keys

Source files use discriminator keys to identify the type of record being loaded. These are injected as literal values into the SELECT.

| Key | Used By | Example Values |
|-----|---------|---------------|
| `entry_type` | Ledger entries | `VENDOR_PAYMENT`, `PAYROLL`, `CONTRACT` |
| `event_type` | Budget/financial events | `APPROPRIATION`, `REVENUE`, `POSITION` |

The discriminator is used in:
1. **PK generation**: `ABS(HASH(CONCAT(entry_type, '_', source_key)))`
2. **Filtering**: `WHERE entry_type = 'VENDOR_PAYMENT'`
3. **Computed measures**: `SUM(CASE WHEN entry_type = 'PAYROLL' THEN amount ELSE 0 END)`

---


### domain_source Key

Every source declares `domain_source:` as a top-level key with a SQL literal string:

```yaml
domain_source: "'chicago'"
```

This is NOT a column alias — it's metadata about the source. The loader injects it as a literal column in the SELECT. It must be a SQL string literal (wrapped in single quotes inside double quotes).

Federation uses `domain_source` as the `union_key` to identify which source each row came from in UNION views.

---


### Multiple Sources → One Table

Multiple source files can feed the same target table via `maps_to:`. The loader unions them automatically:

```yaml
# payments.md                    # contracts.md
maps_to: fact_ledger_entries     maps_to: fact_ledger_entries
entry_type: VENDOR_PAYMENT       entry_type: CONTRACT
```

Both produce rows in `fact_ledger_entries` with different `entry_type` discriminators. Hash-based PKs with the `entry_type` prefix ensure no collisions.

---


### Adding a New Source

1. Create a new `.md` file in the model's `sources/` directory
2. Set `maps_to:` to the target table
3. Map all required canonical fields in `aliases:`
4. Set nullable fields to `TBD` or `NULL` if the source lacks them
5. No changes needed to `model.md` — the loader discovers sources automatically
