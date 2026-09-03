---
title: "Lab 3 Deep Agents Research Pipeline: Software Design Document"
document_type: "arc42 Software Design Document"
status: "Current implementation"
---

# Lab 3 Deep Agents Research Pipeline

## Software Design Document

## Contents

1. Introduction and goals
2. Constraints and strategy
3. Building blocks
4. Runtime and evidence model
5. Deployment, quality, and risks
6. Glossary

## 1. Introduction and goals

This Deep Agents solution produces a cited research brief or an evidence-backed white paper. The paper mode runs nine stages: planning, search, verification, outline, diagram, writing, review, assembly, and optional publication. It treats grounding, cost, and stopping as program-owned policy rather than agent judgment.

### Functional requirements

- Plan three to twelve research questions and limited figures.
- Search approved sources, record claims, and cross-check prioritized claims.
- Build Mermaid or PlantUML source diagrams and accept only judged publication figures.
- Write scoped paper sections, review them, assemble the final artifact, and gate publication.
- Preserve a resumable checkpoint and stop in the documented order: done, cost, then max turns.

### Quality requirements

- Writer, verifier, and diagrammer have distinct write paths; reviewer and researcher have none.
- Tool lists, custom path checks, virtual filesystem mounts, and disabled general-purpose subagents form four fences.
- No Bing fallback is used for normal auto research.
- `task test`, `task table`, and `task checks` are offline.

## 2. Constraints and strategy

Deep Agents provides delegated subgraphs, not policy. `roleplan.py` owns the seven-role scope map; `paper.py` owns nine-stage orchestration; `stages.py`, `gates.py`, and `paper_check.py` supply deterministic transition rules. The research boundary filters URLs through an official-host policy before a claim can reach the paper.

```mermaid
flowchart LR
    CLI["loop.py or Task"] --> Pipeline["Paper pipeline"]
    Pipeline --> Graph["Deep Agents parent graph"]
    Graph --> Planner["Planner"]
    Graph --> Researcher["Filtered researcher"]
    Graph --> Verifier["Evidence verifier"]
    Graph --> Diagrammer["Diagrammer"]
    Graph --> Writer["Paper writer"]
    Graph --> Reviewer["Read-only reviewer"]
    Pipeline --> Stages["Stage gates and checkpoint"]
    Researcher --> Providers["Perplexity, Anthropic, OpenAI, fixture"]
    Verifier --> Providers
    Writer --> Work["work slash paper slash slug"]
    Diagrammer --> Figure["Judged image backend"]
    Stages --> Publish["Opt-in secret gist"]
    classDef boundary fill:#E8F0FE,stroke:#174EA6,color:#202124
    classDef agent fill:#E6F4EA,stroke:#137333,color:#202124
    classDef control fill:#FEF7E0,stroke:#B06000,color:#202124
    class CLI,Providers,Work,Figure,Publish boundary
    class Graph,Planner,Researcher,Verifier,Diagrammer,Writer,Reviewer agent
    class Pipeline,Stages control
```

Each role's context and tool set are intentionally narrow, preserving independence between research, verification, and prose generation. Source: [`docs/diagrams/architecture.mmd`](docs/diagrams/architecture.mmd).

## 3. Building blocks

```text
sol3_research_deep_agents/
├── loop.py                   Brief and paper entry points
├── paper.py                  Nine-stage pipeline and resumable run
├── stages.py                 Stage-level validation
├── gates.py                  Done, retry, cost, and turn decisions
├── roles.py                  Deep Agents construction and fences
├── roleplan.py               Seven-role scopes
├── research.py               Filtered provider boundary and cost control
├── evidence.py               Source, claim, and corroboration model
├── diagrams.py               Mermaid and PlantUML publication figures
├── paper_check.py            Final hard checks
├── publish.py                Opt-in secret Gist publication
└── tests/                    Offline pipeline and isolation tests
```

| Module | Responsibility |
| --- | --- |
| `paper.py` | Coordinates phase outputs, retry boundaries, and checkpoint recovery. |
| `roles.py` | Builds role-specific graphs and removes filesystem escape paths. |
| `research.py` | Selects a filtered provider chain and enforces spending limits. |
| `evidence.py` | Models sources, claims, findings, and corroboration. |
| `diagrams.py` | Enforces source inventory and image-fidelity acceptance. |
| `paper_check.py` | Validates references, citations, body, images, style, and exit wording. |

