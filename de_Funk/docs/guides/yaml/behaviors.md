---

type: reference
description: "Guide for the behaviors convention — cross-cutting capabilities on base templates"
---

> **Implementation Status**: **PARSED ONLY**. Behavior tags are read from config but are NOT used for validation, feature auto-discovery, or capability queries. They serve as documentation metadata only.


## behaviors Guide

A `behaviors:` list on a base template documents which cross-cutting capabilities the template supports. Behaviors are **informational** (like `tags:`) — they make capabilities discoverable without changing build processing.

### Syntax

```yaml
behaviors:
  - temporal        # Has auto_edges for date_id → calendar
  - geo_locatable   # Has auto_edges for location_id → geo_location
  - subsettable     # Has subsets: block
```

### Available Behaviors

| Behavior | Meaning | Implies |
|----------|---------|---------|
| `temporal` | Facts FK to `temporal.dim_calendar` via `date_id` | `auto_edges` includes `date_id` (on this template or inherited) |
| `geo_locatable` | Facts FK to `geo_location._dim_location` via `location_id` | `auto_edges` includes `location_id` (inherited from event) |
| `subsettable` | Data can be filtered by a dimension discriminator into subsets | `subsets:` block is present |

**Note:** `federable` was removed as a behavior. Federation is now owned by federation models in `models/_base/`, not by base templates. See federation.md.

### Inheritance

Behaviors are inherited through the `extends:` chain. A child template inherits its parent's behaviors and may add its own:

```
_base._base_.event           → [temporal, geo_locatable]
└── _base.public_safety.crime → [temporal, geo_locatable, subsettable]
```

Child templates don't need to re-declare inherited behaviors but **do** list them for discoverability.

### Current Behavior Assignments

**Root templates:**

| Base Template | behaviors |
|--------------|-----------|
| `_base._base_.entity` | `[]` (root — no behaviors) |
| `_base._base_.event` | `[temporal, geo_locatable]` |

**Event-chain bases** (inherit from `_base._base_.event`):

| Base Template | behaviors |
|--------------|-----------|
| `_base.accounting.financial_event` | `[temporal]` |
| `_base.accounting.ledger_entry` | `[temporal]` |
| `_base.accounting.financial_statement` | `[temporal]` |
| `_base.corporate.earnings` | `[temporal]` |
| `_base.finance.corporate_action` | `[temporal]` |
| `_base.finance.securities` | `[temporal, subsettable]` |
| `_base.property.parcel` | `[temporal, subsettable]` |
| `_base.public_safety.crime` | `[temporal, geo_locatable, subsettable]` |
| `_base.regulatory.inspection` | `[temporal, geo_locatable]` |
| `_base.operations.service_request` | `[temporal, geo_locatable, subsettable]` |
| `_base.housing.permit` | `[temporal, geo_locatable, subsettable]` |
| `_base.transportation.transit` | `[temporal, geo_locatable, subsettable]` |
| `_base.transportation.traffic` | `[temporal, geo_locatable]` |

**Entity-chain bases** (inherit from `_base._base_.entity` or its descendants):

| Base Template | behaviors | Note |
|--------------|-----------|------|
| `_base.entity.legal` | `[]` | Pure entity |
| `_base.entity.company` | `[]` | Reference dimension |
| `_base.entity.municipality` | `[]` | Reference dimension |
| `_base.entity.organizational_entity` | `[]` | Reference dimension |
| `_base.geography.geo_location` | `[]` | Target of auto_edges |
| `_base.geography.geo_spatial` | `[]` | Boundary dimension |
| `_base.accounting.chart_of_accounts` | `[]` | Classification dimension |
| `_base.accounting.fund` | `[]` | Classification dimension |
| `_base.temporal.calendar` | `[]` | Target dimension |
| `_base.property.tax_district` | `[]` | Tax classification dimension |

**Subset-only bases** (child templates, inherit parent behaviors):

| Base Template | behaviors | subset_of |
|--------------|-----------|-----------|
| `_base.property.residential` | (inherits from parcel) | `_base.property.parcel` |
| `_base.property.commercial` | (inherits from parcel) | `_base.property.parcel` |
| `_base.property.industrial` | (inherits from parcel) | `_base.property.parcel` |

### Relationship to Other Blocks

Behaviors summarize capabilities defined elsewhere:

| Behavior | Defined By |
|----------|-----------|
| `temporal` | `auto_edges:` with `date_id` (on this template or ancestor) |
| `geo_locatable` | `auto_edges:` with `location_id` (on this template or ancestor) |
| `subsettable` | `subsets:` block |

### Why Not Mixins?

Behaviors are informational, not compositional. The actual capability (auto_edges, subsets) is declared via its own YAML block. Behaviors simply document which capabilities are active, enabling:

- **Discovery**: Query "which templates are subsettable?" without scanning every block
- **Validation**: Loader can verify that claimed behaviors match actual blocks
- **Documentation**: Single line item summarizes template capabilities
