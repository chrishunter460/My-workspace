# Entity Resolution: Master Registry + Cosine Similarity

**Proposed**: 2026-03-15
**Status**: Draft
**Scope**: Generic entity resolution framework with initial application to `dim_department`

---

## Problem Statement

Department names arrive from three Chicago data sources with inconsistent naming conventions:

```
┌───────────────────────────┬─────────────────────────────┬─────────────────────────┐
│ chicago_payments          │ chicago_budget_appropriations│ chicago_budget_positions │
│ (department column)       │ (department_description)     │ (department_description) │
├───────────────────────────┼─────────────────────────────┼─────────────────────────┤
│ "POLICE"                  │ "Police Department"          │ "DEPT OF POLICE"        │
│ "STREETS & SAN"           │ "Streets and Sanitation"     │ "STREETS & SANITATION"  │
│ "WATER MGMT"              │ "Water Management"           │ "DEPT OF WATER MGMT"   │
│ "OEMC"                    │ "Office of Emergency Mgmt"   │ "OEMC"                  │
│ "FIRE"                    │ "Fire Department"            │ "DEPT OF FIRE"          │
└───────────────────────────┴─────────────────────────────┴─────────────────────────┘
```

Currently, the `dim_department` DISTINCT transform groups on raw `organizational_unit` and hashes directly:

```sql
org_unit_id   = ABS(HASH(COALESCE(organizational_unit, 'UNKNOWN')))
org_unit_code = COALESCE(organizational_unit, 'UNKNOWN')
```

**Result**: "POLICE", "Police Department", and "DEPT OF POLICE" produce **three separate dimension rows** with different surrogate keys. Enrichment joins then split budget and payment data across these duplicates, making budget-vs-actual analysis incorrect.

This same class of problem exists for `dim_vendor` (payee name variations), `dim_facility` (facility name/address drift), and any future dimension built from free-text source fields.

---

## Current Data Flow (Before)

```
                BRONZE LAYER
┌────────────────────────────────────────────────────────────────┐
│ chicago_payments          chicago_budget_appropriations         │
│ ┌──────────────────┐      ┌──────────────────────────┐        │
│ │ department:       │      │ department_description:    │        │
│ │  "POLICE"         │      │  "Police Department"      │        │
│ │  "STREETS & SAN"  │      │  "Streets and Sanitation" │        │
│ │  "WATER MGMT"     │      │  "Water Management"       │        │
│ │  "OEMC"           │      │  "Office of Emergency.."  │        │
│ └──────────────────┘      └──────────────────────────┘        │
└──────────┬─────────────────────────────┬──────────────────────┘
           │                             │
        alias:                        alias:
   organizational_unit          department_description
           │                             │
           ▼                             ▼
┌──────────────────────────────────────────────────────────────────┐
│ SILVER FACT TABLES (Phase 1)                                     │
│                                                                  │
│ fact_ledger_entries              fact_budget_events               │
│ ┌──────────────────────┐       ┌──────────────────────┐         │
│ │ organizational_unit: │       │ department_description:│         │
│ │  "POLICE"            │       │  "Police Department"  │         │
│ │  "STREETS & SAN"     │       │  "Streets and Sanit.."│         │
│ │  "WATER MGMT"        │       │  "Water Management"   │         │
│ └──────────────────────┘       └──────────────────────┘         │
└──────────┬──────────────────────────────┬────────────────────────┘
           │                              │
           └────────────┬─────────────────┘
                        │
          ┌─────────────▼──────────────┐
          │ SELECT DISTINCT            │
          │ on [organizational_unit]   │
          │ from UNION of both tables  │
          └─────────────┬──────────────┘
                        │
                        ▼
          ┌──────────────────────────────────────────────────┐
          │ dim_department                                    │
          │                                                  │
          │ DUPLICATES — same entity, different rows:        │
          │                                                  │
          │  org_unit_id  │ org_unit_code                    │
          │ ──────────────┼────────────────────────────────  │
          │  hash(A)      │ "POLICE"                         │
          │  hash(B)      │ "Police Department"              │
          │  hash(C)      │ "DEPT OF POLICE"                 │
          │  hash(D)      │ "STREETS & SAN"                  │
          │  hash(E)      │ "Streets and Sanitation"         │
          │  hash(F)      │ "WATER MGMT"                     │
          │  hash(G)      │ "Water Management"               │
          │  ...          │ ...                               │
          └──────────────────────────────────────────────────┘
                        │
                        ▼ ENRICHMENT JOINS FRAGMENT
          ┌──────────────────────────────────────────────────┐
          │ Enrichment Block 1:                              │
          │   JOIN fact_ledger_entries                       │
          │     ON organizational_unit = org_unit_code       │
          │                                                  │
          │   "POLICE" row gets $200M in payments            │
          │   "Police Department" row gets $0                │
          │   "DEPT OF POLICE" row gets $0                   │
          │                                                  │
          │ Enrichment Block 2:                              │
          │   JOIN fact_budget_events                        │
          │     ON department_description = org_unit_code    │
          │                                                  │
          │   "POLICE" row gets $0 budget                    │
          │   "Police Department" row gets $350M budget      │
          │   "DEPT OF POLICE" row gets $0                   │
          │                                                  │
          │ Result: budget_utilization_pct = NULL everywhere │
          │ because budget and actuals land on DIFFERENT rows│
          └──────────────────────────────────────────────────┘
```

