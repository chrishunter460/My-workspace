# Field: legal_entity_type

## Purpose
`legal_entity_type` answers the question:

> "Who publishes or owns this data?"

It replaces the old `government_level` field to unify **governments, corporations, nonprofits, and individuals** under a single property.

---

## Recommended Values

| Type | Description | Examples |
|------|------------|---------|
| municipal | City, town, or municipal authority | City budget, local crime stats |
| county | County government | County property records |
| state | State agencies | Department of transportation, public health |
| federal | National government | Census, Federal Reserve, NOAA |
| corporate | Private company | SEC filings, corporate sensor data |
| nonprofit | NGO or foundation | Charity data, public interest datasets |
| individual | Person | Personal weather logs, self-collected IoT data |
| academic | Universities / research institutions | Research datasets, open data portals |
| tribal | Tribal governments | Tribal census, land records |
| regional | Multi-county authorities or MPOs | Regional transit or planning agencies |

---

## Rules of Thumb
- If the publisher can **enforce law, collect taxes, or provide public services**, it’s a government type (municipal, county, state, federal, tribal, regional).
- If it’s a **private entity**, choose corporate, nonprofit, individual, or academic.
- Always separate **publisher type** from **domain** or **tags**.
- Multiple types can be listed if joint ownership exists.

---

## Dataview Example

Retrieve all municipal finance datasets:

```dataview
TABLE domain, length(rows) AS "Endpoint Count"
FROM "de'funk/APIs/Endpoints"
GROUP BY legal_entity_type
SORT legal_entity_type, domain

