# Clover MA Analytics Platform — Architecture Brief

**Status:** Brainstorm / Pre-Design  
**Date:** 2026-06-30  
**Author:** Chris Hunter

---

## Executive Summary

Medicare Advantage is a capital allocation problem. Every dollar of premium revenue is committed against a projected cost of care, and the accuracy of that projection — at the member level, in near real time — determines whether the business performs. Risk adjustment ties member health status to premium, and coding accuracy is what makes risk adjustment trustworthy. When coding is wrong, capital is deployed against the wrong picture of a member's health. That error compounds: it flows into STARS calculations, encounter submissions, actuarial reserves, and ultimately into plan bids priced against a flawed baseline.

This platform is an investment in the accuracy of that picture.

### The Problem

The data exists. Clover operates 1,700 dbt models transforming data from 145 vendor sources across claims, pharmacy, EHR, care engagement, quality measures, and provider networks — all landing in a governed Snowflake warehouse. The clinical review system (Veritas) is built and approaching production. The actuarial team has the models and the domain knowledge.

What does not yet exist is the layer that makes all of this **queryable together, fast, by the people who need it** — and a structured mechanism to turn clinical review into durable model signal that improves over time.

### Architecture in Brief

The platform rests on three interconnected components:

**Query engine over the Snowflake mart layer.** A FastAPI service that accepts declarative exhibit configurations — short YAML blocks expressing what fields, filters, groupings, and aggregations are needed — and translates them into SQL executed against `CLOVER_MA_PROD.MART`. Field references and join paths are resolved automatically from the dbt `manifest.json`, which encodes the full model dependency and relationship graph. Analysts express intent; the engine handles execution. No SQL required, no data pull request, no latency between question and answer.

**Interactive exhibit dashboards.** A React frontend rendering configurable exhibit canvases — line charts, pivot tables, metric cards, heatmaps, detail tables — over any mart domain. Filter controls in a persistent sidebar propagate reactively to all exhibits on a page. An actuarial analyst can configure a claims exhibit, apply filters for plan year and HCG group, and share that view with another team member in the same session. Domain pages for core claims, finance, HEDIS, Stars, payment integrity, and CA visit analytics ship as initial workspaces.

**Clinical coding review and model refinement loop.** LLM extraction runs produce ICD-10 diagnosis findings from member charts. Clinical coders review findings in a split-view workspace alongside the member's chart PDF, recording verdicts, confidence scores (1–5), and correction notes. Critically: the same exhibit engine that powers the analytics workspace is embedded in the review interface. When reviewing a finding for a member with suspected heart failure, the coder can open a supporting exhibit showing that member's prior cardiac claims, HEDIS cardiovascular gaps, and inpatient history — without leaving the review screen. The coder's verdict is richer because their context is richer.

### Enabling Code Review by Bringing Model Results Together

The clinical review workspace is not just a validation interface — it is a **convergence point** for everything the Clover data environment knows about a member at the moment of chart review. The LLM extraction result is one input. The MART data is another. The system surfaces both in the same screen, pre-filtered to the member and date of service, and lets the coder connect them.

This matters architecturally because it means coding decisions are no longer made in isolation against a single PDF. A coder who can see that a member has three prior heart failure hospitalizations in `core_claims` will be more confident confirming an ICD-10 code for CHF than a coder who only sees the chart text. Confidence 5 from that coder is a stronger signal than confidence 3 from a coder who had no supporting context. The system captures both, labeled differently, and the model training loop knows the difference.

Over time, the features that drove high-confidence coder confirmations — claims patterns, pharmacy fills, HEDIS gaps, lab values, engagement history — become training signal for the next model iteration. The LLM learns not just from the text of the chart but from the full member record that informed the coder's decision.

### Model Deploy and Retraining: The LLM-to-Lightweight Pipeline

Large language models are the right tool for the extraction phase: reading unstructured clinical text, identifying diagnoses, citing evidence pages, handling the variability of real-world medical documentation. They are not the right tool for production inference at scale — they are expensive, slow, and opaque.

The architecture treats the LLM as a **teacher, not a production model.**

The LLM runs in batch extraction mode against a chart corpus. Coders review and refine the outputs, producing a labeled dataset: chart text + structured member context → confirmed ICD-10 codes, confidence weights, correction notes, and supporting evidence references. That labeled dataset is the training corpus for a lighter-weight model — a fine-tuned smaller language model, a gradient-boosted classifier over structured features, or a retrieval-augmented system that matches chart excerpts against a curated evidence index — designed to run cheaply at inference time.