**The core problem**: Budget data joins on `department_description` while payment data joins on `organizational_unit`. These are different strings for the same department, so enrichment metrics (budget variance, utilization %) are meaningless — budget lands on one row, actuals on another.

---

## Proposed Data Flow (After)

```
                BRONZE LAYER (unchanged)
┌────────────────────────────────────────────────────────────────┐
│ chicago_payments          chicago_budget_appropriations         │
│ ┌──────────────────┐      ┌──────────────────────────┐        │
│ │ department:       │      │ department_description:    │        │
│ │  "POLICE"         │      │  "Police Department"      │        │
│ └──────────────────┘      └──────────────────────────┘        │
└──────────┬─────────────────────────────┬──────────────────────┘
           │                             │
           ▼                             ▼
┌──────────────────────────────────────────────────────────────────┐
│ SILVER FACT TABLES (Phase 1 — unchanged)                         │
│                                                                  │
│ fact_ledger_entries              fact_budget_events               │
│ ┌──────────────────────┐       ┌──────────────────────┐         │
│ │ organizational_unit: │       │ department_description:│         │
│ │  "POLICE"            │       │  "Police Department"  │         │
│ └──────────────────────┘       └──────────────────────┘         │
└──────────┬──────────────────────────────┬────────────────────────┘
           │                              │
           └────────────┬─────────────────┘
                        │
          ┌─────────────▼──────────────┐
          │ SELECT DISTINCT            │
          │ on [organizational_unit]   │
          │ from UNION of both tables  │
          └─────────────┬──────────────┘
                        │
                        ▼  RAW DISTINCT VALUES (~100 rows)
          ┌──────────────────────────────────────────────┐
          │  "POLICE"                                     │
          │  "Police Department"                          │
          │  "DEPT OF POLICE"                             │
          │  "STREETS & SAN"                              │
          │  "Streets and Sanitation"                     │
          │  "WATER MGMT"                                 │
          │  "Water Management"                           │
          │  "OEMC"                                       │
          │  ...                                          │
          └──────────────┬───────────────────────────────┘
                         │
    ═════════════════════╪══════════════════════════════════
    ║  NEW: ENTITY       ║
    ║  RESOLUTION        ║
    ║  PHASE             ║
    ═════════════════════╪══════════════════════════════════
                         │
          ┌──────────────▼───────────────────────────────┐
          │                                               │
          │  STEP 1: MASTER REGISTRY LOOKUP               │
          │  ─────────────────────────────                │
          │  Load entities/departments.md                  │
          │                                               │
          │  For each raw name:                           │
          │    Check alias map (O(1) dict lookup)         │
          │                                               │
          │  "POLICE"            → ✅ "Police Department"  │
          │  "Police Department" → ✅ "Police Department"  │
          │  "DEPT OF POLICE"    → ✅ "Police Department"  │
          │  "STREETS & SAN"     → ✅ "Streets & San"      │
          │  "OEMC"              → ✅ "OEMC"               │
          │  "POLCE DEPT"        → ❌ no match             │
          │  "New Bureau XYZ"    → ❌ no match             │
          │                                               │
          └──────────────┬───────────────────────────────┘
                         │
                         │ unmatched names
                         ▼
          ┌──────────────────────────────────────────────┐
          │                                               │
          │  STEP 2: COSINE SIMILARITY FALLBACK           │
          │  ────────────────────────────────              │
          │  TF-IDF vectorize (char n-grams, n=2..4)     │
          │  Compare unmatched → master canonical names   │
          │                                               │
          │  "POLCE DEPT"                                  │
          │    vs "Police Department" → cos=0.91 ✅ MATCH  │
          │    vs "Streets & San"     → cos=0.12 ❌        │
          │                                               │
          │  "New Bureau XYZ"                              │
          │    vs all canonicals      → max cos=0.31 ❌    │
          │    → FLAGGED for manual review                │
          │                                               │
          │  Threshold: 0.85 (configurable per entity)    │
          │                                               │
          └──────────────┬───────────────────────────────┘
                         │
                         ▼
          ┌──────────────────────────────────────────────┐
          │                                               │
          │  STEP 3: BUILD RESOLUTION MAP                 │
          │  ─────────────────────────────                │
          │  raw_name → canonical_name mapping:           │
          │                                               │
          │  ┌─────────────────────┬────────────────────┐ │
          │  │ raw_name            │ canonical_name     │ │
          │  ├─────────────────────┼────────────────────┤ │
          │  │ "POLICE"            │ "Police Department"│ │
          │  │ "Police Department" │ "Police Department"│ │
          │  │ "DEPT OF POLICE"    │ "Police Department"│ │
          │  │ "POLCE DEPT"        │ "Police Department"│ │
          │  │ "STREETS & SAN"     │ "Streets & San"    │ │
          │  │ "Streets and Sanit" │ "Streets & San"    │ │
          │  │ "New Bureau XYZ"    │ "New Bureau XYZ"   │ │
          │  └─────────────────────┴────────────────────┘ │
          │                                               │
          │  method: MASTER | COSINE | PASSTHROUGH        │
          │                                               │
          └──────────────┬───────────────────────────────┘
                         │
                         ▼
          ┌──────────────────────────────────────────────┐
          │                                               │
          │  STEP 4: APPLY MAP + DERIVE                   │
          │  ───────────────────────                      │
          │  Replace organizational_unit with canonical   │
          │  Re-deduplicate on canonical name             │
          │  Then apply standard derive expressions       │
          │                                               │
          └──────────────┬───────────────────────────────┘
                         │
    ═════════════════════╪══════════════════════════════════
                         │
                         ▼  RESOLVED DISTINCT VALUES (~45 rows)
          ┌──────────────────────────────────────────────────┐
          │ dim_department (CONSOLIDATED)                     │
          │                                                  │
          │  org_unit_id  │ org_unit_code        │ aliases   │
          │ ──────────────┼──────────────────────┼────────── │
          │  hash(X)      │ "Police Department"  │ 3 names   │
          │  hash(Y)      │ "Streets & San"      │ 2 names   │
          │  hash(Z)      │ "Water Management"   │ 2 names   │
          │  hash(W)      │ "OEMC"               │ 1 name    │
          │  hash(V)      │ "New Bureau XYZ"     │ 1 name    │
          │  ...          │ ...                   │           │
          └──────────────────────────────────────────────────┘
                         │
                         ▼ ENRICHMENT JOINS NOW CONVERGE
          ┌──────────────────────────────────────────────────┐
          │                                                  │
          │  Enrichment Block 1 (ledger):                    │
          │    JOIN fact_ledger_entries                       │
          │      ON organizational_unit IN (alias list)      │
          │      → "Police Department" gets ALL $200M        │
          │                                                  │
          │  Enrichment Block 2 (budget):                    │
          │    JOIN fact_budget_events                        │
          │      ON department_description IN (alias list)   │
          │      → "Police Department" gets ALL $350M budget │
          │                                                  │
          │  Result:                                          │
          │    budget_variance      = $350M - $200M = $150M  │
          │    budget_utilization   = $200M / $350M = 57.1%  │
          │    ✅ CORRECT — all data on ONE row              │
          │                                                  │
          └──────────────────────────────────────────────────┘
```

