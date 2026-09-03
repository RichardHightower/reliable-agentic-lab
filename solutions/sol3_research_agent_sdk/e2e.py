#!/usr/bin/env python3
"""Acceptance test for an illustrated loop-engineering white paper.

The fixture lane keeps the research corpus stable while exercising every phase
of the real harness, including the image renderer. The live lane substitutes
the Agent SDK and MCP tools, but evaluates the same durable artifact contract;
it deliberately does not compare prose to a snapshot.

Both lanes write ``e2e-report.json`` beside the paper. The report is a compact
CI artifact: it says whether a failure came from the generated document or
from an unavailable renderer, credential, or live research provider.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import struct
import subprocess
import sys
from pathlib import Path

import diagrams
import roles

FOLDER = Path(__file__).resolve().parent
SCENARIO = FOLDER / "e2e" / "loop-engineering-best-practices.md"
FIXTURE = FOLDER / "fixtures" / "loop-engineering-e2e.json"
TOPIC = "loop engineering best practices"
REQUIRED_FIGURES = ("control-loop", "trust-boundary")
MIN_SOURCES = 3
MIN_PNG_WIDTH = 1024
MIN_PNG_HEIGHT = 576
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
BACKEND_POLICY = {
    "imagen": "imagen-cli-vars",
    "grok": "grok-imagine",
    "codex": "grok-imagine",
}
PUBLICATION_THEME = "arctic-fox"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _png_dimensions(path: Path) -> tuple[int, int]:
    """Read a PNG's dimensions without adding Pillow to the standalone port."""
    header = path.read_bytes()[:24]
    if header[:8] != PNG_SIGNATURE or header[12:16] != b"IHDR":
        raise ValueError("not a PNG with an IHDR header")
    return struct.unpack(">II", header[16:24])


def validate(work_dir: Path, *, max_usd: float | None = None) -> dict:
    """Validate the publication contract and return an artifact-safe report."""
    work_dir = Path(work_dir)
    failures: list[str] = []
    report: dict = {"work_dir": str(work_dir), "failures": failures}

    def need(path: Path) -> bool:
        if path.is_file():
            return True
        failures.append(f"missing required artifact: {path.relative_to(work_dir)}")
        return False

    paper_path = work_dir / "paper.md"
    outline_path = work_dir / "outline.approved.json"
    plan_path = work_dir / "plan.json"
    sources_path = work_dir / "sources.json"
    claims_path = work_dir / "claims.json"
    diagrams_path = work_dir / "diagrams.json"
    check_path = work_dir / "check.json"
    review_path = work_dir / "review.json"
    state_path = work_dir / ".harness" / "state.json"
    for path in (
        paper_path,
        outline_path,
        sources_path,
        claims_path,
        diagrams_path,
        check_path,
        review_path,
        state_path,
    ):
        need(path)
    if failures:
        report["passed"] = False
        return report

    paper = paper_path.read_text(encoding="utf-8")
    stamp = _read_json(outline_path)
    import outline as outlines  # noqa: PLC0415

    plan = outlines.plan_view(outlines.load_approved(stamp))
    if plan_path.is_file():
        # Older artifacts kept a derived plan.json. The approved outline wins.
        pass
    sources = _read_json(sources_path)
    claims = _read_json(claims_path).get("claims", [])
    figures = _read_json(diagrams_path).get("figures", [])
    score = _read_json(check_path)
    review = _read_json(review_path)
    state = _read_json(state_path)

    report["sections"] = len(plan.get("sections", []))
    report["questions"] = len(plan.get("questions", []))
    report["figures"] = len(figures)
    report["claims"] = len(claims)
    report["usd"] = state.get("total_usd", 0.0)

    if not score.get("passed"):
        failures.append("the deterministic paper checks did not pass")
    if not review.get("done"):
        failures.append("the paper judge did not accept the paper")
    if "## Abstract" not in paper or "## References" not in paper:
        failures.append("paper.md is missing an abstract or references")
    if len(plan.get("sections", [])) < 3 or len(plan.get("questions", [])) < 3:
        failures.append("the paper plan is too small for the acceptance scenario")
    if len(claims) < 3:
        failures.append("the research phase produced fewer than three claims")
    if any(claim.get("status") == "contradicted" for claim in claims):
        failures.append("a contradicted claim reached the publication candidate")

    source_urls = sorted(
        {
            source.get("url", "")
            for source in sources.get("sources", [])
            if source.get("url")
        }
    )
    report["source_urls"] = source_urls
    if len(source_urls) < MIN_SOURCES:
        failures.append(f"fewer than {MIN_SOURCES} distinct sources were retrieved")
    domains = {url.split("/", 3)[2] for url in source_urls if url.startswith("http")}
    if len(domains) < MIN_SOURCES:
        failures.append(f"fewer than {MIN_SOURCES} source domains were retrieved")

    by_name = {figure.get("name"): figure for figure in figures}
    for name in REQUIRED_FIGURES:
        figure = by_name.get(name)
        if figure is None:
            failures.append(f"required figure {name!r} was not planned and rendered")
            continue
        if not figure.get("path"):
            failures.append(f"required figure {name!r} has no rendered PNG")
            continue
        if figure.get("misses"):
            failures.append(f"required figure {name!r} has fidelity misses: {figure['misses']}")
        caption = figure.get("caption", "").strip()
        if not caption or caption not in paper:
            failures.append(f"required figure {name!r} has no published caption")
        image = work_dir / figure["path"]
        if not image.is_file():
            failures.append(f"required figure {name!r} points at a missing image")
            continue
        try:
            width, height = _png_dimensions(image)
        except ValueError as exc:
            failures.append(f"required figure {name!r} is invalid: {exc}")
            continue
        if width < MIN_PNG_WIDTH or height < MIN_PNG_HEIGHT or image.stat().st_size < 4096:
            failures.append(
                f"required figure {name!r} is below publication resolution "
                f"({width}x{height}, {image.stat().st_size} bytes)"
            )
        if f"]({figure['path']})" not in paper:
            failures.append(f"required figure {name!r} is not embedded in paper.md")
        source_dir = work_dir / "diagrams"
        if not any((source_dir / f"{name}{suffix}").is_file() for suffix in (".mmd", ".puml")):
            failures.append(f"required figure {name!r} is missing its source diagram")

        # imagen-diagrams persists both its rendering decision and the
        # inventory judge. These are the proof that the PNG is an article
        # figure produced from source, rather than an arbitrary raster file.
        render_sidecar = image.with_suffix(".json")
        judge_sidecar = image.with_suffix(".judge.json")
        if not render_sidecar.is_file():
            failures.append(f"required figure {name!r} is missing the imagen-diagrams sidecar")
        else:
            rendered = _read_json(render_sidecar)
            backend = rendered.get("backend")
            if backend not in BACKEND_POLICY:
                failures.append(f"required figure {name!r} records an unsupported image backend")
            elif rendered.get("policy") != BACKEND_POLICY[backend]:
                failures.append(f"required figure {name!r} records the wrong brace policy")
            if rendered.get("density") != "article":
                failures.append(f"required figure {name!r} was not rendered at article density")
            if rendered.get("theme") != PUBLICATION_THEME:
                failures.append(
                    f"required figure {name!r} used {rendered.get('theme')!r}, "
                    f"not the {PUBLICATION_THEME!r} publication theme"
                )
        if not judge_sidecar.is_file():
            failures.append(f"required figure {name!r} is missing the imagen-diagrams judge sidecar")
        elif not _read_json(judge_sidecar).get("pass"):
            failures.append(f"required figure {name!r} did not pass the imagen-diagrams judge")

    knowledge = state.get("phases", {}).get("knowledge", {})
    if knowledge.get("valid") is not True:
        failures.append("the research knowledge bundle did not validate")
    if max_usd is not None and float(state.get("total_usd", 0.0)) > max_usd:
        failures.append(f"run exceeded its ${max_usd:.2f} E2E cost cap")

    report["passed"] = not failures
    return report


