---
type: domain-model-table
table: dim_contract
table_type: dimension
primary_key: [contract_id]
unique_key: [contract_number]

# Base columns from bronze (source-specific fields not in canonical ledger schema)
# [column, type, nullable, description, {options}]
schema:
  - [contract_id, integer, false, "PK", {derived: "ABS(HASH(contract_number))"}]
  - [contract_number, string, false, "Natural key"]
  - [specification_number, string, true, "Specification reference"]
  - [vendor_name, string, true, "Vendor on contract"]
  - [vendor_id, integer, true, "FK to dim_vendor", {fk: dim_vendor.vendor_id, derived: "ABS(HASH(COALESCE(vendor_name, 'UNKNOWN')))"}]
  - [description, string, true, "Contract description"]
  - [contract_description, string, true, "Contract description (unique alias for pivot)", {derived: "description"}]
  - [department, string, true, "Awarding department"]
  - [department_id, integer, true, "FK to dim_department", {fk: dim_department.org_unit_id, derived: "ABS(HASH(COALESCE(department, 'UNKNOWN')))"}]
  - [procurement_type, string, true, "Procurement method"]
  - [award_amount, "decimal(18,2)", true, "Contract award value", {format: $}]
  - [start_date, date, true, "Contract start", {format: date}]
  - [end_date, date, true, "Contract end", {format: date}]
  - [is_active, boolean, false, "Currently active", {derived: "end_date >= CURRENT_DATE OR end_date IS NULL"}]

measures:
  - [contract_count, count_distinct, contract_id, "Number of contracts", {format: "#,##0"}]
  - [total_award_amount, sum, award_amount, "Total award value", {format: "$#,##0.00"}]
---

## Contract Dimension

Contracts are obligations, not ledger entries. Sourced directly from bronze — contract-specific columns like `specification_number`, `procurement_type`, `start_date`, `end_date` don't belong on the ledger.

### Example Query

```sql
-- Active contracts by department
SELECT department, COUNT(*) as contracts, SUM(award_amount) as total_awarded
FROM dim_contract
WHERE is_active = true
GROUP BY department
ORDER BY total_awarded DESC;
```