---

## Enrichment Join Strategy (Critical Detail)

The resolution map doesn't just consolidate the dimension — it must also **widen the enrichment joins** so all source name variants route to the single canonical row.

### Option A: Alias Expansion Table (Recommended)

The entity resolver produces a side-table persisted alongside the dimension:

```
dim_department_aliases (side-table, auto-generated)
┌─────────────────────────────┬────────────────────┬──────────┐
│ raw_name                    │ canonical_code      │ method   │
├─────────────────────────────┼────────────────────┼──────────┤
│ POLICE                      │ Police Department  │ MASTER   │
│ Police Department           │ Police Department  │ MASTER   │
│ DEPT OF POLICE              │ Police Department  │ MASTER   │
│ POLCE DEPT                  │ Police Department  │ COSINE   │
│ STREETS & SAN               │ Streets & San      │ MASTER   │
│ Streets and Sanitation      │ Streets & San      │ MASTER   │
│ New Bureau XYZ              │ New Bureau XYZ     │ PASS     │
└─────────────────────────────┴────────────────────┴──────────┘
```

Enrichment joins change from:
```sql
-- BEFORE (direct string match — fragments data)
JOIN fact_ledger_entries ON organizational_unit = org_unit_code

-- AFTER (alias-aware — converges data)
JOIN dim_department_aliases a ON organizational_unit = a.raw_name
JOIN dim_department d ON a.canonical_code = d.org_unit_code
```

