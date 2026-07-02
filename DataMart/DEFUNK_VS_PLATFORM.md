# de_Funk vs Clover MA Analytics Platform — Comparison Summary

**Date:** 2026-07-01  
**Author:** Chris Hunter

---

## What de_Funk Was

de_Funk was a personal exploratory project — a graph-based analytical overlay built to make external financial and municipal data queryable through Obsidian notes. It was vibe-coded: ambitious architecture, several unfinished pipelines, and a handful of genuinely good ideas buried inside a system that never reached end-to-end production use.

Its value was as a proof of concept for a specific UX idea: that an analyst should be able to express what they want to see in a few lines of configuration, and a query engine should handle the rest — field resolution, join path finding, SQL generation, and rendering. That idea is sound. The implementation had real flaws.

This document summarises what was learned, what carries forward as inspiration, what gets replaced entirely, and how the Clover MA Analytics Platform is a fundamentally different thing built for a fundamentally different context.

---

## What de_Funk Got Right

### The exhibit model
The core concept — a short declarative config block that produces a fully-rendered visualization against live data — is the right abstraction. An analyst should not write SQL to see a chart. They should describe intent: what fields, what grouping, what filters, what format. The engine executes.

de_Funk proved this works. The Obsidian plugin rendered Plotly charts, pivot tables, metric cards, and detail tables from YAML blocks of under 15 lines. The Clover platform keeps this model, redesigned and built properly.

### Filter-driven reactive dashboards
The filter sidebar with pub/sub propagation — where changing one filter re-renders all exhibits on the page — is the right interaction model for analytical dashboards. The in-flight request deduplication (identical concurrent queries sharing one promise) was a particularly clean detail.

### Separating query concerns from rendering
The FieldResolver and DomainGraph separation — where field references resolve to physical columns and join paths are found by graph traversal — is architecturally correct. It means the same exhibit config works regardless of which tables are involved, and adding a new domain doesn't require touching rendering code.

### The LLM-as-teacher framing
Though de_Funk's ML pipeline was never completed, the ArtifactStore and the framing of the LLM as a batch teacher (not a production model) pointed in the right direction. The Clover platform builds that framing out properly with the feedback refinement and ensemble layer as the bridge between raw coder verdicts and a clean training corpus.

---

## What de_Funk Got Wrong

### Built its own data lake instead of using what existed
de_Funk ingested Alpha Vantage and Socrata APIs into Bronze Delta Lake tables, then ran Spark to build Silver dimensional star schemas. This was enormous infrastructure investment for a solo analytical project. In a real enterprise context — Clover specifically — the data warehouse already exists, is governed, and has 1,700 models maintained by a data engineering team. Building a parallel lake is the wrong answer.

### Obsidian as the UI host
Embedding analytics in a note-taking tool was clever for solo use but fundamentally limits the audience, the collaboration model, and the access control story. A clinical coder, a coder manager, and a chief actuary cannot all be Obsidian users with the right plugins installed. A web portal is the only viable production surface.

### Domain config in markdown frontmatter
Declaring domain models, join edges, and field schemas in markdown YAML files was a creative approach but created fragile, hard-to-maintain config with no validation, no version control story beyond git, and no UI for non-technical users to interact with. The Clover platform replaces this entirely with dbt's `manifest.json` as the field registry — already maintained, already documented, already versioned.

### The ML pipeline was scaffolded but never closed
The ArtifactStore existed. The training methods (Prophet, ARIMA, RandomForest) existed. The forecast hook was registered but not wired. The prediction endpoint existed in FastAPI but had no handler in the Obsidian plugin. The loop never closed. There was no labeled dataset, no ensemble step, no lightweight model deployment path. Good intentions, incomplete execution.

### No multi-user story
de_Funk had no authentication, no role separation, no audit trail. It was a single-user local tool. None of that is acceptable in a clinical and actuarial context where PHI discipline, role-based access, and decision traceability are requirements, not features.

---

## What the Clover Platform Replaces Entirely

| de_Funk Component | Replacement |
|---|---|
| Bronze ingestion (Alpha Vantage, Socrata) | clover-ma-pipelines parsers, Airbyte, dbt staging |
| Silver / domain model build (Spark) | dbt mart models in Snowflake — already exists |
| Domain config (markdown YAML EdgeSpecs) | dbt `manifest.json` — field registry and join graph |
| Obsidian plugin as UI | React SPA portal |
| Local Delta Lake storage | Snowflake MART + AlloyDB |
| No auth | Okta SSO (SAML2) — already in Veritas |
| ArtifactStore (local pickle + JSON) | GCS for artifacts, AlloyDB for model registry metadata |

---

## What the Clover Platform Is Inspired By

| de_Funk Idea | How It Appears in the Clover Platform |
|---|---|
| Exhibit config blocks (short YAML → rendered viz) | Same model, redesigned. Workspace Builder lets CA team configure exhibits without SQL. |
| FieldResolver (domain.field → physical column) | Query Service resolves field references from dbt manifest at startup |
| DomainGraph (BFS join resolution) | Join paths derived from dbt relationship tests in manifest — no hand-authored edges |
| Filter sidebar with pub/sub | React filter sidebar, same reactive propagation model, framework-agnostic |
| In-flight request deduplication | Carried into the Query Service |
| LLM as batch teacher | Fully built out: LLM extraction → coder review → feedback refinement & ensemble → lightweight model inference |

The exhibit UX is the primary inheritance. Everything else is rebuilt from scratch for the Clover environment.

---

## The Fundamental Difference

de_Funk was built around the question: *how do I make external data queryable for myself?*

The Clover MA Analytics Platform is built around the question: *how does the actuarial team get accurate, fast, continuously improving readouts of member risk — and how does clinical review feed back into that accuracy?*

The scope is different. The users are different. The data is different. The stakes are different.

de_Funk proved that the exhibit model works and that a graph-resolved query engine is the right abstraction. The Clover platform takes that proof and builds a production system on top of infrastructure — Snowflake, dbt, Veritas, GCP — that already exists and already governs the data.

---

## What Is Net New

None of the following exists in de_Funk or Veritas today:

- **Analytics Workspace** — configurable exhibit dashboards over CLOVER_MA_PROD.MART for actuarial and operational domains
- **Workspace Builder** — UI for the Chief Actuary team to configure exhibit pages, filter sidebars, and exhibit controls without code
- **Review Workspace enriched with supporting exhibits** — coder sees member claims history, HEDIS gaps, and risk scores in the same screen as the chart PDF
- **Confidence scoring and structured correction types** — coder verdicts as weighted training signal, not just binary decisions
- **Feedback Refinement & Ensemble** — multi-coder verdict reconciliation step that produces a clean labeled dataset before training
- **Ops Dashboard with write capability** — coder assignment, pipeline health, queue management
- **Pre-pay inference** — trajectory-based auto-approve or hold recommendation for claims before payment
- **Post-pay audit** — code gap analysis between claim codes and chart-confirmed codes
- **HCC capture tracking** — confirmed codes mapped to HCC, RAF weight, and gap against current-year submissions
- **Data Service Layer** — explicit write/query separation so IT has a clean boundary to design behind
- **Model Inference as a parallel path to LLM** — lightweight model running production charts cheaply alongside LLM for edge cases

---

## One-Line Summary

de_Funk was a solo proof of concept that showed the exhibit model works. The Clover MA Analytics Platform is the production version of that idea, built on Clover's actual data infrastructure, extended with a clinical review loop, a feedback refinement pipeline, and a model inference system — all aimed at one thing: more accurate capital deployment through better member risk readouts.
