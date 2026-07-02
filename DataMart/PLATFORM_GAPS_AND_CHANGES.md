# Platform Gap Analysis — What Needs to Change

**Status:** Brainstorm / Pre-Design  
**Date:** 2026-07-01  
**Author:** Chris Hunter  
**Reference:** ANALYTICS_PLATFORM.md, EXECUTIVE_SUMMARY.md

---

## Context

This document maps the vision in the Analytics Platform brief against what exists today in the Veritas (claims-accuracy) codebase. It breaks down required changes by user type and workflow, then summarizes schema, API, and service gaps across pre-pay, post-pay, HCC capture, and model retraining.

The Veritas codebase is well-built. The durable queue, LLM extraction pipeline, and per-chunk cost accounting are solid foundations. What is missing is the **structured signal layer** — the schema, API, and UI additions that let a coder's verdict, a manager's oversight view, and a model trainer's performance analysis all feed back into an improving system.

---

## User Types and What Each Needs

### 1. Clinical Coder

**Current state:** Reviews LLM-extracted ICD-10 findings from chart PDFs. Can confirm, deny, or add codes. Records an optional free-text note and evidence page. One review pass per coder per chart.

**Missing:**
- **Confidence score** — no structured confidence signal on `ChartCoding`. A confirm at low confidence is fundamentally different training signal from a high-confidence confirm. Required for weighted model retraining.
- **Claim category tagging** — no way for the coder to indicate whether a finding is relevant to pre-pay or post-pay context, or to flag it as an HCC capture opportunity. These are distinct workflows with distinct downstream consumers.
- **Supporting member context** — the coder sees the chart PDF and the LLM findings. They cannot see the member's claims history, pharmacy fills, prior risk scores, or HEDIS gaps without leaving the application. This limits coder confidence and degrades the quality of the labeled dataset.
- **Structured correction type** — `note` is free text. There is no structured enum for why a code was denied (e.g. insufficient evidence, wrong code, duplicate, not clinically supported). That structure is needed for retraining signal — the model needs to know *why* it was wrong, not just that it was wrong.

**Additions needed to `ChartCoding`:**
```
confidence          IntegerField(1–5, required)
correction_type     CharField(choices: insufficient_evidence | wrong_code |
                              duplicate | not_clinically_supported | other, nullable)
claim_context       CharField(choices: prepay | postpay | hcc_capture | unspecified)
supporting_context  JSONField(nullable) — snapshot of exhibit state at time of verdict
```

---

### 2. Coder Manager

**Current state:** No manager-level view exists. The review queue (`GET /api/coding/review/queue`) shows all reviewable charts to any authenticated user. There is no aggregation by coder, no throughput metrics, no confidence distribution, no inter-rater agreement tracking.

**What a coder manager needs:**
- **Coder throughput** — how many charts has each coder completed this week, this run, this month?
- **Confidence distribution by coder** — a coder who consistently rates confidence 1–2 is flagging uncertainty. A coder who always rates 5 may not be engaging critically.
- **Decision distribution** — what fraction of each coder's verdicts are confirm / deny / add? Outliers warrant review.
- **Inter-rater agreement** — where two coders have reviewed the same chart, do they agree? Disagreement by ICD-10 code identifies codes that need clearer guidance or prompt improvement.
- **Queue assignment** — currently coders self-assign from the queue. Managers need to be able to assign charts to specific coders or coder teams, and see assignment status.
- **Run-level progress view** — how far through a given PromptRun is the human review phase?

**New API endpoints needed:**
```
GET  /api/coding/manager/coder-summary
     → per-coder: charts_completed, avg_confidence, confirm_rate, deny_rate, add_rate

GET  /api/coding/manager/agreement
     → inter-rater agreement by ICD-10 code across runs or a specific PromptRun

GET  /api/coding/manager/run-progress/{run_id}
     → reviewed_count, unreviewed_count, in_progress_count, 
       avg_confidence, confidence_distribution

POST /api/coding/manager/assign
     → body: {chart_run_id, assigned_to_user_id}
     → creates or updates chart assignment (new ChartAssignment model)
```

