# Diagram sources

Technical models for the decks. Mermaid and PlantUML are the source of truth.
Imagen Diagrams is the presentation layer when a backend is available.

```
slides/diagrams/
  mermaid/     .mmd source
  plantuml/    .puml source plus SVG
  imagen/      theme YAML and prompt sidecars
```

Session 1 coverage:

| File | Concept |
|---|---|
| `mermaid/agent-runtime-loop.mmd` | Five-part loop |
| `mermaid/orchestrator-doer-judge.mmd` | Same graph, three roles |
| `mermaid/three-exits.mmd` | pass / retry / escalate |
| `mermaid/react-cycle.mmd` | Perceive, reason, act, observe, decide |
| `mermaid/two-repos.mmd` | Engine never imports target |
| `mermaid/write-scope.mmd` | Scope as a type |
| `mermaid/enhancer-sequence.mmd` | Ticket enhancer runtime |
| `mermaid/stable-failure.mmd` | Same signature twice |
| `mermaid/maker-checker.mmd` | Maker and checker split |
| `mermaid/context-rule.mmd` | File in, summary back |
| `mermaid/lab1-plugin.mmd` | Skill plus two agents |
| `mermaid/four-objects.mmd` | Same graph, four objects |
| `mermaid/human-oversight.mmd` | Human owns merge |
| `mermaid/state-locations.mmd` | Disk vs process vs chat |
| `mermaid/failure-modes.mmd` | Four collapses |
| `mermaid/four-artifacts.mmd` | Four things they leave with |
| `mermaid/four-properties.mmd` | Explicit state, scope, evidence, transition |
| `mermaid/flow-vs-prompt.mmd` | AlphaCodium 19 to 44 |
| `mermaid/trigger-types.mmd` | File, webhook, schedule, anti-pattern |
| `mermaid/ticket-kinds.mmd` | Bug, feature, ui contracts |
| `mermaid/module2-preview.mmd` | Why Module 2 does not get cut |
| `plantuml/agent-runtime-loop.puml` | Component view of the loop |
| `plantuml/lab1-plugin.puml` | Plugin shape |
| `plantuml/two-repo-deployment.puml` | Two-repo contract |
| `plantuml/trust-boundaries.puml` | Untrusted model output vs trusted process |
| `plantuml/enhancer-sequence.puml` | Sequence with three exits |
| `plantuml/roles-scope.puml` | Judge has no write method |

`python scripts/build_slides.py` renders mermaid blocks inside each
`slides.md` to SVG via mermaid-cli.

PlantUML SVGs next to the `.puml` files were rendered with:

```bash
java -jar plantuml.jar -tsvg -Playout=smetana slides/diagrams/plantuml/*.puml
```

Imagen Diagrams (`SpillwaveSolutions/imagen-diagrams`) was used as the
prompt contract and Spillwave theme. The `imagen` / `grok` / `codex` CLIs
were not on PATH in this environment, so raster enhancement used the
image generation backend directly. Semantic diagrams in the room should
prefer the mermaid-cli SVGs, not the raster drafts, when labels disagree.
