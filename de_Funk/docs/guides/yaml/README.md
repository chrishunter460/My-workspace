# YAML Frontmatter Reference

Syntax reference for every YAML frontmatter section used in de_Funk domain model configs.

## Implementation Status

| Guide | Status | What Works | What Doesn't |
|---|---|---|---|
| [domain_model.md](domain_model.md) | Mostly implemented | type, model, version, extends, depends_on, graph.edges, build, hooks, storage | `ml_models:` parsed only, `views:` not implemented |
| [domain_base.md](domain_base.md) | Implemented | canonical_fields, extends chains | `generation:` only works for temporal via custom hook |
| [tables.md](tables.md) | Mostly implemented | schema, primary_key, table_type, seed, distinct, union, enrich, unpivot | `derivations:` not implemented, `unique_key` parsed but not enforced |
| [sources.md](sources.md) | Implemented | from, aliases, domain_source, coercion_rules | — |
| [source_onboarding.md](source_onboarding.md) | Implemented | Step-by-step guide, all steps work | — |
| [graph.md](graph.md) | Partially implemented | Explicit edges work | `auto_edges:` parsed only, `paths:` parsed only |
| [extends.md](extends.md) | Implemented | Model, table, source, view inheritance | — |
| [measures.md](measures.md) | Partially implemented | simple, computed (SQL) measures | Python measures (NPV, sharpe_ratio) not auto-executed |
| [subsets.md](subsets.md) | Partially implemented | Pattern 1 (wide_table absorption) | Pattern 2 (separate models), Pattern 3 (filter-only) not implemented |
| [views.md](views.md) | **Planned** | Config parsing exists | Views are NOT materialized as Silver tables |
| [federation.md](federation.md) | **Planned** | Federation flags parsed | `union_of` tables not synthesized into SQL UNIONs |
| [storage.md](storage.md) | Implemented | Silver paths, format, partitions | — |
| [materialization.md](materialization.md) | Implemented | Build phases, ordering, optimize/vacuum | — |
| [behaviors.md](behaviors.md) | Parsed only | Tags parsed from config | NOT used for validation or feature discovery |
| [depends_on.md](depends_on.md) | Implemented | Build ordering, dependency resolution | — |
| [data_classes.md](data_classes.md) | Implemented | All 27 dataclasses mirror YAML | — |
| [base_templates.md](base_templates.md) | Implemented | Inheritance, canonical fields, merge | — |

**Legend**: Implemented = works in build pipeline. Parsed only = config loader reads it but build ignores it. Planned = not built yet.
