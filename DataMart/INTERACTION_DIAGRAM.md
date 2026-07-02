# Platform Interaction Diagram

**User types:** Clinical Coder · Coder Manager · Project Manager · Chief Actuary Team  
**Renders in VS Code Markdown Preview (Ctrl+Shift+V)**

---

## 1a. Platform Overview — Simplified

```mermaid
graph LR
    subgraph USERS["User Types"]
        C(["👩‍⚕️ Clinical Coder"])
        CM(["👔 Coder Manager"])
        PM(["📊 Project Manager"])
        CA(["🏛️ Chief Actuary Team"])
    end

    subgraph CONFIG["Platform Configuration"]
        WB["Workspace Builder"]
        DF["Review Data Setup"]
    end

    subgraph PORTAL["Analytics & Review Portal"]
        RW["Review Workspace\n(incl. queue)"]
        AW["Analytics Workspace"]
        OPS["Ops Dashboard"]
        PR["Prompt Studio\n(Vertex AI · LLM Batch Runner)"]
        RM["Feedback Refinement\n& Ensemble"]
    end

    subgraph DSL["Services Layer"]
        WR["Write Service"]
        QS["Query Service"]
        CAAPI["CA API\n(Chart Access)"]
    end

    DL[("Data Layer")]

    C --> RW
    C -.->|context| AW

    CM --> RW
    CM --> OPS
    CM --> AW

    PM --> OPS
    PM --> AW

    CA --> WB
    CA --> DF
    CA --> PR
    CA --> RM
    CA --> AW

    WB --> RW
    WB --> AW
    DF --> WR

    RW --> WR
    RW --> QS
    RW --> CAAPI
    AW --> QS
    OPS --> QS
    OPS --> WR
    PR --> CAAPI
    PR --> WR
    RM --> WR
    RM --> QS

    WR --> DL
    DL --> QS

```

---

## 1b. Full System — Prediction Loop Included

```mermaid
flowchart TD
    subgraph USERS["User Types"]
        C(["👩‍⚕️ Clinical Coder"])
        CM(["👔 Coder Manager"])
        PM(["📊 Project Manager"])
        CA(["🏛️ Chief Actuary Team"])
    end

    subgraph CONFIG["Platform Configuration"]
        WB["Workspace Builder"]
        DF["Review Data Setup"]
    end

    subgraph PORTAL["Portal"]
        subgraph REVIEW["Review & Oversight"]
            RW["Review Workspace\n(incl. queue)"]
            OPS["Ops Dashboard"]
        end
        subgraph ANALYTICS["Analytics"]
            AW["Analytics Workspace"]
        end
        subgraph REFINEMENT["Model Refinement"]
            RM["Feedback Refinement\n& Ensemble"]
        end
        subgraph EXTRACTION["Extraction & Inference"]
            PR["Prompt Studio\n(Vertex AI · LLM Batch Runner)"]
            INF["Model Inference"]
        end
    end

    subgraph DSL["Services Layer"]
        WR["Write Service\nfindings · verdicts\nmodel outputs · config"]
        QS["Query Service\nreview results · analytics\nmember context · models"]
        CAAPI["CA API\n(Chart Access)"]
    end

    DL[("Data Layer")]

    CA --> WB
    CA --> DF
    CA --> PR
    CA --> RM
    CA --> AW

    WB --> RW
    WB --> AW
    DF --> WR

    C --> RW
    C -.->|"supporting context"| AW

    CM --> RW
    CM --> OPS
    CM --> AW

    PM --> OPS
    PM --> AW

    PR --> CAAPI
    PR --> WR
    CAAPI -->|"charts"| PR
    CAAPI -->|"charts"| RW
    INF --> WR

    QS -->|"member context"| PR
    QS -->|"member context"| INF
    QS -->|"coder verdicts"| RM
    QS -->|"artifact"| INF

    RM -->|"refined dataset"| WR

    RW --> WR
    RW --> QS
    RW --> CAAPI
    AW --> QS
    OPS --> QS
    OPS --> WR

    WR --> DL
    DL --> QS
```

