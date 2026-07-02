---
type: domain-model-table
table: fact_events
extends: _base.simple.base_template._fact_events
table_type: fact
primary_key: [event_id]
partition_by: [date_id]

additional_schema:
  - [source_system, string, true, "Which system generated this event"]
  - [processed_flag, boolean, true, "Whether event has been processed", {default: false}]

derivations:
  event_id: "ABS(HASH(CONCAT(entity_id, '_', event_date)))"
  date_id: "CAST(DATE_FORMAT(event_date, 'yyyyMMdd') AS INT)"

measures:
  - [total_amount, sum, amount, "Total event amount", {format: "$#,##0.00"}]
  - [avg_amount, avg, amount, "Average event amount", {format: "$#,##0.00"}]
  - [event_count, count_distinct, event_id, "Number of events", {format: "#,##0"}]
---

## Events Fact Table

Test fact table with extends, additional_schema, and derivations.
