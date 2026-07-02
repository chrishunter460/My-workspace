---
type: domain-model-table
table: fact_traffic
extends: _base.transportation.traffic._fact_traffic
table_type: fact
primary_key: [segment_id, timestamp]
optional: true

schema:
  - [segment_id, string, false, "Traffic segment ID"]
  - [timestamp, timestamp, true, "Measurement timestamp"]
  - [speed, double, true, "Average speed", {format: decimal2}]
  - [congestion_level, string, true, "Congestion level"]
---

## Traffic Fact Table

Traffic congestion data by segment.