---

## 2. Clinical Coder — Full Interaction Flow

```mermaid
flowchart TD
    START([Coder logs in]) --> Q

    subgraph QUEUE["Review Queue"]
        Q["View available charts\n/review/queue\nFiltered by PromptRun, status"]
        Q --> QA["Take next chart\nautomatically assigned"]
        Q --> QB["Select specific chart\nfrom queue"]
    end

    QA & QB --> CLAIM["Chart claimed\nChartReview created\nor resumed"]

    subgraph WORKSPACE["Review Workspace"]
        CLAIM --> PDF["View chart PDF\nStreamed via session token\nPage navigation"]
        CLAIM --> FIND["View LLM findings\nICD-10 list with\nevidence citations"]

        PDF <-->|"click finding\njumps to page"| FIND

        FIND --> DEC{"For each finding"}

        DEC --> CONFIRM["CONFIRM\n+ Confidence 1–5\n+ Optional note"]
        DEC --> DENY["DENY\n+ Confidence 1–5\n+ Correction type:\n  insufficient_evidence\n  wrong_code | duplicate\n  not_clinically_supported"]
        DEC --> ADD["ADD missed code\n+ ICD-10 entry\n+ Evidence page\n+ Drag to select\n  bounding box region\n+ Confidence 1–5"]

        CONFIRM & DENY & ADD --> TAG["Tag claim context\nprepay | postpay\nhcc_capture | unspecified"]
    end

    subgraph CONTEXT["Supporting Context Panel"]
        TAG --> CTX{"Need more context?"}
        CTX -->|yes| EX["Open supporting exhibit\npre-filtered to this member\n+ prior claims history\n+ pharmacy fills\n+ HEDIS gaps\n+ prior risk scores"]
        EX --> SNAP["Exhibit snapshot\nsaved to ChartCoding\n(supporting_context)"]
        CTX -->|no| DONE
        SNAP --> DONE
    end

    DONE["Submit verdict\nSave ChartCoding row"] --> NEXT{"More findings?"}
    NEXT -->|yes| DEC
    NEXT -->|no| FINISH

    subgraph FINISH_FLOW["Finish Review"]
        FINISH{"Finish options"}
        FINISH --> FS["Finish & Stop\nChartReview marked complete\nReturn to queue"]
        FINISH --> FN["Finish & Take Next\nChartReview complete\nNext chart auto-claimed"]
    end
```

---

## 3. Coder Manager — Full Interaction Flow

```mermaid
flowchart TD
    START([Manager logs in]) --> DASH

    subgraph OVERVIEW["Manager Dashboard"]
        DASH["Run Progress Overview\nAll active PromptRuns\nreviewed / unreviewed / in_progress"]
        DASH --> SEL["Select a Run\nto drill into"]
    end

    subgraph RUN_VIEW["Run-Level View"]
        SEL --> RP["Run Progress\nreviewed_count\nunreviewed_count\nin_progress_count\navg_confidence\nconfidence distribution"]

        RP --> FILTER["Filter charts by:\nstatus | coder | ICD-10\nclaim_context | confidence"]
    end

    subgraph CODER_VIEW["Coder Performance"]
        FILTER --> CS["Coder Summary\nPer coder this run:\n- charts completed\n- avg confidence\n- confirm / deny / add rate\n- time per chart"]

        CS --> OUTLIER{"Flag outliers"}
        OUTLIER -->|"always 5/5 confidence"| ALERT1["Review that coder's\nrecent decisions"]
        OUTLIER -->|"high deny rate"| ALERT2["Check correction types\nfor pattern"]
        OUTLIER -->|"low throughput"| ALERT3["Check queue assignment"]
    end

    subgraph AGREEMENT["Inter-Rater Agreement"]
        FILTER --> IRA["Agreement Report\nWhere 2+ coders\nreviewed same chart:\n- agree rate by ICD-10\n- disagree cases listed\n- confidence correlation"]

        IRA --> DISC["Disagreement cases\n→ identify codes needing\nbetter prompt guidance"]
    end

    subgraph ASSIGN["Queue Assignment"]
        FILTER --> ASSIGN_ACT["Assign charts\nto specific coders\nor coder teams"]
        ASSIGN_ACT --> AVIEW["View assignment status\nwho has what\nwhat is unassigned"]
    end

    subgraph HCC_VIEW["HCC Capture Tracking"]
        FILTER --> HCC["HCC Capture Rate\nfor this run:\n- charts with ADDED codes\n- new HCCs not on claims\n- estimated RAF uplift"]
    end

    subgraph EXHIBITS["Analytics Context"]
        CS & IRA & HCC --> AW["Open Analytics Workspace\nexhibit for deeper drill\ne.g. coder agreement\nby code category over time"]
    end
```

