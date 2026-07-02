---

type: reference
description: "Guide for the subsets convention — declarative data slicing by dimension discriminator"
---

> **Implementation Status**: Pattern 1 (wide_table auto-absorption) is fully implemented. Pattern 2 (separate models) and Pattern 3 (filter-only subsets) are **parsed only** — config is read but no build-time effects are generated.


## subsets Guide

A `subsets:` block on a base template declares that data can be filtered by a dimension discriminator into semantically meaningful subsets. Each subset value optionally defines type-specific fields.

### Three Implementation Patterns

#### Pattern 1: Wide Table with Auto-Absorption (Recommended for typed entities)

When subsets have **different columns per type**, use child templates with `subset_of` to define type-specific fields. The parent auto-absorbs them into one wide dimension table.

**Parent template** — declares the pattern and references children:

```yaml
subsets:
  discriminator: _dim_property_class.property_category
  pattern: wide_table
  target_table: _dim_parcel
  values:
    RESIDENTIAL:
      extends: _base.property.residential
      description: "Single-family, multi-family, condos"
      filter: "property_category = 'RESIDENTIAL'"
    COMMERCIAL:
      extends: _base.property.commercial
      description: "Office, retail, mixed-use"
      filter: "property_category = 'COMMERCIAL'"
```

**Child template** — single source of truth for subset fields:

```yaml
# _base/property/residential.md
type: domain-base
subset_of: _base.property.parcel
subset_value: RESIDENTIAL

canonical_fields:
  - [bedrooms, integer, nullable: true, description: "Number of bedrooms"]
  - [bathrooms, double, nullable: true, description: "Number of bathrooms"]

measures:
  - [avg_bedrooms, avg, bedrooms, "Average bedrooms", {format: "#,##0.0"}]
```

**What the loader produces** — the absorbed wide table:

```yaml
_dim_parcel:
  partition_by: [property_category]
  schema:
    # Common fields (from parent)
    - [parcel_id, string, false, "PK"]
    - [property_category, string, true, "Denormalized from dim_property_class"]

    # Auto-absorbed from _base.property.residential
    - [bedrooms, integer, true, "Number of bedrooms", {subset: RESIDENTIAL}]
    - [bathrooms, double, true, "Number of bathrooms", {subset: RESIDENTIAL}]

    # Auto-absorbed from _base.property.commercial
    - [commercial_sqft, double, true, "Floor area", {subset: COMMERCIAL}]

  measures:
    # From parent
    - [parcel_count, count_distinct, parcel_id, "Number of parcels"]
    # Auto-absorbed from _base.property.residential
    - [avg_bedrooms, avg, bedrooms, "Average bedrooms", {format: "#,##0.0", subset: RESIDENTIAL}]
```

**Adding a field** — one file change at the base layer:

1. Add to child template's `canonical_fields` (e.g., `commercial.md`)
2. Add source alias in the model's source file
3. Optionally add a `derivation:` in the model table if the source column name differs

**When to use**: Entity has different attributes per type but shares the same fact tables. Examples: property parcels (residential vs commercial vs industrial).

**Advantages**:
- **Single source of truth** — each field defined once in its subset child template
- Delta Lake partition pruning makes filtered queries fast
- Columnar null compression makes sparse columns essentially free
- No join overhead — all fields available in one table
- Schema evolution handles new types by adding columns

**Field dictionary**: The discriminator dimension (e.g., `_dim_property_class`) should include an `applicable_fields` column listing which subset columns are populated for each code.

---


#### Pattern 2: Separate Models (For independent domain models)

> **Status: PLANNED** — Parsed in config but no special handling in the build
> pipeline. Each model builds independently; the subset relationship is
> informational only.

When subsets have **completely different fact tables and build pipelines**, use separate domain models that independently extend the base.

```yaml
subsets:
  discriminator: _dim_security.asset_type
  values:
    Stock:
      model: stocks
      description: "Common and preferred stock equities"
      filter: "asset_type = 'stocks'"
    ETF:
      model: etfs
      description: "Exchange-traded funds"
      filter: "asset_type = 'etfs'"
```

**When to use**: Each subset is a full domain model with its own fact tables, build pipeline, and graph. Examples: securities (stocks vs options vs ETFs — each has different fact tables).

---


#### Pattern 3: Filter-Only (No type-specific fields)

> **Status: PLANNED** — Parsed in config but filter predicates are not
> auto-generated or enforced during build. The discriminator values serve as
> documentation only.

When subsets share the **exact same schema** and differ only as analytical slices.

