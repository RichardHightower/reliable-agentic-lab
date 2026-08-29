---
name: e2e-test-research-report
description: "Generate and validate a standalone sol3 research white paper end to end, export its Markdown and publication figures as an Arctic Fox PDF, and publish the accepted report to a secret GitHub Gist by default. Use when asked to test, smoke-test, or demonstrate research-report generation in `solutions/sol3_research_*`."
---

# E2E test a research report

Run the selected solution as a standalone artifact. Do not extract a shared
research or publishing framework. Default to
`solutions/sol3_research_agent_sdk`; use another `sol3_research_*` folder only
when the user names it and that folder provides the required tasks.

The default workflow uses live research and attempts publication. A secret
Gist is unlisted, not access controlled. Its URL is a credential. If the user
requests local-only output, set `PUBLISH=false` before any Gist call.

## Prepare and prove the folder

1. Read the solution's `Taskfile.yml`, `HOW_TO_RUN.md`, and `SPEC.md`.
2. Run `task setup`, then `task test` and `task checks`.
3. Confirm `imagen`, `grok`, or `codex` is on `PATH`. The renderer must follow
   `imagen`, then `grok`, then `codex` order. A configured `GEMINI_API_KEY` is
   mapped to the `GOOGLE_API_KEY` name required by the Imagen CLI. Preserve
   every failed attempt's prompt and metadata, then fail closed at exit 2 if
   all approved backends fail.
4. Confirm the installed `imagen-diagrams` plugin contains
   `skills/imagen-diagrams/themes/arctic-fox.yaml`.
5. For the default live lane, require both `ANTHROPIC_API_KEY` and
   `PERPLEXITY_API_KEY` through the solution's documented environment lookup.
   Use the fixture lane when the user asks for it or credentials are absent,
   and report clearly that it did not test live research.

## Generate the report

From `solutions/sol3_research_agent_sdk`:

```bash
task setup
task test
task checks
LIVE_E2E_MAX_USD=10 task e2e-live
```

For recorded research with real figure rendering:

```bash
task e2e-fixture
```

Do not rerun a failed live lane before reading
`work/e2e-loop-engineering-live/e2e-report.json`. Preserve the cost cap and
classify the failure as credentials, provider, renderer, generated document,
or publication gate.

## Require one visual system

Every accepted figure must have an imagen-diagrams sidecar that records:

- `theme: arctic-fox`
- `density: article`
- a supported backend and its matching brace policy

It must also have a passing judge sidecar, publication resolution, retained
Mermaid or PlantUML source, an embedded Markdown image, and a caption explained
by the paper. Raw diagram syntax is never the publication figure.

Export the same run as PDF:

```bash
REPORT_DIR=work/e2e-loop-engineering-live task pdf
```

This writes `paper.pdf` and `paper.pdf.json` beside `paper.md`. Require the PDF
sidecar to record `theme: arctic-fox`, reopen the PDF, render every page to PNG,
and visually inspect the pages for clipped text, missing figures, poor contrast,
or broken tables. Do not accept text extraction alone as visual proof.

## Publish by default

Unless the user requested `PUBLISH=false`, attempt publication only after the
E2E report passes and the PDF visual check passes:

```bash
gh auth status
REPORT_DIR=work/e2e-loop-engineering-live task publish-report
```

The GitHub token needs the `gist` scope. The publisher must never pass
`--public`; it creates or updates a secret Gist and uploads `paper.md`,
`paper.pdf`, and the flattened figure files. If authentication or scope is
missing, keep all local artifacts, report `renderer: ready` and
`publisher: missing`, and stop without inventing a Gist URL.

## Verify and report

Inspect these durable artifacts:

- `e2e-report.json`: `passed: true`, bounded spend, required claims and sources
- `diagrams/*_imagen.json`: Arctic Fox, article density, correct backend policy
- `diagrams/*_imagen.judge.json`: fidelity pass with no misses
- `paper.pdf.json`: Arctic Fox theme, page count, figure inventory, byte count
- `gist.json`: secret Gist URL, topic, and uploaded files when publishing ran

Report the lane, provider, spend, source count, figure count, PDF pages, PDF
path, Gist URL or fail-closed publisher status, and the exact failed gate. Do
not describe a fixture lane as live and do not describe an unrendered prompt
sidecar as an image.