**New model needed:**
```python
ChartAssignment
  chart_run        ForeignKey(ChartRun)
  assigned_to      ForeignKey(User)
  assigned_by      ForeignKey(User)
  assigned_at      DateTimeField(auto_now_add=True)
  # Unique on chart_run — one assignment at a time
```

---

### 3. Project Manager / Operations

**Current state:** No project-level view exists. A project manager cannot see across multiple PromptRuns, compare extraction performance across models or prompt versions, or track operational status of the review pipeline.

**What a project manager needs:**
- **Cross-run comparison** — side-by-side metrics for two PromptRuns: extraction count, review completion rate, avg confidence, top codes, cost per chart
- **Pre-pay vs post-pay pipeline tracking** — which runs are targeting which claim context? How complete is each?
- **HCC capture rate** — of charts reviewed, what fraction surfaced at least one new HCC opportunity (a code added by the coder that the LLM missed)?
- **Pipeline health** — are workers running? Are charts stuck? What is the queue depth?
- **Cost tracking** — total token spend by run, model, and date range

**New API endpoints needed:**
```
GET  /api/coding/ops/pipeline-health
     → worker_last_seen, stuck_chart_count, queue_depth, error_rate_last_24h

GET  /api/coding/ops/run-comparison?run_id_a=&run_id_b=
     → side-by-side: cost, extraction_count, review_completion, top_codes, avg_confidence

GET  /api/coding/ops/hcc-capture-rate/{run_id}
     → charts with at least one ADDED decision, rate vs total reviewed

GET  /api/coding/ops/cost-summary
     → total cost by run, by model, by date range
```

Most of these are aggregation queries over existing data — they require no schema changes. They do require new service functions and API endpoints.

---

### 4. Pre-Pay Workflow

**Concept:** Before a claim is paid, the system can evaluate whether the diagnoses and procedures on the claim are supported by the member's clinical record and trajectory. The goal is twofold: flag likely unsupported claims for review (reducing inappropriate payment) and auto-enable payment for claims where the member's trajectory makes the billed codes highly likely to be correct (reducing provider abrasion from unnecessary holds).

**Current state:** The AI PI app already queries Clover's Snowflake warehouse for claim header, claim lines, UMD flags, adjudication messages, and UDTs. It can look up a member and their recent claims. What it does not do is run a model against that data to produce a recommendation — approve, hold, or flag.

**What pre-pay needs that doesn't exist:**

1. **Pre-pay inference endpoint** — given a claim (via `claim_hcc_id`), retrieve the member's clinical context (recent diagnoses, chart-extracted codes, pharmacy fills, risk score) and produce a recommendation with a confidence score.

```
POST /api/ai-pi/prepay/evaluate
     body: {claim_hcc_id}
     response: {
       recommendation: "approve" | "hold" | "flag_for_review",
       confidence: float,
       supporting_codes: [icd10, ...],    # codes from chart extraction supporting the claim
       trajectory_signals: [...],          # MART signals that informed the decision
       model_version: str
     }
```

2. **Member trajectory context** — the current Snowflake queries in `snowflake_queries.py` pull claim header and lines for a specific claim. Pre-pay needs a **longitudinal member context query**: prior diagnoses (from chart codings and claims), RAF score history, pharmacy fills for relevant drug classes, HEDIS gaps. This is a new query function in `snowflake_queries.py` or a new service module.

3. **Feedback loop for pre-pay outcomes** — when a claim that was flagged for review is ultimately paid (or denied), that outcome needs to feed back to the model. Currently there is no outcome tracking for AI PI recommendations. A `PrepayDecision` model is needed to capture the recommendation, the human override (if any), and the final claim disposition.

