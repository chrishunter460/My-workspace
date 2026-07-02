---
type: domain-base
model: subset_b
version: 1.0
description: "Type B subset - auto-absorbed into parent wide table"
extends: _base.simple.base_template
subset_of: _base.simple.base_template
subset_value: TYPE_B

canonical_fields:
  - [field_b1, double, nullable: true, description: "Type B specific field 1"]
  - [field_b2, string, nullable: true, description: "Type B specific field 2"]
  - [field_b3, integer, nullable: true, description: "Type B specific field 3"]

measures:
  - [avg_field_b1, avg, field_b1, "Average field B1", {format: "#,##0.00"}]
  - [total_field_b3, sum, field_b3, "Total field B3", {format: "#,##0"}]

domain: _base
tags: [base, template, subset, test]
status: active
---

## Subset B

Type B specific fields. Auto-absorbed into parent dim_entity.