The retraining loop is:

```
LLM batch extraction
        ↓
Coder review → labeled dataset (findings + confidence + corrections)
        ↓
Veritas AlloyDB → Airbyte → Snowflake MART (veritas domain)
        ↓
dbt models: precision, recall, confidence distribution, coder agreement
        ↓
Training loop exhibits (visible in platform — no spreadsheets)
        ↓
Retrain lightweight model on labeled corpus
        ↓
Deploy lightweight model for production inference
        ↓
Spot-check with LLM on edge cases and new chart types
        ↓
Repeat
```

The LLM is never retired — it remains the standard for difficult cases, new data sources, and periodic full-corpus re-evaluation. But the production path for most charts runs through the lightweight model, which is faster, cheaper, and auditable against the labeled training set that coders produced.

Model versioning is managed through an artifact registry (version number, training corpus snapshot, performance metrics, promotion status). Promoting a new model version to production is a UI action in the training loop workspace, backed by the exhibit comparison that shows precision, recall, and cost delta versus the prior version. The decision is data-driven and visible to the team.

### The Member Journey

A member is not a snapshot. They are a trajectory — enrollment, primary care engagement, diagnoses, claims, pharmacy fills, care gaps, risk score evolution, cost. Today that trajectory must be assembled manually from multiple systems. This platform makes it continuous, queryable, and fast.

As the model matures, it is not extracting ICD-10 codes from a PDF in isolation. It is connecting the chart text to the member's claims history, their engagement patterns, their pharmacy fills, and their lab results — every structured signal the Clover data environment captures. The coding system becomes a **member health inference engine** that feeds into risk adjustment, STARS analytics, encounter submissions, and actuarial modeling simultaneously.

New data sources — a new lab vendor, a new EHR integration, a new encounter feed — can be registered as context sources without platform code changes. The model absorbs new signal; the actuarial estimates improve; the capital allocation becomes more accurate.

### The Actuarial Payoff

- **Faster reserve readouts.** Exhibit dashboards over finance mart models mean actuarial analysts configure and share analysis directly, without a data pull queue.
- **Risk score accuracy feeds pricing.** More accurate ICD-10 coding → more accurate RAF scores → more accurate projected cost of care → plan bids that reflect actual member risk.
- **Payment integrity as a configurable exhibit.** Overpayment identification, recovery tracking, and trend analysis are dashboards, not one-off queries.
- **Compounding return on the model.** Each coding cycle produces more labeled data. Each retraining cycle produces a more accurate model. Each more accurate model produces better risk scores. The actuarial estimates improve continuously, not in discrete annual cycles.

This is the infrastructure for accurate capital deployment. It starts with interactive analytics and a coding review loop. It scales to a member health inference system that connects every data source Clover operates into a single, continuously improving view of member risk.

---

## Overview

A purpose-built internal analytics and clinical review platform for the Clover Medicare Advantage line of business. The platform operates entirely within the Clover data environment — Snowflake as the warehouse, dbt mart models as the semantic layer, GCP for deployment — with no dependency on external data systems.

The design is inspired by prior exploratory work on interactive exhibit-based analytics (filter-driven dashboards, graph-resolved SQL, composable visualizations) but is built clean for a production Clover environment. The emphasis is on **formatting simplicity for the end user** — analysts and clinical coders should be able to express what they want to see in a few lines of configuration, and the platform handles query construction, joins, and rendering.

The platform has two distinct products sharing a common query engine and UI shell:

1. **Analytics Workspace** — interactive exhibit dashboards over MART data
2. **Clinical Review Portal** — LLM-assisted ICD-10 extraction with human coder review, confidence scoring, and a model refinement loop

---

## Table of Contents