---

## 4. Project Manager / Ops — Full Interaction Flow

```mermaid
flowchart TD
    START([PM / Ops logs in]) --> DASH

    subgraph PIPELINE["Pipeline Health Dashboard"]
        DASH["Pipeline Health\nWorker last seen\nQueue depth\nStuck chart count\nError rate last 24h"]
        DASH --> ALERT{"Issues?"}
        ALERT -->|"stuck charts"| REAP["Trigger reap\nOrphaned in_progress\nback to queue"]
        ALERT -->|"high error rate"| ERR["View error log\nby chart / model\nreview failure messages"]
        ALERT -->|"healthy"| CONT["Continue to analytics"]
    end

    subgraph CROSS_RUN["Cross-Run Comparison"]
        CONT --> CRC["Compare two PromptRuns\nside by side:\n- total charts\n- extraction count\n- review completion %\n- avg confidence\n- top ICD-10 codes\n- cost per chart\n- error rate"]
        CRC --> DEC{"Decision"}
        DEC -->|"Run A better"| PROMOTE["Flag Run A prompt\nfor promotion"]
        DEC -->|"neither ready"| ITER["Back to Chief Actuary\nfor prompt iteration"]
    end

    subgraph WORKFLOW_TRACK["Pre-Pay / Post-Pay Tracking"]
        CONT --> WF["Workflow breakdown\nby claim_context tag:\n- prepay: chart count,\n  review completion,\n  auto-approve candidates\n- postpay: audit completion,\n  overpayment flags\n- hcc_capture: new HCCs,\n  estimated RAF uplift"]
    end

    subgraph COST["Cost & Volume Tracking"]
        CONT --> COST_V["Cost Summary\nby run | by model\nby date range:\n- total token spend\n- cost per chart\n- cost per confirmed code\n- volume trend"]
    end

    subgraph HCC_OPS["HCC Capture Operations"]
        CONT --> HCC_R["HCC Capture Rate\nby run:\n- ADDED codes mapping to HCCs\n- new vs already on claims\n- aggregate RAF weight\n  of capture opportunities"]
    end

    subgraph EXHIBITS["Analytics Workspace"]
        CRC & WF & COST_V & HCC_R --> AW["All metrics also available\nas configurable exhibits:\n- line chart: cost over time\n- pivot: ICD-10 by run\n- metric cards: KPIs\n- table: detail drill-down"]
    end
```

---

## 5. Chief Actuary Team — Full Interaction Flow

