---

type: reference
description: "Step-by-step guide for onboarding a new data source into an existing model"
---

> **Implementation Status**: All features fully implemented.


## Source Onboarding Guide

How to add a new data source (bronze table) to an existing domain model. For source file syntax details, see `sources.md`.

---


### Prerequisites

Before starting, you need:

1. **A bronze table** with ingested data (e.g., `bronze.new_city_payments`)
2. **An existing model** that the source feeds into (e.g., `municipal/finance`)
3. **The base template** the model extends (e.g., `_base.accounting.ledger_entry`)

---


### Phase 1: Identify the Target Table

Determine which table in the model your source maps to.

```
Q: Is this the same kind of data as an existing source?
  YES → Use the same maps_to table (e.g., fact_ledger_entries)
  NO  → You may need a new table definition first (see tables.md)
```

Check `canonical_fields` in the base template to understand what columns are expected.

---


### Phase 2: Create the Source File

Create a new `.md` file in the model's `sources/` directory:

```
models/
  municipal/
    sources/
      {entity}/
        finance/
          payments.md          # existing
          new_source.md        # ← create this
```

Minimal template:

```yaml
---

type: domain-model-source
source: new_source
extends: _base.accounting.ledger_entry
maps_to: fact_ledger_entries
from: bronze.new_city_payments
entry_type: NEW_TYPE
domain_source: "'new_city'"

aliases:
  # Required canonical fields
  - [entry_id, "ABS(HASH(CONCAT('NEW_TYPE', '_', source_pk)))"]
  - [legal_entity_id, "ABS(HASH(CONCAT('CITY_', 'New City')))"]
  - [date_id, "CAST(DATE_FORMAT(payment_date, 'yyyyMMdd') AS INT)"]
  - [source_id, source_pk]
  - [transaction_amount, amount_column]
  - [transaction_date, payment_date]

  # Fields not available from this source
  - [expense_category, "null"]
  - [fund_code, "null"]
  - [contract_number, "null"]
---


## New Source

Description of where this data comes from and any caveats.
```

---


### Phase 3: Map Aliases

For each canonical field in the base template:

| Scenario | Alias Value |
|----------|-------------|
| Direct column match | `bronze_column_name` |
| Needs transformation | `"CAST(DATE_FORMAT(col, 'yyyyMMdd') AS INT)"` |
| Literal value | `"'FIXED_VALUE'"` |
| Not available, nullable | `"null"` |
| Not available, non-nullable | `"'UNKNOWN'"` or `COALESCE(col, 'UNKNOWN')` |
| Not yet mapped | `TBD` (acceptable for nullable fields during development) |

**Key rules:**
- Every non-nullable canonical field MUST have a real alias (not `null` or `TBD`)
- Hash-based PKs must use the `entry_type` or `event_type` prefix to prevent collisions across source unions
- `domain_source` must be a SQL string literal: `"'city_name'"`

---


### Phase 4: Verify Edges

Check that your new rows will join correctly through the model's graph edges:

1. **date_id**: Does your date expression produce valid YYYYMMDD integers?
2. **legal_entity_id**: Does the hash match the entity dimension's PK derivation?
3. **Dimension FKs**: Will vendor_id, department_id, etc. resolve to existing dimension rows?

For new dimension values (vendors, departments not yet in the dimension):
- If the dimension uses `transform: distinct` or `enrich:`, new values are auto-discovered
- If the dimension is static (`static: true`), you'll need to add seed data

---


### Phase 5: Test

No changes to `model.md` are needed — the loader discovers sources from the `sources_from:` directory automatically.

Verification checklist:
- [ ] Source file is valid YAML front matter
- [ ] All non-nullable canonical fields have aliases
- [ ] PK derivation uses the correct prefix (`entry_type` or `event_type`)
- [ ] `domain_source` is set (required for federation)
- [ ] Date expressions produce valid YYYYMMDD integers
- [ ] Entity hash matches the entity dimension's derivation pattern

---


### Worked Example: Adding Detroit Payments

Goal: Add Detroit vendor payment data to `municipal/finance`.

**Step 1**: Detroit already has a bronze table: `bronze.detroit_vendor_payments`

**Step 2**: Create `models/municipal/sources/detroit/finance/payments.md`

**Step 3**: Map aliases:

```yaml
---

type: domain-model-source
source: detroit_payments
extends: _base.accounting.ledger_entry
maps_to: fact_ledger_entries
from: bronze.detroit_vendor_payments
entry_type: VENDOR_PAYMENT
domain_source: "'detroit'"

aliases:
  - [legal_entity_id, "ABS(HASH(CONCAT('CITY_', 'Detroit')))"]
  - [entry_id, "ABS(HASH(CONCAT('VENDOR_PAYMENT', '_', payment_id)))"]
  - [date_id, "CAST(DATE_FORMAT(payment_date, 'yyyyMMdd') AS INT)"]
  - [source_id, payment_id]
  - [payee, vendor_name]
  - [transaction_amount, total_amount]
  - [transaction_date, payment_date]
  - [organizational_unit, department_name]
  - [expense_category, account_category]
  - [fund_code, fund_number]
  - [contract_number, "null"]
  - [description, payment_description]
---


## Detroit Payments

City of Detroit vendor payments from Open Data portal.
```

**Step 4**: Verify `legal_entity_id` hash matches what the `dim_municipality` dimension expects for Detroit.

**Step 5**: Build and verify rows appear in `fact_ledger_entries` with `domain_source = 'detroit'`.