```python
PrepayDecision
  claim_hcc_id     CharField
  member_id        CharField
  recommendation   CharField(choices: approve | hold | flag_for_review)
  confidence       FloatField
  model_version    CharField
  human_override   CharField(choices: approved | denied | held, nullable)
  override_reason  TextField(blank=True)
  evaluated_at     DateTimeField(auto_now_add=True)
  resolved_at      DateTimeField(nullable)
```

4. **Provider abrasion metric** — to demonstrate the value of auto-approve decisions, the system needs to track how often pre-pay approvals were correct (no subsequent denial or recoupment). This is a future analytics exhibit, not a schema addition at this stage, but the `PrepayDecision` table is the necessary prerequisite.

---

### 5. Post-Pay Workflow

**Concept:** After a claim is paid, auditing whether codes were supported and identifying overpayment recovery opportunities. This is the primary current use of AI PI.

**Current state:** AI PI supports claim lookup by `claim_hcc_id` and member lookup by `subscriber_id`. LLM review (via the coding app) extracts ICD-10 codes from charts. The gap is that the two apps are not connected — a post-pay auditor cannot start from a claim in AI PI and link directly to chart extraction results for that member.

**What post-pay needs that doesn't exist:**

1. **Claim-to-chart linkage** — given a `claim_hcc_id`, find `ChartRun` records associated with that member and date-of-service window. Currently there is no linkage between `ChartRun` (which has a `chart_id` UUID) and claim data in Snowflake. The connection has to go through `member_id + dos` → CA API documents → `chart_id`.

   A new query in `snowflake_queries.py`:
   ```python
   get_chart_ids_for_claim(claim_hcc_id: str) -> list[str]
   # Joins claim → member → document → chart_id
   ```

2. **Post-pay audit summary** — given a claim, show: which ICD-10 codes are on the claim, which codes were found in chart extraction for the same member/DOS window, and which are confirmed by a coder. Gaps between claim codes and confirmed chart codes are overpayment candidates.

```
POST /api/ai-pi/postpay/audit-summary
     body: {claim_hcc_id}
     response: {
       claim_codes: [icd10, ...],
       extracted_codes: [{icd10, confidence, status: confirmed|denied|unreviewed}, ...],
       discrepancies: [{icd10, claim_has: bool, chart_has: bool, coder_confirmed: bool}, ...]
     }
```

3. **Overpayment flagging** — codes on the claim that are not confirmed by any coder review of the associated chart are candidates for overpayment. This requires no new model — it is a join between `ClaimLine` (from Snowflake) and `ChartCoding` (from Veritas). The schema is ready; the query service and API endpoint are not.

---

### 6. HCC Capture

**Concept:** Hierarchical Condition Categories (HCCs) drive risk adjustment and therefore premium revenue. Codes present in a member's chart but not submitted on a claim represent missed HCC capture — revenue left unrealized. The coding system should surface these gaps explicitly.

**Current state:** Coders can add codes that the LLM missed (`decision = ADDED`). But the system does not know whether those added codes map to HCCs, whether those HCCs are already captured on other claims, or what the RAF impact of capturing them would be.

**What HCC capture needs:**

1. **HCC mapping on `ChartCoding`** — when a coder confirms or adds a code, the system should resolve the ICD-10 to its HCC (if any) using the CMS HCC mapping table (already in the dbt seeds: `diagnosis code mappings`). This can be done at save time in `save_coding()` and stored on `ChartCoding`.

```
hcc_code        CharField(nullable)    # CMS HCC number if code maps to an HCC
hcc_description CharField(nullable)
raf_weight      DecimalField(nullable) # approximate RAF weight for this HCC
```

2. **HCC gap report** — for a given member, show: which HCCs are confirmed in chart review, which are already captured on claims in the current plan year, and which are new (not yet on any claim). New HCCs are capture opportunities.