### Option B: Rewrite Fact Tables (Heavier but Simpler Downstream)

Add a Phase 1.5 that rewrites `organizational_unit` in the fact tables to the canonical name before Phase 2 dimension build. This means all downstream joins work unchanged.

```
Phase 1:   Build fact tables (as-is)
Phase 1.5: Apply resolution map to fact.organizational_unit  ← NEW
Phase 2:   Build dimensions (DISTINCT now sees canonical names only)
           Enrichment joins match naturally
```

**Tradeoff**: Heavier (rewrites large fact tables) but zero changes to enrichment config.

---

## Master Entity Registry Format

```
domains/models/municipal/finance/entities/departments.md
```

```yaml
---
type: domain-entity-registry
entity: department
canonical_field: org_unit_code
match_strategy: cosine
match_threshold: 0.85
vectorizer:
  analyzer: char_wb
  ngram_range: [2, 4]
  max_features: 5000

entries:
  - canonical: "Police Department"
    code: "POLICE"
    aliases:
      - "POLICE"
      - "DEPT OF POLICE"
      - "CPD"
      - "Chicago Police Department"
      - "DEPARTMENT OF POLICE"

  - canonical: "Fire Department"
    code: "FIRE"
    aliases:
      - "FIRE"
      - "DEPT OF FIRE"
      - "CFD"
      - "Chicago Fire Department"
      - "DEPARTMENT OF FIRE"

  - canonical: "Streets & Sanitation"
    code: "STREETS_SAN"
    aliases:
      - "STREETS & SAN"
      - "STREETS AND SANITATION"
      - "DEPT OF STREETS & SANITATION"
      - "DEPARTMENT OF STREETS AND SANITATION"

  - canonical: "Water Management"
    code: "WATER_MGMT"
    aliases:
      - "WATER MGMT"
      - "DEPT OF WATER MANAGEMENT"
      - "DEPARTMENT OF WATER MANAGEMENT"
      - "WATER DEPARTMENT"

  - canonical: "Office of Emergency Management & Communications"
    code: "OEMC"
    aliases:
      - "OEMC"
      - "EMERGENCY MANAGEMENT"
      - "OFFICE OF EMERGENCY MGMT"

  # ... additional departments
---

# Department Entity Registry

Known name variations for City of Chicago departments across budget,
payment, and personnel data sources. The `aliases` lists are the
**hard overrides** — any raw value matching an alias maps directly
to the canonical name with no ML involved.

Values not found in any alias list fall through to cosine similarity
matching against the canonical names. Matches above the threshold
(0.85) are auto-resolved; below-threshold values are flagged in
build logs for manual review and addition to this file.

## Maintenance

When the build log reports unmatched department names:
1. Determine the correct canonical department
2. Add the raw name to the appropriate `aliases` list
3. Re-run the build — the name will resolve on next run

## Sources of Name Variation
- Budget data uses formal names ("Police Department")
- Payment data uses abbreviations ("POLICE")
- Position data uses prefix pattern ("DEPT OF POLICE")
- Historical data may use outdated names from reorganizations
```

---

## Entity Resolver Architecture

