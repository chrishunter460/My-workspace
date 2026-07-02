---
type: domain-base
model: ledger_source
version: 1.0
description: "Base template for silver ledger source tables. Extends ledger_entry with source-specific columns."
extends: _base.accounting.ledger_entry

# Silver ledger source tables are persisted intermediate tables that feed
# into fact_ledger_entries. They carry the full canonical ledger schema
# plus source-specific columns (contract_number, title_code, etc.).
#
# The ledger's source_id is the natural key back to the source table,
# enabling multi-hop joins via the graph resolver without denormalizing
# source-specific columns onto the fact table.

tables:
  _ledger_source:
    type: fact
    primary_key: [entry_id]
    partition_by: [date_id]

    # Canonical columns — same as _fact_ledger_entries
    schema:
      - [entry_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT(entry_type, '_', source_id)))"}]
      - [legal_entity_id, integer, true, "FK to owning legal entity"]
      - [date_id, integer, false, "FK to calendar", {fk: temporal.dim_calendar.date_id}]
      - [entry_type, string, false, "Source discriminator"]
      - [domain_source, string, false, "Origin domain"]
      - [source_id, string, false, "Original source ID"]
      - [payee, string, false, "Who received payment"]
      - [transaction_amount, "decimal(18,2)", false, "Amount"]
      - [transaction_date, date, false, "Transaction date"]
      - [organizational_unit, string, true, "Department"]
      - [expense_category, string, true, "Classification"]
      - [fund_code, string, true, "Fund code"]
      - [description, string, true, "Transaction description"]
      - [account_code, string, true, "Account code"]
      - [account_id, integer, true, "FK to chart of accounts"]
---

## Ledger Source Base

Silver ledger source tables extend this template. Each source adds its own columns via `additional_schema`. The canonical columns flow into `fact_ledger_entries` via union; source-specific columns stay on the source table and are reachable through the graph resolver using `source_id` as the join key.
