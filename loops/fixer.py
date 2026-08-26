#!/usr/bin/env python3
"""The Broken PR Fixer. Module 4, the production pattern.

A failing branch in, a green one out, or an honest explanation of why not.

It is the same graph as the implementer with two differences. There is no plan
to write, because the work is already defined by what is red. And it runs
unattended, so its exits matter more than its successes: nobody is watching to
stop it.

When the failure names an error it cannot place, it asks the research boundary
once, inside the budget, and carries the answer into the next attempt.

    task loop:fixer -- --repo work/northwind-field-crm
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from pathlib import Path

from loops import doers, gates, research, roles, rubric
from loops.contract import Contract

ERROR_IN_OUTPUT = re.compile(r"\b([A-Z][A-Za-z]*(?:Error|Exception))\b[^\n]*")


def failure_summary(run_result) -> str:
    """What the checker reads. Failed test ids and the first real error line."""
    failed = sorted(run_result.junit.failed_ids)
    lines = [f"{len(failed)} failing: {', '.join(failed[:5])}"] if failed else ["the suite is red"]
    error = ERROR_IN_OUTPUT.search(run_result.output or "")
    if error:
        lines.append(error.group(0).strip()[:200])
    return "\n".join(lines)


def run(  # noqa: PLR0913, PLR0915
    *,
    repo: str | Path,
    doer: str = "reference",
    fix_ref: str = "known-good",
    budget: int | None = None,
    research_backend: research.Backend | None = None,
    write_trace: bool = True,
) -> dict:
    """Repair until green, the budget is spent, or the same rows fail twice."""
    contract = Contract(repo)
    contract.validate()
    target = contract.repo

    cast = roles.build(contract)
    boss: roles.Orchestrator = cast["orchestrator"]
    coder = cast["code_implementer"]
    if budget:
        boss.budget_iterations = budget

    backend = doers.build(f"reference:{fix_ref}" if doer == "reference" else doer)
    scholar = (
        research.Researcher(
            backend=research_backend, budget=research.Budget(max_calls=2, max_usd=0.05)
        )
        if research_backend
        else None
    )

    preexisting = set(rubric.changed_files(target))
    trace: dict = {
        "repo": str(target),
        "branch": subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=target,
            text=True,
            capture_output=True,
            check=False,
        ).stdout.strip(),
        "doer": backend.name,
        "attempts": [],
    }

    previous: tuple[str, ...] | None = None
    decision = gates.Decision(gates.RETRY, "not started")

    while True:
        iteration = boss.start_iteration()
        before = contract.run("test")
        signature = tuple(sorted(before.junit.failed_ids))

        if before.junit.green:
            decision = gates.Decision(gates.PASS, "the suite is green")
            trace["attempts"].append({"iteration": iteration, "failing": [], "gate": decision.gate})
            break

        attempt: dict = {
            "iteration": iteration,
            "failing": list(signature),
            "summary": failure_summary(before),
        }

        if scholar is not None:
            error = ERROR_IN_OUTPUT.search(before.output or "")
            if error:
                try:
                    finding = scholar.ask(error.group(0).strip()[:200])
                    if finding.answer:
                        attempt["research"] = finding.to_dict()
                except research.BudgetExceeded as exc:
                    attempt["research_stopped"] = str(exc)

        decision = gates.decide(
            passed=False,
            iteration=iteration,
            budget=boss.budget_iterations,
            signature=signature,
            previous_signature=previous,
            usd_left=boss.usd_left,
        )
        if decision.stop:
            attempt["gate"] = decision.gate
            trace["attempts"].append(attempt)
            break

        result = backend.run(
            repo=target,
            prompt=gates.retry_instruction(decision, list(signature)),
            allow=list(coder.scope.allow),
        )
        boss.spend(result.usd)
        attempt["wrote"] = result.wrote
        attempt["gate"] = decision.gate
        trace["attempts"].append(attempt)
        previous = signature

    after = contract.run("test")
    changed = [p for p in rubric.changed_files(target) if p not in preexisting]
    violations = coder.violations(changed)
    if violations:
        decision = gates.Decision(
            gates.ESCALATE, f"the fix wrote outside its scope: {violations[:3]}"
        )

    trace["gate"] = decision.gate
    trace["reason"] = decision.reason
    trace["green"] = after.junit.green and not violations
    trace["changed"] = changed
    if scholar:
        trace["research_budget"] = scholar.budget.line()
    if not trace["green"]:
        trace["comment"] = (
            "The fixer gave up.\n\n"
            f"Reason: {decision.reason}\n\n"
            f"Still failing: {sorted(after.junit.failed_ids)}\n\n"
            "A human should take this one."
        )

    if write_trace:
        out = target / ".harness"
        out.mkdir(parents=True, exist_ok=True)
        trace["written_at"] = time.time()
        (out / "last-fixer.json").write_text(json.dumps(trace, indent=2), encoding="utf-8")
    return trace


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Broken PR Fixer")
    parser.add_argument("--repo", default="work/northwind-field-crm")
    parser.add_argument("--doer", default="reference")
    parser.add_argument("--fix-ref", default="known-good")
    parser.add_argument("--budget", type=int, default=None)
    parser.add_argument("--research", default="fixture", choices=["off", "fixture", "auto"])
    args = parser.parse_args(argv)

    backend = None
    fixture = Path(__file__).parent / "fixtures" / "research.json"
    if args.research == "fixture":
        backend = research.FixtureBackend(fixture)
    elif args.research == "auto":
        backend = research.choose(fixture=fixture)

    trace = run(
        repo=args.repo,
        doer=args.doer,
        fix_ref=args.fix_ref,
        budget=args.budget,
        research_backend=backend,
    )
    for attempt in trace["attempts"]:
        print(
            f"attempt {attempt['iteration']}: {len(attempt['failing'])} failing -> {attempt['gate']}"
        )
        if attempt.get("summary"):
            print(f"  {attempt['summary'].splitlines()[0]}")
    print()
    print(f"gate: {trace['gate']}")
    print(f"reason: {trace['reason']}")
    if trace.get("comment"):
        print()
        print(trace["comment"])
    return 0 if trace["green"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
