---
type: domain-model-source
source: payments
extends: _base.accounting.ledger_entry
maps_to: fact_payments
from: bronze.chicago_payments
entry_type: VENDOR_PAYMENT
domain_source: "'chicago'"
aliases:
  - [legal_entity_id, "ABS(HASH(CONCAT('CITY_', 'Chicago')))"]
  - [entry_id, "ABS(HASH(CONCAT('VENDOR_PAYMENT', '_', voucher_number)))"]
  - [date_id, "CAST(DATE_FORMAT(check_date, 'yyyyMMdd') AS INT)"]
  - [source_id, voucher_number]
  - [payee, vendor_name]
  - [transaction_amount, amount]
  - [transaction_date, check_date]
  - [organizational_unit, department]
  - [expense_category, "null"]
  - [fund_code, "null"]
  - [contract_number, contract_number]
  - [voucher_number, voucher_number]
  - [description, "null"]
  - [account_code, "CONCAT('ACTUAL_', COALESCE(department, 'UNCLASSIFIED'))"]
  - [account_id, "ABS(HASH(CONCAT('ACTUAL_', COALESCE(department, 'UNCLASSIFIED'))))"]
---

## Payments Source

Chicago vendor payments. Data older than 2 years summarized by vendor/contract.