```mermaid
flowchart TD
    START([Chief Actuary logs in]) --> CHOICE

    subgraph WORKSPACE_BUILDER["Workspace Builder"]
        CHOICE{"Task"}

        CHOICE -->|"new domain page"| WB_NEW["Create workspace page\n- Name + description\n- Select mart domain\n  e.g. Finance, Stars, PI\n- Set page-level filters\n  plan_year | hcg_group\n  claim_type | county"]

        WB_NEW --> WB_GRID["Define exhibit grid\nDrag to arrange slots\nResize exhibit panels\nSet column layout"]

        WB_GRID --> WB_ADD["Add exhibits to grid\nPick exhibit type:\n  chart.line | chart.bar\n  table.pivot | cards.metric\n  chart.heatmap | table.data"]

        WB_ADD --> WB_CFG["Configure each exhibit\nYAML editor with live preview:\n  x: field reference\n  y: measure + aggregation\n  group_by: dimension\n  formatting: title, height\n  filters: exhibit-level"]

        WB_CFG --> WB_FILT["Configure filter sidebar\nFor each page filter:\n  - field source\n  - control type:\n    select | date_range | range\n  - context_filters: yes/no\n  - default value"]

        WB_FILT --> WB_CTRL["Configure exhibit controls\nInteractive controls per exhibit:\n  - dimension switcher\n  - measure selector\n  - sort order toggle\n  - color palette"]

        WB_CTRL --> WB_PUB{"Publish?"}
        WB_PUB -->|"save draft"| WB_DRAFT["Save as draft\nonly visible to\nChief Actuary team"]
        WB_PUB -->|"publish"| WB_LIVE["Publish workspace\nVersioned — prior\nstate recoverable\nVisible to all roles\nwith access"]
    end

    subgraph DATA_FORM["Data Form Designer"]
        CHOICE -->|"new data source\nor exhibit type"| DF_NEW["Register new exhibit\ndata form\nMaps exhibit config fields\nto Snowflake MART columns"]

        DF_NEW --> DF_DOMAIN["Select target domain\nand mart table(s)\ne.g. MART.FINANCE_CLAIM_LINES"]

        DF_DOMAIN --> DF_FIELDS["Define field registry\nFor each queryable field:\n  - alias (e.g. finance.paid_amount)\n  - physical column\n  - allowed aggregations\n  - display format: $ | % | ,\n  - join keys to other tables"]

        DF_FIELDS --> DF_JOINS["Declare join paths\nBetween registered tables:\n  - join key pairs\n  - join type: left | inner\n  - cardinality: 1:many | 1:1\nQuery engine uses these\nto auto-resolve multi-table\nexhibit queries"]

        DF_JOINS --> DF_FILTERS["Define filterable dimensions\nFor each filter-eligible field:\n  - picker type: select | range | date\n  - max distinct values\n  - sort: alpha | measure-ranked\n  - context_filter eligible: yes/no"]

        DF_FILTERS --> DF_TEST["Test form config\nRun a sample exhibit\nquery against Snowflake\nverify field resolution\ncheck join output"]

        DF_TEST --> DF_PUB["Register form\nAvailable in\nWorkspace Builder\nfield picker"]
    end

    subgraph PROMPT_STUDIO["Prompt Studio"]
        CHOICE -->|"new extraction prompt"| PS_NEW["Create prompt\nname + version 1\nprompt_text\nSnowflake context queries:\n  e.g. member RAF history\n  prior claim diagnoses\n  pharmacy fills"]

        CHOICE -->|"iterate existing"| PS_VER["Create new version\nsame name, version + 1\ndiff view vs prior shown"]

        CHOICE -->|"test prompt"| PS_TEST["Single-chart test run\nselect chart_id\nselect model + provider\nview raw findings + chunks\ntoken cost breakdown"]

        PS_TEST --> PS_REFINE{"Good enough?"}
        PS_REFINE -->|no| PS_VER
        PS_REFINE -->|yes| PS_BATCH

        PS_NEW & PS_VER --> PS_BATCH["Launch batch run\n- prompt version\n- model provider + name\n- chart selection:\n  standard corpus OR\n  custom SQL query"]
    end

    subgraph TRAINING_LOOP["Training Loop & Model Governance"]
        PS_BATCH --> TL_MON["Monitor extraction run\npending / error / complete\ncost accumulating\ntop codes emerging"]

        TL_MON --> TL_RESULTS["View coder review results\nonce review phase complete:\n- precision by ICD-10\n- recall by ICD-10\n- confidence distribution\n- agreement rate\n- correction type breakdown"]

        TL_RESULTS --> TL_COMPARE["Compare to prior\nmodel version:\n- delta precision / recall\n- delta cost per chart\n- delta coder agreement"]

        TL_COMPARE --> TL_EXPORT["Export training dataset\nmin confidence filter\ndecision type filter\nclaim context filter\nOutputs labeled JSONL"]

        TL_EXPORT --> TL_TRAIN["Train lightweight model\nexternal: Vertex AI\nor custom pipeline"]

        TL_TRAIN --> TL_REG["Register model version\nname | type | corpus size\nP / R / F1 metrics\nGCS artifact path\nstatus: staging"]

        TL_REG --> TL_VALID["Validate staging model\nheld-out chart set\nexhibit comparison vs\nLLM baseline in AW"]

        TL_VALID --> TL_PROMOTE{"Promote to production?"}
        TL_PROMOTE -->|yes| TL_PROD["Promote\nPrior version retired\nWorker reads new version\nNo code deploy"]
        TL_PROMOTE -->|no| TL_ITER["Iterate\nmore data | adjust arch\nback to Prompt Studio"]

        TL_PROD --> TL_LIGHT["Lightweight model\nruns production charts\nLLM reserved for:\n- edge cases\n- new data sources\n- periodic re-eval"]
    end

    subgraph AW_READ["Analytics Workspace — Read"]
        CHOICE -->|"review actuary\nexhibits"| AW["View published workspaces\nFinance | Stars | PI\nHEDIS | Member panel\nInteractive filters\nExport data"]
    end
```

