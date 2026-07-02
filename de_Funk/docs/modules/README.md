# Module Documentation

Per-group architectural documentation for de_Funk. Each document covers one architectural concern: purpose, key classes, usage examples, triage guidance, and design decisions.

## Which Doc Do I Need?

| I want to... | Read |
|---|---|
| Understand how the app starts up | [01 Application](01-application.md) |
| Add a new YAML config field | [02 Configuration](02-configuration.md) |
| Understand how queries execute | [03 Engine & Sessions](03-engine-sessions.md) |
| Debug a join path or field resolution error | [04 Graph & Resolution](04-graph-resolution.md) |
| Add a new exhibit type or fix a handler | [05 API](05-api.md) |
| Add a new domain model or hook | [06 Build Pipeline](06-build-pipeline.md) |
| Fix ingestion errors or add a provider | [07 Ingestion](07-ingestion.md) |
| Schedule or checkpoint a pipeline | [08 Orchestration](08-orchestration.md) |
| Understand an exception or add error handling | [09 Error Handling](09-error-handling.md) |
| Configure logging or debug log output | [10 Logging](10-logging.md) |
| Find utility helpers | [11 Utilities](11-utilities.md) |
| Work on the Obsidian plugin | [12 Obsidian Plugin](12-obsidian-plugin.md) |

## Document Index

| # | Module | Classes | Status |
|---|---|---|---|
| 01 | [Application](01-application.md) | 1 | draft |
| 02 | [Configuration & Data Classes](02-configuration.md) | 40 | draft |
| 03 | [Engine & Sessions](03-engine-sessions.md) | 17 | draft |
| 04 | [Graph & Resolution](04-graph-resolution.md) | 6 | draft |
| 05 | [API Layer](05-api.md) | 30 | draft |
| 06 | [Build Pipeline & Hooks](06-build-pipeline.md) | 14 | draft |
| 07 | [Ingestion Pipeline](07-ingestion.md) | 41 | draft |
| 08 | [Orchestration](08-orchestration.md) | 5 | draft |
| 09 | [Error Handling](09-error-handling.md) | 26 | draft |
| 10 | [Logging](10-logging.md) | 4 | draft |
| 11 | [Utilities](11-utilities.md) | 3 | draft |
| 12 | [Obsidian Plugin](12-obsidian-plugin.md) | — | draft |

## Relationship to Other Docs

| Existing Doc | What It Covers | These Module Docs Add |
|---|---|---|
| [architecture.md](../architecture.md) | System-level overview, execution paths | Per-group detail, class-level guidance |
| [python-reference.md](../python-reference.md) | Exhaustive class catalog | "Guided tour" with triage and design decisions |
| [internals.md](../internals.md) | Tutorial walkthrough | Systematic coverage of all groups |
| [data-pipeline.md](../data-pipeline.md) | End-to-end pipeline guide | Code-level ingestion and build details |

## Regenerating

```bash
# Regenerate all (overwrites existing)
python -m scripts.docs.scaffold_module_docs --force

# Check staleness
python -m scripts.docs.scaffold_module_docs --check
```
