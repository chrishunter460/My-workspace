---
type: domain-model-source
source: events
extends: _base.simple.base_template
maps_to: fact_events
from: bronze.test_provider_events
domain_source: "'test_provider'"

aliases:
  - [event_id, "ABS(HASH(CONCAT(entity_id, '_', event_date)))"]
  - [entity_id, src_entity_id]
  - [date_id, "CAST(DATE_FORMAT(event_date, 'yyyyMMdd') AS INT)"]
  - [amount, event_amount]
  - [category, event_category]
  - [source_system, "'test_provider'"]
---

## Test Provider Events Source

Maps test_provider bronze events to fact_events.
