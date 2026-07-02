---
type: domain-model-table
table: fact_payments
extends: _base.accounting.ledger_source._ledger_source
table_type: fact
primary_key: [entry_id]
partition_by: [date_id]
persist: true

# Sources auto-discovered: any sources/*.md with maps_to: payments

additional_schema:
  - [contract_number, string, true, "Contract reference (null if no contract)"]
  - [voucher_number, string, true, "Payment voucher number"]
  - [vendor_id, integer, true, "FK to dim_vendor", {fk: dim_vendor.vendor_id, derived: "ABS(HASH(COALESCE(payee, 'UNKNOWN')))"}]
  - [department_id, integer, true, "FK to dim_department", {fk: dim_department.org_unit_id, derived: "ABS(HASH(COALESCE(organizational_unit, 'UNKNOWN')))"}]

measures:
  - [payment_total, sum, transaction_amount, "Total payments", {format: "$#,##0.00"}]
  - [payment_count, count_distinct, entry_id, "Number of payments", {format: "#,##0"}]
  - [vendor_count, count_distinct, payee, "Unique vendors", {format: "#,##0"}]
---

## Payments

Silver table for vendor payment transactions. Extends the ledger source base with payment-specific columns (`contract_number`, `voucher_number`). The `source_id` (voucher_number) is the natural key that links back from `fact_ledger_entries`.

### Contract Linkage

Payments with a `contract_number` can join to `dim_contract` via the graph edge. The resolver finds: `fact_ledger_entries → payments → dim_contract` automatically using `source_id` as the first hop.
