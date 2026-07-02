# Field: data_tags

## Purpose
`data_tags` are **orthogonal descriptors** about the data, beyond subject or publisher. They help filter, categorize, or highlight special characteristics.

---

## Typical Uses
- **Granularity / cadence**: time-series, snapshot
- **Public accessibility**: public, private, restricted
- **Data type**: tabular, geo, JSON, CSV
- **Content nature**: budget, crime, sensor, analytics

---

## Examples

## Data Tags: Reference & Decision Guide

> Data tags describe **what kind of data this is**, not the analytical lens (domain).
> When in doubt: tags can overlap; domains should not.

---

### Temporal & Update Characteristics

| Tag | Explanation | Hard Choice Guidance |
|----|------------|----------------------|
| time-series | Data is indexed by time | Use even if updates are irregular |
| snapshot | Point-in-time extract | Prefer over time-series if no history |
| real-time | Updates continuously or within seconds | If delayed >15 min, use near-real-time |
| near-real-time | Short lag (minutes–hours) | Most public APIs fall here |
| historical | Backfilled or archival | Use alongside time-series |
| forecast | Predictive or modeled data | Do not use for projections stored as static tables |

---

### Regulatory & Enforcement

| Tag | Explanation | Hard Choice Guidance |
|----|------------|----------------------|
| regulatory | Rules or requirements exist | Use when dataset exists due to regulation |
| inspection | Data produced by inspection | Do not use for audits |
| audit | Formal review process | Use only when periodic & evaluative |
| violation | Non-compliance events | Requires enforcement authority |
| enforcement | Actions taken due to violations | Use when penalties or actions are recorded |
| permit | Authorization to act | Do not use for licenses |

---

### Operational & Performance

| Tag | Explanation | Hard Choice Guidance |
|----|------------|----------------------|
| throughput | Volume processed | Prefer over capacity if historical |
| capacity | Maximum possible output | Use for design limits |
| sla | Service-level target | Use only if explicit SLA exists |
| processing-time | Time to completion | Avoid for queue wait time |
| backlog | Work not yet processed | Indicates operational stress |
| utilization | Actual use vs capacity | Requires both metrics |

---

### Economic & Financial

| Tag | Explanation | Hard Choice Guidance |
|----|------------|----------------------|
| budget | Planned spending | Do not use for actuals |
| spending | Executed expenditures | Use for paid amounts |
| appropriations | Authorized funding | Often confused with budget |
| revenue | Incoming funds | Distinct from collections |
| tax | Compulsory payment | Use instead of fee |
| fee | Voluntary payment | Requires opt-in action |
| gdp | Aggregate output | Do not generalize to “economic” |

---

### Geographic & Spatial

| Tag | Explanation | Hard Choice Guidance |
|----|------------|----------------------|
| geospatial | Location-based data | Use whenever coordinates exist |
| boundary | Area definition | Do not use for points |
| parcel | Land unit | Prefer over address for zoning |
| address | Human-readable location | Avoid for analysis |
| census-tract | Census-defined unit | Use instead of zip when available |

---

### Governance & Sensitivity

| Tag | Explanation | Hard Choice Guidance |
|----|------------|----------------------|
| public | No access restrictions | Default for open data |
| restricted | Access limited | Use even if aggregated |
| pii | Personally identifiable | Names, SSNs, emails |
| anonymized | PII removed | Requires irreversible removal |
| aggregated | Grouped statistics | Use even if still sensitive |
| sensitive | Risk if misused | Use sparingly, but intentionally |

---

## Descriptive Data Tags (Informational Characteristics)

These tags describe the **form, structure, and informational nature** of a dataset.
They do **not** imply purpose, authority, or analytical lens.

| Tag | Description | Example |
|----|------------|--------|
| time-series | Observations indexed over time | Monthly unemployment rate |
| cross-sectional | Snapshot across entities at one time | Crime counts by district (2024) |
| longitudinal | Same entities tracked across time | Property assessments by parcel over years |
| snapshot | Single point-in-time extract | Zoning map as of 2023 |
| historical | Archived or backfilled data | Budget data 1990–2010 |
| real-time | Updated continuously | Live transit vehicle locations |
| near-real-time | Short update delay | Grid load every 5 minutes |
| aggregated | Grouped or summarized values | Crime counts by neighborhood |
| microdata | Record-level rows | Individual service requests |
| index | Identifier-based lookup | Parcel ID index |
| reference | Lookup or classification table | Zoning codes |
| categorical | Discrete labels or classes | Permit type, violation category |
| numeric | Quantitative measures | Dollar amounts, counts |
| textual | Free-form text | Complaint descriptions |
| geospatial | Coordinates or geometry | Parcel polygons |
| tabular | Row/column structured | CSV-style dataset |
| hierarchical | Parent/child structure | Budget → department → program |
| dimensional | Fact + dimension model | Time, location, category |
| panel | Entity × time matrix | GDP by country by year |
| forecast | Modeled future values | Energy demand projection |
| estimated | Derived or modeled values | Population estimates |
| revised | Subject to updates | GDP revisions |
| provisional | Preliminary release | Early employment figures |
| benchmarked | Adjusted to standard | Rebasing economic indices |
| normalized | Scaled or standardized | Rates per 100k population |
| seasonally-adjusted | Seasonal effects removed | Monthly unemployment rate |
| raw | Unprocessed source data | Sensor output |
| cleaned | Data quality improved | Deduplicated records |
| anonymized | Identifiers removed | Redacted 311 requests |
| synthetic | Artificially generated | Test datasets |



---

### Example: Hard Tag Decision (Building Violations)

```yaml
domain: regulatory
data_tags:
  - violation
  - inspection
  - code-enforcement
  - geospatial
  - time-series

---

## Rules of Thumb
- Use tags for **quick filtering / discovery**, not primary classification.
- Can combine multiple tags, e.g., `public + time-series + budget`.
- Avoid overloading `data_tags` with publisher or domain info; that belongs in `domain` or `legal_entity_type`.

---

## Dataview Example

Retrieve all public, time-series endpoints:

```dataview
TABLE length(rows) AS "Endpoint Count"
FROM "de'funk/APIs/Endpoints"
FLATTEN data_tags
GROUP BY data_tags