---
type: domain-model
model: test_model
version: 1.0
description: "Test domain model for v4 loader testing"
extends:
  - _base.simple.base_template
depends_on: [temporal]

storage:
  format: delta
  sources_from: sources/{entity}/
  silver:
    root: storage/silver/test/

graph:
  edges:
    - [event_to_entity, fact_events, dim_entity, [entity_id=entity_id], many_to_one, null]
    - [event_to_calendar, fact_events, temporal.dim_calendar, [date_id=date_id], many_to_one, temporal]

  paths:
    event_to_type:
      description: "Event to entity type lookup"
      steps:
        - {from: fact_events, to: dim_entity, via: entity_id}

build:
  partitions: [date_id]
  sort_by: [entity_id, date_id]
  optimize: true
  phases:
    1: { tables: [dim_entity] }
    2: { tables: [fact_events] }

measures:
  simple:
    - [entity_count, count_distinct, dim_entity.entity_id, "Number of entities", {format: "#,##0"}]
    - [total_amount, sum, fact_events.amount, "Total amount", {format: "$#,##0"}]
  computed:
    - [avg_amount_per_entity, expression, "SUM(amount) / NULLIF(COUNT(DISTINCT entity_id), 0)", "Average amount per entity", {format: "$#,##0.00"}]

views:
  view_entity_summary:
    extends: _base.simple.base_template._view_entity_summary
    assumptions:
      factor:
        source: dim_entity.entity_type
        join_on: [entity_id=entity_id]

metadata:
  domain: test
  subdomain: model
status: active
---

## Test Model

Test domain model exercising multi-file discovery, graph, build phases, measures, and views.