def _write_report(work_dir: Path, report: dict) -> None:
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "e2e-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def _preflight(mode: str) -> list[str]:
    missing = []
    if not diagrams.available():
        missing.append("the diagram renderer is absent; run `task setup`")
    if not any(shutil.which(binary) for binary in ("imagen", "grok", "codex")):
        missing.append("no approved image backend is on PATH (imagen, grok, or codex)")
    if mode == "live":
        if not os.environ.get("ANTHROPIC_API_KEY"):
            missing.append("ANTHROPIC_API_KEY is not set")
        if not roles.environment_value("PERPLEXITY_API_KEY"):
            missing.append("PERPLEXITY_API_KEY is not set")
    return missing


def run(mode: str, out: Path, python: str, max_usd: float) -> int:
    """Run one acceptance lane, then leave a report even when it fails."""
    out = Path(out)
    missing = _preflight(mode)
    if missing:
        report = {"work_dir": str(out), "passed": False, "failures": missing, "mode": mode}
        _write_report(out, report)
        print("E2E preflight failed:")
        print("\n".join(f"- {item}" for item in missing))
        return 2

    command = [
        python,
        str(FOLDER / "loop.py"),
        "--topic",
        TOPIC,
        "--out",
        str(out),
        "--fresh",
        "--max-questions",
        "3",
        "--max-claims",
        "6",
        "--max-diagrams",
        "2",
        "--max-iterations",
        "2",
        "--max-usd",
        str(max_usd),
        "--enforce-loop-doctrine",
    ]
    if mode == "fixture":
        command += ["--backend", "fixture", "--fixture", str(FIXTURE)]
    else:
        command += ["--backend", "agent", "--brief-file", str(SCENARIO)]

    proc = subprocess.run(command, cwd=FOLDER, text=True, capture_output=True, check=False)
    report = validate(out, max_usd=max_usd) if proc.returncode == 0 else {
        "work_dir": str(out),
        "passed": False,
        "failures": [f"loop.py exited {proc.returncode}"],
    }
    report.update(
        {
            "mode": mode,
            "command": command,
            "returncode": proc.returncode,
            "stdout_tail": proc.stdout[-4000:],
            "stderr_tail": proc.stderr[-4000:],
        }
    )
    _write_report(out, report)
    if report["passed"]:
        print(f"E2E {mode} passed: {out / 'paper.md'}")
        return 0
    print(f"E2E {mode} failed; see {out / 'e2e-report.json'}", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("fixture", "live"), required=True)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--python", default=sys.executable, help="Python interpreter that owns the runtime")
    parser.add_argument("--max-usd", type=float, default=10.0, help="hard cap for this acceptance run")
    args = parser.parse_args(argv)
    out = args.out or FOLDER / "work" / f"e2e-loop-engineering-{args.mode}"
    return run(args.mode, out, args.python, args.max_usd)


if __name__ == "__main__":
    raise SystemExit(main())
