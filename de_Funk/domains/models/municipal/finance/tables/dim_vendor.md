---
type: domain-model-table
table: dim_vendor
table_type: dimension
transform: aggregate
from: fact_ledger_entries
group_by: [payee]
primary_key: [vendor_id]
unique_key: [payee]

# [column, type, nullable, description, {options}]
schema:
  - [vendor_id, integer, false, "PK", {derived: "ABS(HASH(COALESCE(payee, 'UNKNOWN')))"}]
  - [vendor_name, string, false, "Display name", {derived: "payee"}]
  - [first_payment_date, date, true, "Earliest transaction", {derived: "MIN(transaction_date)", format: date}]
  - [last_payment_date, date, true, "Most recent transaction", {derived: "MAX(transaction_date)", format: date}]
  - [total_payments, "decimal(18,2)", false, "Lifetime total", {derived: "SUM(transaction_amount)", format: $}]
  - [payment_count, integer, false, "Number of ledger entries", {derived: "COUNT(*)", format: number}]
  - [entry_types, string, true, "Which entry types", {derived: "ARRAY_JOIN(COLLECT_SET(entry_type), ', ')"}]
  - [is_active, boolean, false, "Recent activity", {derived: "MAX(transaction_date) >= CURRENT_DATE - INTERVAL 2 YEAR"}]

measures:
  - [vendor_count, count_distinct, vendor_id, "Unique vendors", {format: "#,##0"}]
  - [avg_vendor_lifetime, avg, total_payments, "Avg vendor lifetime total", {format: "$#,##0.00"}]
  - [active_vendor_count, expression, "SUM(CASE WHEN is_active THEN 1 ELSE 0 END)", "Active vendors", {format: "#,##0"}]
---

## Vendor Dimension

Aggregated from **canonicalized ledger entries** (not raw bronze). Uses canonical column names: `payee`, `transaction_amount`, `transaction_date`.

### Why from fact_ledger_entries?

- Alias mapping happens once (in the source definition) — no duplicate column name translation
- Includes **both** VENDOR_PAYMENT and CONTRACT entries for a complete vendor profile
- `entry_types` column shows which types of activity each vendor has

### Enrichment Potential

This dimension could be further enriched with contract data:
```sql
-- How many contracts does this vendor hold?
-- What's their total contracted vs total paid?
```
This is handled at query time via the `contract_to_vendor` edge in the graph.
