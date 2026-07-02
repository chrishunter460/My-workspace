---
type: domain-base
model: fund
version: 1.0
description: "Fund dimension - fiscal accounting pools (General Fund, Special Revenue, etc.)"
extends: _base._base_.entity

# CANONICAL FIELDS
# [field_name, type, nullable: bool, description: "meaning"]
canonical_fields:
  - [fund_id, integer, nullable: false, description: "Primary key"]
  - [fund_code, string, nullable: false, description: "Fund code identifier"]
  - [fund_description, string, nullable: false, description: "Fund name/description"]
  - [fund_type, string, nullable: false, description: "GENERAL, SPECIAL_REVENUE, ENTERPRISE, CAPITAL, GRANT"]
  - [is_active, boolean, nullable: false, description: "Currently in use"]

tables:
  _dim_fund:
    type: dimension
    primary_key: [fund_id]
    unique_key: [fund_code]

    # [column, type, nullable, description, {options}]
    schema:
      - [fund_id, integer, false, "PK", {derived: "ABS(HASH(fund_code))"}]
      - [fund_code, string, false, "Natural key"]
      - [fund_description, string, false, "Display name"]
      - [fund_type, string, false, "Classification", {enum: [GENERAL, SPECIAL_REVENUE, ENTERPRISE, CAPITAL, GRANT, DEBT_SERVICE, OTHER]}]
      - [is_active, boolean, false, "Currently used", {default: true}]

    measures:
      - [fund_count, count_distinct, fund_id, "Number of funds", {format: "#,##0"}]

behaviors: []  # Pure entity — classification dimension only

domain: accounting
tags: [base, template, accounting, fund]
status: active
---

## Fund Base Template

Fiscal accounting pools. Government entities use fund accounting to track restricted and unrestricted resources separately.

### Fund Types

| Type | Description | Example |
|------|-------------|---------|
| GENERAL | Unrestricted operating | Corporate Fund |
| SPECIAL_REVENUE | Legally restricted | Motor Fuel Tax Fund |
| ENTERPRISE | Self-sustaining operations | Water Fund, Airport Fund |
| CAPITAL | Capital projects | Bond proceeds |
| GRANT | External grants | CDBG, federal grants |
| DEBT_SERVICE | Debt repayment | GO Bond Fund |

### Usage

```yaml
extends: _base.accounting.fund
```
