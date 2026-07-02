---
type: domain-model-table
table: dim_entity
extends: _base.simple.base_template._dim_entity
table_type: dimension
primary_key: [entity_id]
unique_key: [entity_name]

additional_schema:
  - [region_code, string, true, "Regional classification"]
  - [priority, integer, true, "Entity priority level"]

enrich:
  - {from: fact_events, join: [entity_id=entity_id], columns: [{name: total_amount, agg: "SUM(amount)"}, {name: event_count, agg: "COUNT(DISTINCT event_id)"}]}

derivations:
  entity_id: "ABS(HASH(name))"
  entity_name: "name"
  entity_type: "type_code"

measures:
  - [type_a_count, count_distinct, entity_id, "Type A entities", {format: "#,##0", filters: ["entity_type = 'TYPE_A'"]}]
  - [type_b_count, count_distinct, entity_id, "Type B entities", {format: "#,##0", filters: ["entity_type = 'TYPE_B'"]}]
---

## Entity Dimension

Test dimension table with extends, additional_schema, derivations, and enrich.