1. [Guiding Principles](#1-guiding-principles)
2. [Data Layer](#2-data-layer)
3. [Query Engine](#3-query-engine)
4. [Frontend Shell & UX Philosophy](#4-frontend-shell--ux-philosophy)
5. [Analytics Workspace](#5-analytics-workspace)
6. [Clinical Review Portal](#6-clinical-review-portal)
7. [Model Training Loop](#7-model-training-loop)
8. [Deployment Architecture](#8-deployment-architecture)
9. [Phasing](#9-phasing)
10. [Open Questions](#10-open-questions)

---

## 1. Guiding Principles

### Snowflake is the only data source
No intermediate data lake, no local DuckDB Silver tables, no Bronze ingestion layer. The platform reads from `CLOVER_MA_PROD.MART` and `CLOVER_MA_PROD.STAGING` via the Snowflake connector. dbt's mart models are the semantic layer — if a domain doesn't have a mart model, the answer is to add one to clover-ma-pipelines, not to add a workaround here.

### Configuration, not code, for analysts
An analyst should be able to add a new exhibit — a chart, a pivot, a metric card — by writing a short YAML or JSON block, not by writing TypeScript. The query engine resolves what to join, how to filter, and how to aggregate. The exhibit config expresses intent; the engine executes it.

Inspired by the de_Funk exhibit block format but redesigned: simpler field references, no dual-backend abstraction, no markdown frontmatter quirks.

### The UI is the product
Rich, interactive, responsive. Filter changes re-render exhibits reactively. Coders should never feel like they are using an internal tool. The review workspace in particular needs to feel like a focused clinical instrument, not a CRUD app.

### PHI discipline
Member IDs, claim IDs, chart IDs never appear in URLs. All sensitive lookups are POST with body params. This is enforced architecturally, not by convention.

### Snowflake auth matches org standards
`externalbrowser` (SSO via Okta) for human sessions. RSA key-pair for service accounts. No passwords anywhere.

---

## 2. Data Layer

### Source of truth: CLOVER_MA_PROD.MART

The platform treats dbt mart models as a stable, documented semantic layer. The query engine maps exhibit field references to mart table columns. Adding a new domain means adding mart models in clover-ma-pipelines and registering the exhibit config — no platform code changes.

**Primary mart domains in scope (initial):**

| Domain | Key Tables | Use Case |
|---|---|---|
| Core | `core_members`, `core_claims`, `core_enrollments` | Member panels, claim detail |
| HEDIS | `hedis_claims`, `hedis_measures`, `hedis_intervention_targets` | Quality measure dashboards |
| Stars | `stars_measure_performance`, `stars_member_compliance` | Stars rating exhibits |
| Finance | `finance_claim_lines`, `finance_hcg_input`, `finance_capitation` | Actuarial exhibits |
| Payment Integrity | `pi_identification`, `pi_overpayment_concept`, `pi_recovery_tracking` | PI review exhibits |
| CA Visit Value | `ca_visits`, `ca_visit_quality`, `ca_member_high_contact` | CA engagement analytics |
| Clinical | `clinical_provider_specialties`, `clinical_authorization` | Provider and auth exhibits |

**Veritas mirror (Phase 2+):**

Coder review data (ICD-10 verdicts, confidence scores, prompt run metrics) mirrors from the Veritas PostgreSQL/AlloyDB into Snowflake via Airbyte. This lands in a new dbt mart domain `mart/veritas/` and enables joins between coder outcomes and MART member/claims data.

```
mart/veritas/
  veritas_prompt_runs.sql        -- aggregate metrics per prompt version
  veritas_chart_codings.sql      -- codings joined to core_members, core_claims
  veritas_coder_agreement.sql    -- agreement rates by ICD-10
  veritas_model_performance.sql  -- precision/recall by prompt version x ICD-10 x domain
```

### Join graph: dbt manifest

dbt produces a `manifest.json` at compile time containing the full model dependency graph, column-level docs, and relationship tests. The query engine loads this at startup to build the join graph — no hand-authored edge declarations. When a mart model adds a `relationships` test between two tables, the join becomes available to the query engine automatically.

---

## 3. Query Engine

### Role

The query engine sits between the frontend and Snowflake. It accepts a declarative exhibit payload (field references, filters, groupings, aggregations) and produces SQL that executes against the MART schema. It returns shaped response data the frontend renders directly.

It is not an ORM. It does not model business logic. It translates exhibit intent into SQL.

### Field resolution

Exhibit configs reference fields as `domain.table.column` (e.g. `core.claims.paid_amount`, `hedis.measures.numerator_flag`). The resolver maps these to physical `CLOVER_MA_PROD.MART.TABLE_NAME.COLUMN_NAME` references using a field index built from the dbt manifest at startup.

If a field reference doesn't resolve, it is an error — not a silent fallback.

### Join resolution

The engine determines the join path between tables involved in a query by traversing the manifest relationship graph (BFS). For most exhibit queries this is 1–2 joins. Complex queries with 3+ tables surface a warning in the response metadata.

Joins are always explicit — no implicit cross joins, no star schema assumptions baked in. If the manifest doesn't declare a relationship between two tables, the query fails with a clear message rather than producing a cartesian product.

### Filter system

Three filter scopes applied in order:

1. **Page filters** — set by the user in the filter sidebar; apply to all exhibits on the page unless a specific exhibit opts out
2. **Exhibit filters** — declared in the exhibit config; always applied regardless of page filter state
3. **Inline filters** — hardcoded in the exhibit payload for specific display logic (e.g. "only show claims in the current plan year")

Filter operators: `eq`, `in`, `between`, `gte`, `lte`, `like`, `is_null`, `is_not_null`.

Date filters accept ISO strings and support relative expressions (`last_12_months`, `ytd`, `prior_year`) resolved server-side to absolute date ranges before SQL generation.

### Aggregation

Measure definitions include field, aggregation function (`sum`, `avg`, `count`, `count_distinct`, `min`, `max`), display format (`$`, `%`, `,`, `integer`), and optional label override.

Window functions (YoY delta, running total, rank) are declared as a separate `windows` array in the exhibit config, not inlined into measure definitions.

### Response format

Every query response includes:

```json
{
  "type": "plotly.line",
  "series": [...],
  "metadata": {
    "row_count": 1240,
    "sql_ms": 843,
    "truncated": false,
    "warnings": []
  }
}
```

The frontend never constructs SQL. It never inspects table names. It receives shaped data and renders it.

### Technology

- **Language:** Python (FastAPI)
- **Snowflake:** `snowflake-connector-python`, `externalbrowser` for dev, RSA key-pair for service accounts
- **Manifest loading:** parsed from dbt `manifest.json` at startup; refreshed on a configurable interval or on-demand
- **Deployment:** Cloud Run (stateless, horizontally scalable)

---

## 4. Frontend Shell & UX Philosophy

### Technology

- **Framework:** React 19 + TypeScript
- **Routing:** TanStack Router (file-based)
- **State:** TanStack Query (server state), Zustand (UI state)
- **Styling:** Tailwind CSS v4 + shadcn/ui components
- **Charts:** Plotly.js
- **Tables:** TanStack Table
- **Build:** Vite

This matches the Veritas frontend stack exactly. Shared components live in `frontend/shared/`.

### The exhibit model

The UI is built around a concept of **exhibits** — discrete visualizations that each represent one query. An exhibit has a type, a data config, and a formatting config. Types:

| Type | Description |
|---|---|
| `chart.line` | Time series line chart |
| `chart.bar` | Categorical bar chart (grouped or stacked) |
| `chart.area` | Stacked area chart |
| `chart.scatter` | Scatter / bubble |
| `chart.pie` | Pie / donut |
| `table.data` | Flat sortable/paginated table |
| `table.pivot` | Cross-tab pivot with expandable rows |
| `cards.metric` | KPI metric cards with optional delta |
| `chart.heatmap` | Calendar or matrix heatmap |

Exhibit configs are short. An analyst writing a new exhibit should be able to express it in under 15 lines of YAML. The engine handles the rest.

**Example exhibit config:**

```yaml
type: chart.line
data:
  x: core.claims.service_date
  y:
    - field: core.claims.paid_amount
      aggregation: sum
      format: $
      label: Paid Amount
  group_by: core.claims.place_of_service_code
  sort:
    field: core.claims.service_date
    dir: asc
formatting:
  title: Monthly Paid Claims by Place of Service
  height: 400
```

That's it. No SQL. No joins specified. No table names.

### Filter sidebar

A persistent sidebar panel containing:

- **Page filters** — filter controls declared at the workspace level. Select pickers (searchable, multi-select with tag chips), date range pickers, numeric range inputs.
- **Exhibit controls** — per-exhibit interactive controls: dimension switcher (what to group by), measure selector, sort order toggle.

Filter changes propagate to all exhibits on the page via a reactive event bus. Each exhibit re-fetches when any relevant filter changes. Concurrent identical requests are deduplicated — if the same query is already in-flight, the second call waits for the first result.

Select pickers support **context filters**: a picker for `member_id` can declare that it should refetch its available values when the `plan_year` filter changes. The available set narrows dynamically.

### UX tone

- No empty states that just say "No data." — exhibit frames render a skeleton while loading and surface a clear message if the query returns no rows, including a suggested filter adjustment if detectable.
- No debug information visible to users by default. A collapsible footer on each exhibit shows the active filters and approximate row count for power users.
- Filter sidebar collapses to an icon rail on narrow viewports.
- Page-level filter changes animate smoothly; exhibits update in place rather than unmounting/remounting.

---

## 5. Analytics Workspace

### Concept

A configurable dashboard environment where analysts define pages of exhibits driven by shared filters. Pages are organized by domain (one page per major mart domain). The filter sidebar applies globally across all exhibits on a page.

### Page structure

Each workspace page has:
- A YAML/JSON config declaring the filter definitions and exhibit layout
- A grid of exhibit slots (resizable, drag-to-reorder in edit mode)
- A persistent filter sidebar
- An optional control panel for per-exhibit interactive controls

Workspace configs are stored in the application database (not hardcoded). Analysts with editor access can modify them through an edit mode UI. Read-only users see the current published state.

### Initial domains

**Core Member Panel**
Filters: `plan_year`, `member_id` (context-filtered), `county`, `pcp_npi`
Exhibits: member enrollment trend (line), member months by plan type (stacked bar), disenrollment reason breakdown (pie), member detail table

**HEDIS Quality**
Filters: `plan_year`, `measure_id`, `provider_npi`
Exhibits: measure performance vs. benchmark (bar), member compliance rate by measure (heatmap), intervention target count trend (line), gap closure metric cards

**Stars Performance**
Filters: `plan_year`, `star_domain`
Exhibits: domain score trend (line), measure-level score table, member compliance by star measure (pivot), overall rating metric card

**Payment Integrity**
Filters: `plan_year`, `pi_category`, `vendor`
Exhibits: identification count by category (bar), recovery tracking by quarter (line), overpayment amount metric cards, case detail table

**Finance / Actuarial**
Filters: `plan_year`, `claim_type`, `hcg_group`
Exhibits: paid claims PMPM trend (line), capitation vs. claims comparison (dual-axis), HCG distribution (bar), claim line detail table

### Exhibit edit mode

Users with editor access can:
- Add / remove / reorder exhibits on a page
- Edit exhibit YAML config in an embedded editor with live preview
- Adjust filter declarations (add/remove/reorder sidebar controls)
- Publish changes (versioned — prior state is recoverable)

---

## 6. Clinical Review Portal

### Concept

A focused clinical instrument for reviewing LLM-extracted ICD-10 diagnoses from member medical charts. Coders work through a queue of completed LLM extraction runs, confirming or denying each finding, adding missed codes, and recording confidence and supporting evidence. The portal connects directly to Analytics Workspace exhibits so coders can pull up relevant member/claim history without leaving the review context.

This is the Veritas coding studio, extended with richer exhibit integration and structured confidence signal.

### Review queue

A paginated list of completed extraction runs. Columns: member (masked), chart date, model used, number of findings, review status (unreviewed / in progress / complete), assigned coder.

Coder takes the next available chart ("Take next") or selects from the queue. The claim is atomic — no two coders can be assigned the same chart simultaneously.

### Review workspace layout

```
┌──────────────────────────┬─────────────────────────────────────────┐
│   Chart PDF              │   Findings Panel                        │
│                          │                                         │
│   [Scrollable PDF viewer]│   ICD-10: F41.1 — Generalized Anxiety  │
│                          │   Evidence: "...patient reports chronic │
│   Page jump on           │   worry and sleep disturbance..." p.4  │
│   finding click          │                                         │
│                          │   [CONFIRM]  [DENY]  [EDIT CODE]        │
│                          │   Confidence: ●●●●○  (4/5)             │
│                          │   Note: ___________________________     │
│                          │                                         │
│                          │   ─────────────────────────────────     │
│                          │                                         │
│                          │   ICD-10: I50.9 — Heart Failure        │
│                          │   Evidence: "EF 35%..." p.11           │
│                          │   [CONFIRM]  [DENY]  [EDIT CODE]        │
│                          │   Confidence: ●●●●●  (5/5)             │
│                          │                                         │
│                          │   ─────────────────────────────────     │
│                          │                                         │
│                          │   [+ Add missed code]                   │
│                          │                                         │
│                          │   ─────────────────────────────────     │
│                          │   [Supporting Exhibits ▼]               │
│                          │   [FINISH & STOP] [FINISH & NEXT]       │
└──────────────────────────┴─────────────────────────────────────────┘
```

### Confidence signal

Each finding verdict includes a 1–5 confidence rating (star or dot scale). This is not decorative — it becomes the label weight in the training loop. A coder who confirms a code at confidence 2 is saying "I think this is right but the evidence is thin." That signal is materially different from a confidence 5 confirmation and should be treated differently when evaluating model performance.

Confidence is required before a finding can be marked complete.

### Supporting exhibits drawer

A collapsible panel at the bottom of the findings column. When expanded, it renders one or more Analytics Workspace exhibits pre-filtered to the member and date-of-service of the chart being reviewed.

Example: reviewing a chart for a member with a suspected CHF finding — the supporting exhibit drawer shows:
- A table of the member's prior inpatient claims filtered to cardiac DRG groups
- A metric card showing number of ED visits in the past 12 months
- A HEDIS compliance card for cardiovascular measures

Coders can also attach a specific exhibit view to a finding verdict — recording "this claim history is the additional evidence that supported my decision." This becomes a reference link stored on the `ChartCoding` record.

### Schema additions to Veritas

New fields on `ChartCoding`:
- `confidence` — integer 1–5 (required)
- `correction_note` — text (optional, coder free text)
- `supporting_exhibit_snapshot` — JSONB (optional, serialized exhibit state at time of submission)

These additions do not break the existing multi-pass review architecture. A different coder in a QA pass will record their own confidence independently.

---

## 7. Model Training Loop

### Concept

A workspace for the team managing LLM prompt versions. Surfaces coder outcome data as analytics exhibits — the same exhibit engine, pointed at the `veritas` mart domain — and provides tooling to compare prompt versions, promote a version to production, and track refinement over time.

### Prompt version management

Prompts are versioned (already the case in Veritas: `name + version_number`). The training loop UI adds:

- Side-by-side prompt diff viewer (A/B comparison)
- Run the same chart set against two prompt versions and compare extraction outcomes
- "Promote to production" button that updates a config record read by the worker — no code deploy required

### Performance exhibits

The `veritas` mart domain (Snowflake mirror of AlloyDB) enables standard exhibit-style dashboards for model performance:

- **Precision by ICD-10 code** — for each code, what fraction of LLM findings were confirmed by coders? (pivot table)
- **Recall by ICD-10 code** — for each code, what fraction of coder-added codes were missed by the LLM? (pivot table)
- **Confidence distribution** — histogram of coder confidence scores by prompt version
- **Cost per chart** — token cost trend by model and prompt version (line chart)
- **Coder agreement rate** — where multi-pass reviews exist, agreement rate between primary and QA coder (metric card)
- **Version comparison** — for a selected pair of prompt versions, a side-by-side metric card set showing the delta in precision, recall, cost, and agreement

All of these are standard exhibits. No custom visualization code.

### Feedback loop

```
LLM extraction run
       ↓
Coder review (confirm / deny / add / confidence)
       ↓
Veritas AlloyDB → Airbyte → Snowflake MART (veritas domain)
       ↓
dbt models: veritas_model_performance, veritas_coder_agreement
       ↓
Training loop exhibits (precision, recall, confidence distribution)
       ↓
Prompt refinement decision (promote / iterate / A/B test)
       ↓
Updated prompt version → LLM extraction run (next batch)
```

The loop is visible end-to-end in the platform. The decision to promote a prompt version is data-driven and made within the same UI that shows the evidence.

---

## 8. Deployment Architecture

All components run within Clover's existing GCP environment.

| Component | Type | Notes |
|---|---|---|
| Query engine API | Cloud Run service | Stateless, horizontally scalable. Reads from Snowflake via RSA key-pair. |
| React SPA | Cloud Run service | Served by a minimal Python/Node static server, or Django shell matching Veritas pattern. |
| Veritas Django app | Cloud Run service | Extended with confidence fields and exhibit drawer API. |
| Veritas worker | Cloud Run Job | Unchanged. |
| Airbyte mirror | Existing Airbyte | New AlloyDB → Snowflake connector for veritas domain. |
| dbt `veritas` domain | clover-ma-pipelines | New mart subfolder, new transformation DAG config. |

**Auth:** Okta SSO (SAML2) across all surfaces — same session for Analytics Workspace and Clinical Review Portal. The query engine accepts a service account token for server-to-server calls.

**Secrets:** Google Cloud Secret Manager. Snowflake RSA private key for the query engine service account. No passwords anywhere.

**Environments:** Staging (`CLOVER_MA_STAGING`) and Production (`CLOVER_MA_PROD`). The query engine's Snowflake target schema is configurable via environment variable.

---

## 9. Phasing

### Phase 1 — Query Engine + Analytics Workspace

**Deliverables:**
- FastAPI query engine resolving against `CLOVER_MA_PROD.MART`
- Field resolver seeded from dbt `manifest.json`
- Join graph from dbt relationship tests
- Core exhibit types: `chart.line`, `chart.bar`, `table.data`, `cards.metric`
- React SPA shell with filter sidebar and exhibit grid
- Initial workspace pages: Core Member Panel, HEDIS Quality, Stars Performance

**Success criteria:** An analyst can define a new exhibit in YAML, see it rendered against live MART data, and apply page-level filters that reactively update all exhibits.

### Phase 2 — Full Exhibit Suite + Review Portal

**Deliverables:**
- Remaining exhibit types: `table.pivot`, `chart.area`, `chart.scatter`, `chart.heatmap`
- Edit mode (workspace config management in UI)
- Clinical Review Portal with confidence scoring and correction notes
- Supporting exhibit drawer (pre-filtered exhibit embedded in review UI)
- Finance / Actuarial and Payment Integrity workspace pages

**Success criteria:** Coders can complete a review queue, record confidence, and open a supporting exhibit without leaving the review workspace.

### Phase 3 — Training Loop + Veritas Integration

**Deliverables:**
- Airbyte AlloyDB → Snowflake mirror
- dbt `veritas` mart domain
- Training loop workspace: precision/recall exhibits, version comparison, cost tracking
- Prompt promotion flow (promote version without code deploy)
- `supporting_exhibit_snapshot` stored on ChartCoding

**Success criteria:** A prompt version comparison can be made entirely within the platform using live coder outcome data. The decision to promote is backed by a dashboard, not a spreadsheet.

---

## 10. Open Questions

1. **Query engine auth for analysts:** Does the query engine run as a single Snowflake service account (simpler, single role), or does it forward the user's Okta identity to Snowflake for row-level security enforcement? Row-level security matters if PHI access should vary by user role.

2. **Workspace config storage:** Where do workspace configs (exhibit YAML, filter declarations) live? Options: Veritas PostgreSQL/AlloyDB (simplest, one DB), a dedicated config table in Snowflake (consistent with the warehouse-centric model), or a GCS bucket (git-like versioning). Likely AlloyDB with version history.

3. **dbt manifest refresh cadence:** The manifest drives field resolution and join graph. It should refresh after each dbt run. Options: pull from GCS after each Airflow transformation DAG, or expose a refresh endpoint the Airflow DAG pings post-run.

4. **Exhibit grid persistence:** Do workspace layouts (which exhibits, what size, what order) persist per-user or per-workspace-config? A shared config that all users see the same way is simpler; per-user layouts are more flexible.

5. **Snowflake query cost controls:** Interactive queries from analysts could be expensive if exhibits are poorly configured. Should the query engine enforce a row limit, a query timeout, or require warehouse specification per workspace? `CLOVER_MA_ACTUARIAL` warehouse is the natural default for actuarial workspaces.

6. **Pivot table depth:** The `table.pivot` type in the reference design supports expandable row groups. This requires the backend to return hierarchical data, not flat rows. How many levels of hierarchy are needed for the MA use cases? HEDIS measure → measure_category → member is 3 levels.

7. **Veritas / portal relationship:** Is the Clinical Review Portal a new section of the Veritas app (same Django backend, same deploy) or a standalone service? Sharing the Django backend is simpler operationally but couples deployment. Given the query engine is a separate service either way, a standalone portal SPA talking to both the query engine and Veritas API is probably the cleaner long-term split.