### New File: `src/de_funk/models/base/entity_resolver.py`

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│  EntityResolver                                                     │
│  ──────────────                                                     │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ __init__(registry_path: Path, config: dict)                  │   │
│  │   - Parse entities/departments.md YAML frontmatter           │   │
│  │   - Build alias_map: Dict[str, str]  (lowered raw → canon)  │   │
│  │   - Build canonical_list: List[str]  (all canonical names)   │   │
│  │   - Fit TF-IDF vectorizer on canonical_list                  │   │
│  │   - Pre-compute canonical_vectors matrix                     │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ resolve(raw_name: str) → Resolution                          │   │
│  │                                                               │   │
│  │   1. Normalize: strip, upper, collapse whitespace             │   │
│  │   2. Check alias_map → if found: (canonical, 1.0, MASTER)    │   │
│  │   3. TF-IDF transform raw_name → vector                      │   │
│  │   4. Cosine similarity vs canonical_vectors                   │   │
│  │   5. If max_sim ≥ threshold: (best_match, sim, COSINE)       │   │
│  │   6. Else: (raw_name, max_sim, UNMATCHED)                    │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ resolve_column(df, column) → df with canonical column        │   │
│  │                                                               │   │
│  │   Spark path:                                                 │   │
│  │     - Collect distinct values (.distinct().collect())         │   │
│  │     - Resolve each via resolve()                              │   │
│  │     - Broadcast mapping as Spark MapType                      │   │
│  │     - df.withColumn(col, map_lookup[col])                     │   │
│  │                                                               │   │
│  │   DuckDB path:                                                │   │
│  │     - Register mapping as temp table                          │   │
│  │     - LEFT JOIN + COALESCE                                    │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ build_alias_table(df, column) → alias_df                     │   │
│  │                                                               │   │
│  │   Returns DataFrame:                                          │   │
│  │     [raw_name, canonical_code, confidence, method]            │   │
│  │   For persistence as dim_{entity}_aliases side-table          │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ report_unmatched() → List[UnmatchedEntry]                    │   │
│  │                                                               │   │
│  │   Returns names that fell through both master + cosine       │   │
│  │   For build log warnings + manual review                     │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  Resolution = namedtuple:                                           │
│    canonical: str                                                   │
│    confidence: float  (1.0 for master, 0.0-1.0 for cosine)        │
│    method: MASTER | COSINE | UNMATCHED                              │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Cosine Similarity Detail

```
                    TF-IDF Vectorizer
                    (char_wb, ngrams 2-4)

  "POLCE DEPT"  ──────────────────────────▶  sparse vector v₁
                                              dim ≈ 5000

  Canonical corpus (pre-fitted):

  "Police Department"      → v_police     ┐
  "Fire Department"        → v_fire       │
  "Streets & Sanitation"   → v_streets    ├── canonical_vectors matrix
  "Water Management"       → v_water      │     (N_canonical × 5000)
  "OEMC"                   → v_oemc       ┘

  cosine_similarity(v₁, canonical_vectors):

    vs "Police Department"      = 0.91  ← BEST MATCH ✅
    vs "Fire Department"        = 0.34
    vs "Streets & Sanitation"   = 0.08
    vs "Water Management"       = 0.12
    vs "OEMC"                   = 0.02

  0.91 ≥ threshold (0.85) → resolve to "Police Department"
```

**Why char n-grams (not word tokens)**:
- Handles abbreviations: "DEPT" ↔ "Department" share char trigrams "DEP", "EPT"
- Handles missing spaces: "STREETSAN" still overlaps with "STREETS & SAN"
- Handles typos: "POLCE" shares most trigrams with "POLICE"
- Small vocabulary: ~45 department names → fast matrix multiply

---

## Integration Point in Build Pipeline

### dim_department.md Changes

```yaml
---
type: domain-model-table
table: dim_department
extends: _base.entity.organizational_entity._dim_org_unit
table_type: dimension
transform: distinct
from: fact_ledger_entries
union_from: [fact_ledger_entries, fact_budget_events]
group_by: [organizational_unit]
primary_key: [org_unit_id]
unique_key: [org_unit_code]

# NEW: Entity resolution config
entity_resolution:
  registry: entities/departments.md      # path relative to model directory
  source_column: organizational_unit     # column to resolve
  strategy: master_then_cosine           # MASTER lookup → COSINE fallback
  threshold: 0.85                        # cosine similarity threshold
  persist_aliases: true                  # write dim_department_aliases table
  on_unmatched: passthrough              # passthrough | error | skip

schema:
  # org_unit_id now hashes the CANONICAL name, not the raw name
  - [org_unit_id, integer, false, "PK", {derived: "ABS(HASH(COALESCE(organizational_unit, 'UNKNOWN')))"}]
  # ... rest unchanged
---
```

### domain_model.py Changes

