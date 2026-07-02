---
type: domain-base
model: subset_a
version: 1.0
description: "Type A subset - auto-absorbed into parent wide table"
extends: _base.simple.base_template
subset_of: _base.simple.base_template
subset_value: TYPE_A

canonical_fields:
  - [field_a1, string, nullable: true, description: "Type A specific field 1"]
  - [field_a2, integer, nullable: true, description: "Type A specific field 2"]

measures:
  - [avg_field_a2, avg, field_a2, "Average field A2", {format: "#,##0.0"}]

domain: _base
tags: [base, template, subset, test]
status: active
---

## Subset A

Type A specific fields. Auto-absorbed into parent dim_entity.