```
GET /api/coding/hcc/member-gap/{member_id}?plan_year=
    response: {
      confirmed_hccs: [{hcc, icd10, raf_weight, on_claim: bool}, ...],
      capture_opportunities: [{hcc, icd10, raf_weight, evidence_chart_id}, ...]
    }
```

   This requires a Snowflake query for the member's current-year HCC submissions (from `core_claims` or a HEDIS/Stars mart table) joined against confirmed `ChartCoding` rows.

3. **Run-level HCC summary** — across a PromptRun, how many unique HCCs were confirmed? How many were new (not on any claim)? What is the estimated aggregate RAF uplift? This is a management exhibit, not a real-time API call.

---

## Structured Feedback for Retraining

This is the most important gap. The current system produces labeled data (confirm/deny/add decisions) but that data is not structured for model training consumption. Three changes are needed:

### 1. Training dataset export

A new service function that extracts a clean, structured training dataset from `ChartCoding` rows:

```python
export_training_dataset(
    prompt_run_ids: list[int],
    min_confidence: int = 3,
    decisions: list[str] = ["CONFIRMED", "DENIED", "ADDED"]
) -> list[TrainingRecord]
```

Where `TrainingRecord` contains:
- `chart_id` — the source chart
- `chart_text_excerpt` — the evidence text the coder cited (`evidence_found`)
- `evidence_page` — page number
- `icd10` — the code
- `decision` — confirm / deny / add
- `confidence` — coder confidence (1–5, used as label weight)
- `correction_type` — structured reason for denial
- `claim_context` — prepay / postpay / hcc_capture
- `coder_id` — for inter-rater weighting
- `query_results` — Snowflake context injected at extraction time

A new endpoint:
```
POST /api/coding/training/export
     body: {prompt_run_ids, min_confidence, decisions}
     response: JSONL stream or presigned GCS URL
```

### 2. Model version registry

An artifact registry for tracking trained model versions. When the lightweight model is trained on a labeled corpus, the registry records:

```python
ModelVersion
  id               BigAutoField
  name             CharField
  version          CharField
  model_type       CharField(choices: llm_prompt | fine_tuned | classifier | retrieval)
  training_run_ids JSONField    # which PromptRun labeled data was used
  corpus_size      IntegerField # number of ChartCoding records in training set
  precision        FloatField(nullable)
  recall           FloatField(nullable)
  f1               FloatField(nullable)
  cost_per_chart   DecimalField(nullable)
  status           CharField(choices: training | staging | production | retired)
  promoted_at      DateTimeField(nullable)
  promoted_by      ForeignKey(User, nullable)
  artifact_path    CharField  # GCS path to model artifact
  created_at       DateTimeField(auto_now_add=True)
```

A new endpoint:
```
GET  /api/coding/models              → list of ModelVersion
POST /api/coding/models/{id}/promote → flips status to production, retires current
```

### 3. Performance tracking per model version

`ChartRun` gains a `model_version` foreign key (nullable, for runs executed by the lightweight model rather than an LLM prompt). This enables precision/recall comparison across model versions using the same coder review data — the same labeled dataset that validated the LLM run can validate the lightweight model's output on the same charts.

```
model_version    ForeignKey(ModelVersion, nullable)
```

This is the connection that closes the loop: the LLM extracts, coders label, the lightweight model is trained on that labeled data, the lightweight model runs on new charts, coders label those outputs, and the comparison between LLM and lightweight model performance is a query over `ChartRun` grouped by `model_version`.

---

## Summary Table: What Needs to Change

### Schema Changes (Veritas / AlloyDB)

