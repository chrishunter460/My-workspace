---
type: domain-model-source
source: contracts
maps_to: dim_contract
from: bronze.chicago_contracts
domain_source: "'chicago'"
aliases:
  - [contract_id, "ABS(HASH(contract_number))"]
  - [contract_number, contract_number]
  - [specification_number, specification_number]
  - [vendor_name, vendor_name]
  - [vendor_id, "ABS(HASH(COALESCE(vendor_name, 'UNKNOWN')))"]
  - [description, description]
  - [department, department]
  - [department_id, "ABS(HASH(COALESCE(department, 'UNKNOWN')))"]
  - [procurement_type, procurement_type]
  - [award_amount, "CAST(award_amount AS DECIMAL(18,2))"]
  - [start_date, start_date]
  - [end_date, end_date]
---

## Contracts Source

Chicago city contracts — obligations, not ledger entries. Sourced directly into `dim_contract` as a reference dimension with award amounts, vendor info, and contract lifecycle dates.
