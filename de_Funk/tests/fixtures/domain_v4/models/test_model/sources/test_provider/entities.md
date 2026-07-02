---
type: domain-model-source
source: entities
extends: _base.simple.base_template
maps_to: dim_entity
from: bronze.test_provider_entities
domain_source: "'test_provider'"

aliases:
  - [entity_id, "ABS(HASH(name))"]
  - [entity_name, name]
  - [entity_type, type_code]
  - [created_date, create_dt]
---

## Test Provider Entities Source

Maps test_provider bronze entities to dim_entity.
