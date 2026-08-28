#!/usr/bin/env python3
"""The Research Assistant. Module 3, over the MCP tool boundary.

A question in, a cited brief out. The same graph as the other three loops on a
different object, which is the point: swap the object, keep the graph.

    plan       break the question into sub-questions
    research   ask the boundary, inside a budget
    write      assemble a brief that cites what was retrieved
    check      grounding and style, deterministically
    gate       pass, retry, or escalate

The tool boundary is the lesson. This loop can search and it can write a file
in its own output folder. It cannot merge, deploy, or touch the repo. A tool
contract is a list of what an agent may do, and a much more interesting list of
what it may not.

    task loop:research -- --question "how do I make a column nullable"
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import brief
import gates
import research

FIXTURE = Path(__file__).parent / "fixtures" / "research.json"


def plan_questions(question: str) -> list[str]:
    """Break one question into the sub-questions a brief needs.

    ponytail: a template, not a planner. Swapping in a model here is the lab's
    stretch goal, and the checks downstream do not change when you do.
    """
    return [
        question,
        f"{question} common mistake",
        f"{question} how to verify",
    ]


def write_brief(question: str, findings: list[research.Finding]) -> tuple[str, list[str]]:
    """Assemble the brief. Every paragraph cites the finding it came from."""
    sources: list[str] = []
    for finding in findings:
        for citation in finding.citations:
            if citation not in sources:
                sources.append(citation)

    lines = [f"# {question}", ""]
    for finding in findings:
        if not finding.answer:
            continue
        marks = "".join(f"[{sources.index(c) + 1}]" for c in finding.citations if c in sources)
        if not marks and sources:
            marks = "[1]"
        lines += [f"## {finding.question}", "", f"{finding.answer} {marks}".strip(), ""]

    if sources:
        lines += ["## Sources", ""]
        lines += [f"{index}. {url}" for index, url in enumerate(sources, 1)]
        lines.append("")

    return "\n".join(lines), sources


def run(
    *,
    question: str,
    backend: research.Backend | None = None,
    out_dir: Path | str | None = None,
    budget: int = 3,
    write_trace: bool = True,
) -> dict:
    backend = backend or research.choose(fixture=FIXTURE)
    scholar = research.Researcher(
        backend=backend, budget=research.Budget(max_usd=0.20, max_calls=8, soft_usd=0.10)
    )
    out = Path(out_dir or (Path.cwd() / "work" / "research"))
    out.mkdir(parents=True, exist_ok=True)

    trace: dict = {"question": question, "backend": backend.name, "rounds": []}
    previous: tuple[str, ...] | None = None
    decision = gates.Decision(gates.RETRY, "not started")
    body = ""
    sources: list[str] = []

    for iteration in range(1, budget + 1):
        questions = plan_questions(question)
        findings: list[research.Finding] = []
        stopped = None
        for sub in questions:
            try:
                findings.append(scholar.ask(sub))
            except research.BudgetExceeded as exc:
                stopped = str(exc)
                break

        body, sources = write_brief(question, findings)
        body = brief.strip_em_dashes(body)
        score = brief.check(body, sources)

        decision = gates.decide(
            passed=score.passed,
            iteration=iteration,
            budget=budget,
            signature=score.signature(),
            previous_signature=previous,
            usd_left=0.0 if stopped else 1.0,
        )
        trace["rounds"].append(
            {
                "iteration": iteration,
                "questions": questions,
                "findings": [f.to_dict() for f in findings],
                "checks": {c.name: c.passed for c in score.checks},
                "gate": decision.gate,
                "reason": decision.reason,
                "budget_stopped": stopped,
            }
        )
        trace["report"] = score.report()
        if decision.stop:
            break
        previous = score.signature()

    path = out / "brief.md"
    path.write_text(body, encoding="utf-8")
    trace["brief"] = str(path)
    trace["sources"] = sources
    trace["gate"] = decision.gate
    trace["reason"] = decision.reason
    trace["budget"] = scholar.budget.line()

    if write_trace:
        (out / "last-research.json").write_text(json.dumps(trace, indent=2), encoding="utf-8")
        trace["written_at"] = time.time()
    return trace


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Research Assistant")
    parser.add_argument("--question", required=True)
    parser.add_argument("--backend", default="auto", choices=["auto", "fixture", "websearch"])
    parser.add_argument("--inbox", default=None, help="websearch answers file")
    parser.add_argument("--out", default=None)
    parser.add_argument("--budget", type=int, default=3)
    args = parser.parse_args(argv)

    if args.backend == "fixture":
        backend = research.FixtureBackend(FIXTURE)
    elif args.backend == "websearch":
        backend = research.WebSearchBackend(args.inbox or "work/research/websearch.json")
    else:
        backend = research.choose(fixture=FIXTURE, inbox=args.inbox)

    trace = run(question=args.question, backend=backend, out_dir=args.out, budget=args.budget)
    print(trace["report"])
    print()
    print(f"backend: {trace['backend']}   budget: {trace['budget']}")
    print(f"brief:   {trace['brief']}")
    print(f"gate:    {trace['gate']}")
    print(f"reason:  {trace['reason']}")
    return 0 if trace["gate"] == gates.PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