| Model | Change | Purpose |
|---|---|---|
| `ChartCoding` | Add `confidence` (int 1–5, required) | Training label weight |
| `ChartCoding` | Add `correction_type` (enum, nullable) | Structured denial reason for retraining |
| `ChartCoding` | Add `claim_context` (enum: prepay/postpay/hcc_capture) | Workflow routing |
| `ChartCoding` | Add `supporting_context` (JSONB, nullable) | Exhibit snapshot at verdict time |
| `ChartCoding` | Add `hcc_code`, `hcc_description`, `raf_weight` | HCC capture tracking |
| `ChartRun` | Add `model_version` (FK nullable) | Lightweight model tracking |
| New: `ChartAssignment` | chart_run, assigned_to, assigned_by, assigned_at | Manager-driven queue assignment |
| New: `PrepayDecision` | claim, recommendation, confidence, human_override, model_version | Pre-pay feedback loop |
| New: `ModelVersion` | name, type, corpus, metrics, status, artifact_path | Model artifact registry |

### New API Endpoints (Veritas)

| Endpoint | Purpose |
|---|---|
| `GET /api/coding/manager/coder-summary` | Throughput and confidence by coder |
| `GET /api/coding/manager/agreement` | Inter-rater agreement by ICD-10 |
| `GET /api/coding/manager/run-progress/{run_id}` | Run-level review progress |
| `POST /api/coding/manager/assign` | Chart-to-coder assignment |
| `GET /api/coding/ops/pipeline-health` | Worker and queue status |
| `GET /api/coding/ops/run-comparison` | Cross-run performance comparison |
| `GET /api/coding/ops/hcc-capture-rate/{run_id}` | HCC add rate by run |
| `GET /api/coding/ops/cost-summary` | Token spend by run / model / date |
| `POST /api/ai-pi/prepay/evaluate` | Pre-pay recommendation for a claim |
| `POST /api/ai-pi/postpay/audit-summary` | Post-pay code gap for a claim |
| `GET /api/coding/hcc/member-gap/{member_id}` | HCC capture opportunities for a member |
| `POST /api/coding/training/export` | Labeled dataset export for retraining |
| `GET /api/coding/models` | Model version registry list |
| `POST /api/coding/models/{id}/promote` | Promote model version to production |

### New Snowflake Queries (`snowflake_queries.py`)

| Function | Purpose |
|---|---|
| `get_member_trajectory(member_id, plan_year)` | Longitudinal context: diagnoses, RAF, pharmacy, HEDIS gaps |
| `get_chart_ids_for_claim(claim_hcc_id)` | Link claim → member → chart for post-pay audit |
| `get_member_hcc_submissions(member_id, plan_year)` | Current-year HCC claims for gap analysis |
| `get_hcc_for_icd10(icd10_codes)` | Resolve ICD-10 list to HCC codes using dbt seed mapping |

### New dbt Domain: `mart/veritas/`

| Model | Purpose |
|---|---|
| `veritas_prompt_runs.sql` | PromptRun metrics: cost, extraction count, review completion |
| `veritas_chart_codings.sql` | ChartCoding joined to core_members, core_claims |
| `veritas_coder_agreement.sql` | Agreement rates by ICD-10 and coder pair |
| `veritas_model_performance.sql` | Precision / recall by model version and ICD-10 |
| `veritas_hcc_capture.sql` | HCC opportunity rate by run, member cohort, plan year |
| `veritas_prepay_outcomes.sql` | PrepayDecision outcomes vs claim adjudication |

These dbt models require Airbyte to mirror Veritas AlloyDB into Snowflake — a new connector, not a code change in clover-ma-pipelines itself.

---

## What Does Not Need to Change

- The durable queue architecture (`ChartRun.status` as queue, `SELECT FOR UPDATE SKIP LOCKED`) — this is correct and scalable.
- Per-chunk token/cost accounting on `ChartChunk` — this is the right granularity.
- The multi-pass review architecture (`ChartReview` unique on chart_run + reviewer) — supports QA passes without schema changes.
- The LLM provider abstraction in `common/llm.py` — already supports Vertex Gemini, Vertex Anthropic, LiteLLM.
- PHI exclusion from URLs — enforced and correct.
- The CA API client and chart PDF streaming — no changes needed.
- Okta SAML auth — extends naturally to the new portal surfaces.
