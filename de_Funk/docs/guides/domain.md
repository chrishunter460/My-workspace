# Field: domain

## Purpose
The `domain` field answers the question:

> "What is this data about?"

It represents the **subject matter** of the dataset or API endpoint, not who publishes it. Domains are orthogonal to publisher type (`legal_entity_type`) and descriptive tags (`data_tags`).

---

## Recommended Values

Most use one of the following. Adding additional domains is the responsibility of the data governance workgroup

| Domain | Explanation |
|--------|------------|
| finance | Budgets, appropriations, spending, tax records |
| public-health | Public health stats, hospital data, disease tracking |
| transportation | Traffic counts, ridership, transit schedules |
| environment | Weather, pollution, energy, water quality |
| housing | Property, zoning, building permits |
| education | School statistics, enrollments, testing |
| public-safety | Crime stats, fire reports, emergency calls |
| operational | Inspection throughput metrics, Permit processing time, staffing levels |
| economic | Production, growth, markets, employment, prices |
| infrastructure | Assets, condition, capacity|
| regulatory | Rules, compliance, violations, enforcement| 
| demographic | Population, households, migration| 
| geospatial | Spatial classification, mapping, boundaries|
| culture | Museums, arts funding, events, tourism |
| elections | voter registration, turnout, precinct results| 
| justice | court cases, filings, dispositions |
| social-services | SNAP, Homelessness services, child welfare |
| energy | grid load, electricity generation, renewables |

---

## Rules of Thumb
- Use **domain** to classify the *subject*, not the publisher.
- Multiple endpoints across different publishers can share the same domain.
- Avoid free-text variants like "city finance"; standardize to `finance`.

---

## Dataview Example

Retrieve all finance endpoints:

```dataview
LIST
FROM "de'funk/APIs/Endpoints"
WHERE domain = "finance"