```
_build_distinct_node()
│
├── 1. Load union of source tables (existing)
├── 2. SELECT DISTINCT on group_by columns (existing)
│
├── 3. ★ NEW: Check for entity_resolution config
│       If present:
│         resolver = EntityResolver(registry_path, config)
│         df = resolver.resolve_column(df, source_column)
│         alias_df = resolver.build_alias_table(df, source_column)
│         Re-deduplicate on resolved canonical values
│         Log unmatched entries
│
├── 4. Apply derived expressions (existing)
├── 5. Apply enrichments (existing — joins now converge)
└── 6. Return final dimension
```

---

## Operational Flow

### Build Time

```
$ python -m scripts.build.build_models --models municipal_finance

[INFO]  Phase 1: Building fact tables...
[INFO]    fact_ledger_entries: 2.4M rows
[INFO]    fact_budget_events: 850K rows

[INFO]  Phase 2: Building dimensions...
[INFO]    dim_department: entity resolution enabled
[INFO]      Master registry: 42 canonical entries, 187 aliases
[INFO]      Raw distinct values: 98
[INFO]      ├── Master matched: 89 (90.8%)
[INFO]      ├── Cosine matched: 6 (6.1%) [threshold=0.85]
[INFO]      │   ├── "POLCE DEPT" → "Police Department" (0.91)
[INFO]      │   ├── "STRETS & SAN" → "Streets & Sanitation" (0.88)
[INFO]      │   └── ... 4 more
[INFO]      └── Unmatched (passthrough): 3 (3.1%)
[WARN]          ├── "Bureau of Asset Management" (best: 0.62 → "Asset Management")
[WARN]          ├── "New Office of Climate" (best: 0.41 → none)
[WARN]          └── "COPA" (best: 0.38 → none)
[INFO]      Consolidated: 98 raw → 47 canonical departments
[INFO]      Alias table persisted: dim_department_aliases (98 rows)
[INFO]    dim_department: enrichment complete
[INFO]      budget_utilization_pct: 47/47 rows have non-null values ✅
```

### Maintenance Cycle

```
                    ┌──────────────┐
                    │  Build runs  │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
              ┌─────│  Unmatched?  │─────┐
              │ No  └──────────────┘ Yes │
              │                          │
              ▼                          ▼
        ┌───────────┐          ┌─────────────────┐
        │  Done ✅   │          │  Build log warns │
        └───────────┘          │  with names +    │
                               │  best candidates │
                               └────────┬────────┘
                                        │
                                        ▼ human reviews
                               ┌─────────────────┐
                               │  Add to master   │
                               │  registry .md    │
                               │  (alias or new   │
                               │  canonical entry)│
                               └────────┬────────┘
                                        │
                                        ▼
                               ┌─────────────────┐
                               │  git commit +    │
                               │  re-run build    │
                               └─────────────────┘
```

---

## Applicability to Other Entities

The same pattern generalizes to any dimension built from free-text source fields:

| Dimension | Source Column | Name Drift Examples |
|-----------|-------------|---------------------|
| `dim_department` | `organizational_unit` | "POLICE" vs "Police Department" |
| `dim_vendor` | `payee` | "ACME INC" vs "ACME, INC." vs "ACME INCORPORATED" |
| `dim_facility` | `facility_name` | "O'Hare Airport" vs "OHARE INTL" |
| `dim_community_area` | `community_area` | "LOOP" vs "The Loop" vs "Loop (Downtown)" |

Each gets its own `entities/{name}.md` registry file in the model directory. The `EntityResolver` class is generic — it only needs a registry path and a column name.

---

## Dependencies

**Python packages (already available or lightweight)**:
- `scikit-learn` — `TfidfVectorizer`, `cosine_similarity` (likely already installed for forecast models)
- No heavy ML frameworks, no embeddings API, no GPU needed

**Performance**:
- Master lookup: O(1) dict, handles 90%+ of values
- TF-IDF fit: <100ms on ~50 canonical names
- Cosine similarity: <10ms for ~10 unmatched names × ~50 canonicals
- Total overhead per dimension build: <200ms

---

## File Inventory (New + Modified)

| File | Status | Purpose |
|------|--------|---------|
| `src/de_funk/models/base/entity_resolver.py` | **NEW** | EntityResolver class (master + cosine) |
| `domains/models/municipal/finance/entities/departments.md` | **NEW** | Department master registry |
| `domains/models/municipal/finance/tables/dim_department.md` | MODIFY | Add `entity_resolution:` config block |
| `src/de_funk/models/base/domain_model.py` | MODIFY | Call EntityResolver in `_build_distinct_node()` |
| `src/de_funk/config/domain/schema.py` | MODIFY | Parse `entity_resolution` from table config |
