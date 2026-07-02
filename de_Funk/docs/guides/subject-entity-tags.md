# Field: subject_entity_tags

## Purpose
The `subject_entity_type` field answers the question:

> "Who or what is this data describing?"

It represents the **entities that the dataset is about**, which may differ from the publisher of the endpoint. This allows you to clearly separate:

- **Publisher (`legal_entity_type`)** → Who operates or provides the API  
- **Subject (`subject_entity_type`)** → Who or what the data describes

This is essential for datasets where the **publisher and the entities described are not the same**, e.g., a city publishing contracts about corporate vendors.

---

## Legal subject entities

| Type        | Description | Example |
|------------|------------|---------|
| municipal   | City or municipal authority as the subject of the data | City departments, local councils |
| county      | County government | County election boards, county courts |
| state       | State government | State agencies or departments |
| federal     | National government | Federal funding programs, national statistics |
| corporate   | Private company | Vendors, contractors, corporations referenced in contracts |
| nonprofit   | NGO or foundation | Charities or nonprofit recipients of grants |
| individual  | Single person / citizen | Residents, patients, survey participants |
| academic   | Universities or research institutions | Research outputs, university datasets |
| tribal      | Tribal governments | Tribal authorities, reservations |
| regional   | Multi-county or regional authorities | MPOs, regional transit authorities |

## Non-Legal Subject Entities

| Type | Description | Example |
|------|------------|---------|
| property | Physical asset or parcel; the row represents a building, lot, or other tangible object | Building violations dataset where each row is a building; property tax assessments |
| infrastructure | Physical systems or assets that provide services; the row represents the asset itself rather than ownership | Roads, bridges, water mains, electrical substations |
| facility | A location or building used for a service; often organizational or public service related | Library branches, schools, hospitals, government offices |
| geographic-area | Abstract region or spatial unit; the row represents a defined area rather than a physical asset | Census tract, zoning district, ZIP code, municipal boundary |



---

## Examples

### 1. City Budget / Appropriations
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