```yaml
subsets:
  discriminator: _dim_crime_type.crime_category
  values:
    VIOLENT:
      description: "Homicide, assault, battery, robbery"
      filter: "crime_category = 'VIOLENT'"
    PROPERTY:
      description: "Theft, burglary, motor vehicle theft"
      filter: "crime_category = 'PROPERTY'"
```

**When to use**: All rows have the same columns. The discriminator is just for analytical filtering. No `extends:`, `model:`, or `fields:` needed.

---


### Pattern Selection Guide

| Question | Wide Table | Separate Models | Filter-Only |
|----------|-----------|-----------------|-------------|
| Different columns per type? | Yes | Yes | No |
| Different fact tables per type? | No | Yes | No |
| Same build pipeline? | Yes | No | Yes |
| Same source data? | Yes | No | Yes |

---


### Key Properties

**Parent `subsets:` block:**

| Property | Required | Description |
|----------|----------|-------------|
| `discriminator` | Yes | `dimension_table.column` — where the enum lives |
| `pattern` | No | `wide_table` or omit (inferred from context) |
| `target_table` | Wide table only | Which table absorbs subset columns (e.g., `_dim_parcel`) |
| `description` | No | Human-readable description of the absorption mechanism |
| `values` | Yes | Map of enum values to subset definitions |
| `values.*.extends` | Wide table only | Reference to child template (e.g., `_base.property.residential`) |
| `values.*.model` | Separate models only | Child domain-model name |
| `values.*.description` | Yes | What this subset represents |
| `values.*.filter` | Yes | SQL predicate for the subset |

**Child template (wide table pattern):**

| Property | Required | Description |
|----------|----------|-------------|
| `subset_of` | Yes | Parent base template (e.g., `_base.property.parcel`) |
| `subset_value` | Yes | Discriminator value (e.g., `RESIDENTIAL`) |
| `canonical_fields` | Yes | Fields to absorb into parent's target table |
| `measures` | No | Measures to absorb into parent's target table |

---


### Auto-Absorption Mechanism

When a parent template has `subsets.pattern: wide_table`:

1. **Discovery**: Loader finds child templates with `subset_of: <parent>` (or follows `subsets.values.*.extends` references)
2. **Field absorption**: Each child's `canonical_fields` → appended to `target_table.schema` as nullable columns with `{subset: child.subset_value}`
3. **Measure absorption**: Each child's `measures` → appended to `target_table.measures` with `{subset: child.subset_value}`
4. **Fields list**: `subsets.values.*.fields` auto-derived from child `canonical_fields` (not manually listed)
5. **Validation**: Verify discriminator column exists, verify no field name collisions across subsets

**Result**: Parent's `target_table` contains common columns + all subset columns. No duplication between parent and children.

---


### Current Subset Assignments

| Base Template | Discriminator | Pattern | Values |
|--------------|---------------|---------|--------|
| `_base.property.parcel` | `_dim_property_class.property_category` | **Wide table** | RESIDENTIAL, COMMERCIAL, INDUSTRIAL, EXEMPT, OTHER |
| `_base.finance.securities` | `_dim_security.asset_type` | **Separate models** | Stock, ETF, Option, Future |
| `_base.public_safety.crime` | `_dim_crime_type.crime_category` | Filter-only | VIOLENT, PROPERTY, OTHER |
| `_base.operations.service_request` | `_dim_request_type.request_category` | Filter-only | INFRASTRUCTURE, SANITATION, VEGETATION, BUILDINGS, ANIMALS, OTHER |
| `_base.housing.permit` | `_dim_permit_type.permit_category` | Filter-only | NEW_CONSTRUCTION, ALTERATION, DEMOLITION, OTHER |
| `_base.transportation.transit` | `_dim_transit_station.transit_mode` | Filter-only | RAIL, BUS, SUBWAY, LIGHT_RAIL, FERRY |

---


### Relationship to Federation

Subsets and federation are complementary:
- **Federation** slices data horizontally by `domain_source` (which city/county produced it)
- **Subsets** slice data vertically by a dimension attribute (what category it belongs to)

This enables queries like: "Show residential parcels across all federated counties" (subset + federation).

---


### Loader Behavior

The `subsets:` block is declarative. The loader uses it for:
1. **Auto-absorption**: Merge child template fields and measures into parent's target table
2. **Validation**: Verify discriminator column exists; no field name collisions across subsets
3. **Filter generation**: Produce filter predicates for downstream queries
4. **Column metadata**: `{subset: VALUE}` marks which columns belong to which subset
5. **Field dictionary**: Populate `applicable_fields` on the discriminator dimension
6. **Documentation**: Discoverable via `behaviors: [subsettable]`
