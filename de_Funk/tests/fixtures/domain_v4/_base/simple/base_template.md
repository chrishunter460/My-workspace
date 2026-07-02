---
type: domain-base
model: simple_entity
version: 1.0
description: "Simple base template for testing - entity with dimensions and facts"

canonical_fields:
  - [entity_id, integer, nullable: false, description: "Primary key"]
  - [entity_name, string, nullable: false, description: "Entity name"]
  - [entity_type, string, nullable: true, description: "Type discriminator"]
  - [date_id, integer, nullable: false, description: "FK to calendar"]
  - [amount, "decimal(18,2)", nullable: true, description: "Monetary amount"]

tables:
  _dim_entity:
    type: dimension
    primary_key: [entity_id]
    unique_key: [entity_name]

    schema:
      - [entity_id, integer, false, "PK", {derived: "ABS(HASH(entity_name))"}]
      - [entity_name, string, false, "Natural key"]
      - [entity_type, string, true, "Type", {enum: [TYPE_A, TYPE_B, TYPE_C]}]
      - [created_date, date, true, "Creation date"]

    measures:
      - [entity_count, count_distinct, entity_id, "Number of entities", {format: "#,##0"}]

  _fact_events:
    type: fact
    primary_key: [event_id]
    partition_by: [date_id]

    schema:
      - [event_id, integer, false, "PK", {derived: "ABS(HASH(CONCAT(entity_id, '_', date_id)))"}]
      - [entity_id, integer, false, "FK to dim_entity", {fk: _dim_entity.entity_id}]
      - [date_id, integer, false, "FK to calendar", {fk: temporal.dim_calendar.date_id}]
      - [amount, "decimal(18,2)", true, "Amount"]
      - [category, string, true, "Event category"]

    measures:
      - [total_amount, sum, amount, "Total amount", {format: "$#,##0.00"}]
      - [event_count, count_distinct, event_id, "Number of events", {format: "#,##0"}]

subsets:
  discriminator: _dim_entity.entity_type
  pattern: wide_table
  target_table: _dim_entity
  description: "Entity types partition the wide dim_entity table"
  values:
    TYPE_A:
      extends: _base.simple.child.subset_a
      description: "Type A entities"
      filter: "entity_type = 'TYPE_A'"
    TYPE_B:
      extends: _base.simple.child.subset_b
      description: "Type B entities"
      filter: "entity_type = 'TYPE_B'"

auto_edges:
  - [date_id, temporal.dim_calendar, [date_id=date_id], many_to_one, temporal]

behaviors:
  - temporal

domain: _base
tags: [base, template, test]
status: active
---

## Simple Entity Base Template

Test fixture for domain v4 loader testing.
