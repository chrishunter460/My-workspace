# Clover MA Analytics Platform — Executive Summary

**Date:** 2026-06-30  
**Author:** Chris Hunter

---

Medicare Advantage is a capital allocation problem. Every dollar of premium revenue is committed against a projected cost of care, and the accuracy of that projection — at the member level, in near real time — determines whether the business performs. Risk adjustment ties member health status to premium, and coding accuracy is what makes risk adjustment trustworthy. When coding is wrong, capital is deployed against the wrong picture of a member's health. That error compounds: it flows into STARS calculations, encounter submissions, actuarial reserves, and ultimately into plan bids priced against a flawed baseline.

This platform is an investment in the accuracy of that picture.

---

## The Problem

The data exists. Clover operates 1,700 dbt models transforming data from 145 vendor sources across claims, pharmacy, EHR, care engagement, quality measures, and provider networks — all landing in a governed Snowflake warehouse. The clinical review system (Veritas) is built and approaching production. The actuarial team has the models and the domain knowledge.

What does not yet exist is the layer that makes all of this **queryable together, fast, by the people who need it** — and a structured mechanism to turn clinical review into durable model signal that improves over time.

---

## Architecture in Brief

The platform rests on three interconnected components:

**Query engine over the Snowflake mart layer.** A FastAPI service that accepts declarative exhibit configurations — short YAML blocks expressing what fields, filters, groupings, and aggregations are needed — and translates them into SQL executed against `CLOVER_MA_PROD.MART`. Field references and join paths are resolved automatically from the dbt `manifest.json`, which encodes the full model dependency and relationship graph. Analysts express intent; the engine handles execution. No SQL required, no data pull request, no latency between question and answer.

**Interactive exhibit dashboards.** A React frontend rendering configurable exhibit canvases — line charts, pivot tables, metric cards, heatmaps, detail tables — over any mart domain. Filter controls in a persistent sidebar propagate reactively to all exhibits on a page. An actuarial analyst can configure a claims exhibit, apply filters for plan year and HCG group, and share that view with another team member in the same session. Domain pages for core claims, finance, HEDIS, Stars, payment integrity, and CA visit analytics ship as initial workspaces.

**Clinical coding review and model refinement loop.** LLM extraction runs produce ICD-10 diagnosis findings from member charts. Clinical coders review findings in a split-view workspace alongside the member's chart PDF, recording verdicts, confidence scores (1–5), and correction notes. Critically: the same exhibit engine that powers the analytics workspace is embedded in the review interface. When reviewing a finding for a member with suspected heart failure, the coder can open a supporting exhibit showing that member's prior cardiac claims, HEDIS cardiovascular gaps, and inpatient history — without leaving the review screen. The coder's verdict is richer because their context is richer.

---

## Enabling Code Review by Bringing Model Results Together

The clinical review workspace is not just a validation interface — it is a **convergence point** for everything the Clover data environment knows about a member at the moment of chart review. The LLM extraction result is one input. The MART data is another. The system surfaces both in the same screen, pre-filtered to the member and date of service, and lets the coder connect them.

This matters architecturally because it means coding decisions are no longer made in isolation against a single PDF. A coder who can see that a member has three prior heart failure hospitalizations in `core_claims` will be more confident confirming an ICD-10 code for CHF than a coder who only sees the chart text. Confidence 5 from that coder is a stronger signal than confidence 3 from a coder who had no supporting context. The system captures both, labeled differently, and the model training loop knows the difference.

Over time, the features that drove high-confidence coder confirmations — claims patterns, pharmacy fills, HEDIS gaps, lab values, engagement history — become training signal for the next model iteration. The LLM learns not just from the text of the chart but from the full member record that informed the coder's decision.

---

## Model Deploy and Retraining: The LLM-to-Lightweight Pipeline

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

Model versioning is managed through an artifact registry (version number, training corpus snapshot, performance metrics, promotion status). Promoting a new model version to production is a UI action in the training loop workspace, backed by an exhibit comparison showing precision, recall, and cost delta versus the prior version. The decision is data-driven and visible to the team.

---

## The Member Journey

A member is not a snapshot. They are a trajectory — enrollment, primary care engagement, diagnoses, claims, pharmacy fills, care gaps, risk score evolution, cost. Today that trajectory must be assembled manually from multiple systems. This platform makes it continuous, queryable, and fast.

As the model matures, it is not extracting ICD-10 codes from a PDF in isolation. It is connecting the chart text to the member's claims history, their engagement patterns, their pharmacy fills, and their lab results — every structured signal the Clover data environment captures. The coding system becomes a **member health inference engine** that feeds into risk adjustment, STARS analytics, encounter submissions, and actuarial modeling simultaneously.

New data sources — a new lab vendor, a new EHR integration, a new encounter feed — can be registered as context sources without platform code changes. The model absorbs new signal; the actuarial estimates improve; the capital allocation becomes more accurate.

---

## The Actuarial Payoff

- **Faster reserve readouts.** Exhibit dashboards over finance mart models mean actuarial analysts configure and share analysis directly, without a data pull queue.
- **Risk score accuracy feeds pricing.** More accurate ICD-10 coding → more accurate RAF scores → more accurate projected cost of care → plan bids that reflect actual member risk.
- **Payment integrity as a configurable exhibit.** Overpayment identification, recovery tracking, and trend analysis are dashboards, not one-off queries.
- **Compounding return on the model.** Each coding cycle produces more labeled data. Each retraining cycle produces a more accurate model. Each more accurate model produces better risk scores. The actuarial estimates improve continuously, not in discrete annual cycles.

This is the infrastructure for accurate capital deployment. It starts with interactive analytics and a coding review loop. It scales to a member health inference system that connects every data source Clover operates into a single, continuously improving view of member risk.
