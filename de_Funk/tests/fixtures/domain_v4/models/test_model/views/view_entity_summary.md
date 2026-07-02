---
type: domain-model-view
view: view_entity_summary
view_type: rollup
from: fact_events
grain: [entity_id, category]
description: "Entity-level event summary"

schema:
  - [entity_id, integer, false, "Entity"]
  - [category, string, false, "Event category"]
  - [event_count, integer, false, "Number of events", {derived: "COUNT(DISTINCT event_id)"}]
  - [total_amount, "decimal(18,2)", false, "Total amount", {derived: "SUM(amount)"}]
  - [avg_amount, "decimal(18,2)", false, "Average amount", {derived: "AVG(amount)"}]

measures:
  - [grand_total, sum, total_amount, "Grand total amount", {format: "$#,##0.00"}]

status: active
---

## Entity Summary View

Rollup view aggregating events to entity + category level.