---

## 6. Data Flow Summary — All Users

```mermaid
flowchart LR
    subgraph INPUTS["Inputs"]
        CHART["Medical Chart PDF\n(CA API)"]
        SNOW["Snowflake MART\nMember / Claims / RAF\nHEDIS / Stars / PI"]
    end

    subgraph CONFIG["Platform Configuration\n(Chief Actuary Team)"]
        WB["Workspace Builder\npage layout\nexhibit grid\nfilter sidebar\nexhibit controls"]
        DF["Data Form Designer\nfield registry\njoin paths\nfilter dimensions"]
        PS["Prompt Studio\nprompt versions\ncontext queries\nbatch runs"]
    end

    subgraph EXTRACTION["LLM Extraction"]
        LLM["LLM Batch Run\nICD-10 findings\nper chunk"]
        CHUNK["ChartChunk\ntoken cost\nevidence page"]
        LLM --> CHUNK
    end

    subgraph REVIEW["Human Review\n(Coder)"]
        QUEUE["Review Queue"]
        VERDICT["ChartCoding\ndecision + confidence\ncorrection_type\nclaim_context\nhcc_code + RAF weight"]
        QUEUE --> VERDICT
    end

    subgraph OVERSIGHT["Oversight\n(Manager / PM)"]
        MGMT["Coder metrics\nAgreement rates\nHCC capture\nCost tracking\nPipeline health"]
    end

    subgraph RETRAINING["Retraining Loop\n(Chief Actuary Team)"]
        EXPORT["Labeled dataset\nexport"]
        REGISTRY["ModelVersion\nregistry"]
        DEPLOY["Lightweight model\nproduction deploy"]
        EXPORT --> REGISTRY --> DEPLOY
    end

    subgraph DOWNSTREAM["Downstream Impact"]
        RAF["Risk Adjustment\nRAF scores"]
        PREPAY["Pre-Pay\nauto-approve / hold"]
        POSTPAY["Post-Pay\noverpayment audit"]
        STARS["STARS / HEDIS\ngap closure"]
        CAPITAL["Capital Deployment\nReserves / Pricing / Bids"]
    end

    WB -->|"shapes what analysts see"| SNOW
    DF -->|"registers queryable fields\nand join paths"| SNOW
    PS -->|"defines extraction logic\nand Snowflake context"| LLM

    CHART --> LLM
    SNOW --> LLM
    SNOW -->|"supporting exhibits\nfor coders"| QUEUE

    CHUNK --> QUEUE
    VERDICT --> MGMT
    VERDICT --> EXPORT
    VERDICT --> RAF
    VERDICT --> PREPAY
    VERDICT --> POSTPAY
    VERDICT --> STARS

    RAF & PREPAY & POSTPAY & STARS --> CAPITAL

    DEPLOY -->|"replaces LLM\nfor most charts"| LLM
```
