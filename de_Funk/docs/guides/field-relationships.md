

# Field Relationships: domain, data_tags, legal_entity_type

## How the fields interact

| Field | Purpose | Typical Overlap / Interaction |
|-------|---------|-------------------------------|
| domain | What is the data about? | Orthogonal to publisher; multiple endpoints across different publishers can share the same domain |
| legal_entity_type | Who publishes the data | Orthogonal to domain; multiple domains can be published by same entity type |
| subject_tags | Descriptive qualifiers | Meant for defining who the data is about and can overlap with legal entity, but mostly for discovery of relationships |
| data_tags | Descriptive qualifiers | Can overlap with domain (budget) or publisher (public), but mostly for filtering and discovery |

---

## Example: City Payments

```yaml
domain: finance
legal_entity_type:
  - municipal          # publisher
subject_entity_type:
  - municipal          # city departments
  - corporate          # vendors the city pays
data_tags:
  - budget
  - appropriations
  - public
  - time-series