## 4. Runtime and evidence model

```mermaid
flowchart TD
    Start([Topic]) --> Plan["Plan three to twelve questions"]
    Plan --> Search["Filtered search"]
    Search --> Verify["Cross-check selected claims"]
    Verify --> Outline["Build supported outline"]
    Outline --> Diagram["Create source diagrams"]
    Diagram --> Image["Render and judge figures"]
    Image --> Write["Write cited sections"]
    Write --> Review["Review rubric"]
    Review --> Assemble["Assemble and hard-check paper"]
    Assemble --> Exit{"Done, cost, or max turns?"}
    Exit -- Done --> Publish{"Opt-in publication?"}
    Publish -- Yes --> Gist["Push secret gist"]
    Publish -- No --> Complete([Keep report bundle])
    Gist --> Complete
    Exit -- Retryable --> Search
    Exit -- Cost or max turns --> Escalate([Keep checkpoint and evidence])
```

The cost test happens before every model call and has headroom based on observed role cost. Source: [`docs/diagrams/workflow.mmd`](docs/diagrams/workflow.mmd).

```mermaid
sequenceDiagram
    participant L as loop.py
    participant G as Deep Agents graph
    participant S as Search providers
    participant P as Paper pipeline
    participant Q as Gates
    L->>P: run paper(topic, budget)
    P->>G: plan bounded questions
    P->>G: research each question
    G->>S: filtered search or retrieval
    S-->>G: evidence candidates
    P->>G: verify and create figures
    G-->>P: findings and judged figures
    P->>G: write and review sections
    G-->>P: scoped files and verdict
    P->>Q: hard-check paper and state
    Q-->>L: done, retry, cost, or max turns
```

The parent pipeline is the only component that converts stage information into a terminal state. Source: [`docs/diagrams/sequence.mmd`](docs/diagrams/sequence.mmd).

```mermaid
classDiagram
    class SourceDocument {
        +url: str
        +quote: str
        +host: str
    }
    class Claim {
        +text: str
        +source_ids: str[]
        +truth_state: str
        +cross_checked: bool
    }
    class Finding {
        +claim_id: str
        +state: str
    }
    class Checkpoint {
        +completed_stages: str[]
        +cost_usd: float
    }
    class PaperRun {
        +run(): int
        +publish: bool
    }
    SourceDocument --> Claim
    Claim --> Finding
    PaperRun --> Checkpoint
    PaperRun --> Finding
```

`truth_state` counts source agreement, while `cross_checked` records whether a verifier made a separate retrieval. This distinction is important when budget limits truncate verification. Source: [`docs/diagrams/model.mmd`](docs/diagrams/model.mmd).

![Deep Agents research use cases](docs/diagrams/use-cases.svg)

PlantUML source: [`docs/diagrams/use-cases.puml`](docs/diagrams/use-cases.puml).

## 5. Deployment, quality, and risks

`task paper` runs fixture research, while `task live` enables the filtered provider chain after local setup. Figure creation depends on the pinned local rendering plugins and an image backend. Publication is explicit and never invoked by a failed paper path.

| Quality scenario | Expected behavior |
| --- | --- |
| Research returns an unapproved host | The Python filter drops it before paper generation. |
| Diagram source loses labels in the image | The pipeline requests a bounded redraw or records the fidelity miss. |
| Cost cap is reached | The next model call is refused and the checkpoint is preserved. |
| Reviewer fails a rubric row | The hard-check path cannot publish the paper. |

Risks include provider availability, image-backend availability, non-public Gist links, and research cost. The solution addresses them with fail-closed renderer behavior, staged checkpoints, source filtering, and cost checks inside phases.

## 6. Glossary

| Term | Meaning |
| --- | --- |
| Cross-checked | A verifier independently retrieved evidence for a claim. |
| Fixture backend | Recorded offline research source used for deterministic runs. |
| Checkpoint | State that allows completed pipeline stages to be skipped on resume. |
| Figure fidelity | Whether the rendered image retains the meaning and labels of its source. |
| Stage gate | Deterministic condition that permits moving to the next paper stage. |
