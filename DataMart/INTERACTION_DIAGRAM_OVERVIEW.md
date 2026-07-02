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
