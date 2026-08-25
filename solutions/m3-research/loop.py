#!/usr/bin/env python3
"""Module 3 research report loop.

Fact-check and style-guide enforcer run as editor/checker domains.
Python holds retries, budget, and stop rules.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import fact_checker
import gates
import researcher
import style_enforcer
import writer

DEFAULT_TOPIC = "Should CRM sales tasks store optional UTC ISO due dates?"


def run_domain(
    *,
    name: str,
    check_fn,
    repair_fn,
    report_path: Path,
    notes: dict,
    cost: float,
    max_loops: int,
    max_budget: float,
) -> dict:
    previous = None
    steps = []
    last = {"passed": False, "gate": gates.ESCALATE, "cost": cost}
    for iteration in range(1, max_loops + 1):
        if name == "FACT":
            verdict = check_fn(report_path.read_text(encoding="utf-8"), notes)
        else:
            verdict = check_fn(report_path.read_text(encoding="utf-8"))
        cost += gates.CALL_COST
        failed = verdict.get("failed_ids") or []
        decision = gates.decide(
            passed=verdict["passed"],
            iteration=iteration,
            failed_ids=failed,
            previous_failed_ids=previous,
            cost=cost,
            max_loops=max_loops,
            max_budget=max_budget,
        )
        step = {
            "domain": name,
            "iteration": iteration,
            "passed": verdict["passed"],
            "issues": verdict.get("issues", []),
            "gate": decision["gate"],
            "cost": cost,
        }
        steps.append(step)
        last = {**decision, "passed": verdict["passed"], "cost": cost, "failed_ids": failed}
        if decision["gate"] != gates.RETRY:
            break
        repair_fn(report_path, verdict.get("issues", []))
        cost += gates.CALL_COST
        previous = list(failed)
    return {"steps": steps, "score": last, "cost": cost}


def run(
    topic: str = DEFAULT_TOPIC,
    *,
    dirty: bool = False,
    max_loops: int = gates.DEFAULT_MAX_LOOPS,
    max_budget: float = gates.DEFAULT_MAX_BUDGET,
    work_dir: Path | None = None,
) -> dict:
    work = work_dir or (HERE / "work")
    work.mkdir(parents=True, exist_ok=True)
    cost = 0.0
    research = researcher.research(topic, work)
    cost += gates.CALL_COST
    notes = json.loads(Path(research["path"]).read_text(encoding="utf-8"))
    report_path = writer.draft(notes, work, dirty=dirty)
    cost += gates.CALL_COST

    fact = run_domain(
        name="FACT",
        check_fn=fact_checker.check_facts,
        repair_fn=writer.repair_facts,
        report_path=report_path,
        notes=notes,
        cost=cost,
        max_loops=max_loops,
        max_budget=max_budget,
    )
    cost = fact["cost"]
    style = {"steps": [], "score": {"passed": False, "gate": gates.ESCALATE}}
    if fact["score"].get("passed"):
        cleaned = style_enforcer.strip_emdashes(report_path.read_text(encoding="utf-8"))
        report_path.write_text(cleaned, encoding="utf-8")
        style = run_domain(
            name="STYLE",
            check_fn=style_enforcer.check_style,
            repair_fn=writer.repair_style,
            report_path=report_path,
            notes=notes,
            cost=cost,
            max_loops=max_loops,
            max_budget=max_budget,
        )
        cost = style["cost"]

    passed = bool(fact["score"].get("passed") and style["score"].get("passed"))
    payload = {
        "trace_id": "m3-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "topic": topic,
        "research_summary": research["summary"],
        "research_backend": research["backend"],
        "report_path": str(report_path),
        "fact": fact,
        "style": style,
        "cost": cost,
        "max_loops": max_loops,
        "max_budget": max_budget,
        "passed": passed,
        "gate": "pass" if passed else "escalate",
    }
    (work / "last-loop.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Module 3 research report loop")
    parser.add_argument("--topic", default=DEFAULT_TOPIC)
    parser.add_argument("--dirty", action="store_true", help="Start from a failing draft to prove retry.")
    parser.add_argument("--max-loops", type=int, default=gates.DEFAULT_MAX_LOOPS)
    parser.add_argument("--max-budget", type=float, default=gates.DEFAULT_MAX_BUDGET)
    args = parser.parse_args()
    payload = run(
        args.topic,
        dirty=args.dirty,
        max_loops=args.max_loops,
        max_budget=args.max_budget,
    )
    print(json.dumps({"passed": payload["passed"], "gate": payload["gate"], "cost": payload["cost"]}, indent=2))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
