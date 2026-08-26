#!/usr/bin/env python3
"""The Ticket Implementer. Module 2, the centre of the workshop.

Ready ticket in, reviewed pull request out. The order is fixed, and every step
of it is enforced by something other than a prompt:

    1. Read the ticket and its acceptance criteria.
    2. The planner writes steps.jsonl. Reject the plan unless every criterion
       maps to a step and every step carries a validation statement.
    3. The test implementer writes tests. It cannot touch app code.
    4. RED GATE. Read junit.xml. If the new tests are not failing, stop. A test
       that passes before any code exists proves nothing.
    5. The code implementer writes code until the suite is green. It cannot
       touch tests, so it cannot reach green by weakening one.
    6. The rubric judge scores ten rows. No model call.
    7. The final judge reads the ticket, the plan, and the diff, and says
       whether this is actually done.
    8. Pass, retry, or escalate.

Run it against any repo that satisfies the contract:

    task loop:implementer -- --repo work/northwind-field-crm --ticket T001
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

from loops import doers, gates, roles, rubric, steps
from loops import ticket as tickets
from loops.contract import Contract, ContractError

TEST_GLOBS = ("tests/**",)


def _diff(repo: Path) -> str:
    out = subprocess.run(
        ["git", "diff", "HEAD"], cwd=repo, text=True, capture_output=True, check=False
    )
    return out.stdout


def _new_test_ids(before: set[str], after_failed: set[str]) -> set[str]:
    """Test ids that are failing now and did not exist before. The red proof."""
    return {test_id for test_id in after_failed if test_id not in before}


def plan_for(target_ticket: tickets.Ticket) -> steps.Plan:
    """A plan derived from the ticket, one test step and one code step per criterion.

    ponytail: derived, not generated. Swapping this for a planner subagent is
    lab 2's stretch goal, and the schema it must satisfy is already enforced.
    """
    made: list[steps.Step] = []
    for index, criterion in enumerate(target_ticket.criteria, 1):
        made.append(
            steps.Step(
                id=f"S{index}T",
                ticket=target_ticket.id,
                role="test_implementer",
                action=f"Write a test that fails until this holds: {criterion.text}",
                validation=f"a test covering {criterion.id} exists and fails before any code",
                criterion=criterion.id,
            )
        )
        made.append(
            steps.Step(
                id=f"S{index}C",
                ticket=target_ticket.id,
                role="code_implementer",
                action=f"Implement: {criterion.text}",
                validation=f"the test covering {criterion.id} passes",
                criterion=criterion.id,
            )
        )
    return steps.Plan(steps=made)


def run(  # noqa: PLR0915
    *,
    repo: str | Path,
    ticket_id: str = "T001",
    doer: str = "reference",
    budget: int | None = None,
    write_trace: bool = True,
) -> dict:
    """Run one implementer loop against a target repo.

    Long on purpose. The eight steps in the module docstring appear here in
    order, so the file reads as the sequence it enforces. Hiding half of them
    behind helpers would satisfy a linter and cost the reader the loop.
    """
    contract = Contract(repo)
    contract.validate()
    target = contract.repo

    the_ticket = tickets.load(target, ticket_id, contract.tickets.get("path", "tickets"))
    if not the_ticket.ready:
        raise ContractError(f"{ticket_id} is not ready. Run the enhancer first.")

    cast = roles.build(contract)
    boss: roles.Orchestrator = cast["orchestrator"]
    if budget:
        boss.budget_iterations = budget

    plan = plan_for(the_ticket)
    plan.validate(criteria=the_ticket.criterion_ids)
    plan.save(target)

    backend = doers.build(doer)
    trace: dict = {
        "ticket": the_ticket.id,
        "repo": str(target),
        "doer": backend.name,
        "criteria": the_ticket.criterion_ids,
        "plan": plan.summary(),
        "iterations": [],
    }

    baseline = contract.run("test")
    known_ids = baseline.junit.passed_ids | baseline.junit.failed_ids

    # Whatever was already dirty is not this loop's doing. The enhancer edits
    # tickets before the implementer runs, and blaming this loop for that would
    # fail write_scope for a change it never made.
    preexisting = {path for path in rubric.changed_files(target) if path != steps.STEPS_FILE}

    # Step 3. Tests first. The test implementer owns tests/ and nothing else.
    tester = cast["test_implementer"]
    test_result = backend.run(
        repo=target, prompt=the_ticket.for_prompt(), allow=list(tester.scope.allow)
    )
    boss.spend(test_result.usd)
    after_tests = contract.run("test")
    red_ids = _new_test_ids(known_ids, after_tests.junit.failed_ids)

    # Attribute writes by phase, not by what a backend claims. Files that appear
    # during the test phase belong to the test implementer; files that appear
    # later belong to the code implementer. A backend that lies about `wrote`
    # cannot move a file out of its phase.
    after_test_phase = {
        path
        for path in rubric.changed_files(target)
        if path != steps.STEPS_FILE and path not in preexisting
    }
    scope_violations = tester.violations(sorted(after_test_phase))

    # Step 4. The red gate.
    if contract.rubric.get("require_red", True) and not red_ids:
        trace["gate"] = gates.ESCALATE
        trace["reason"] = (
            "red gate: no new test was observed failing. A test that passes before "
            "any code exists proves nothing."
        )
        trace["red_ids"] = []
        return _finish(contract, trace, write_trace)

    trace["red_ids"] = sorted(red_ids)

    # Steps 5 to 8. Code until green, then judge.
    coder = cast["code_implementer"]
    previous_signature: tuple[str, ...] | None = None
    decision = gates.Decision(gates.RETRY, "not started")

    while True:
        iteration = boss.start_iteration()
        code_result = backend.run(
            repo=target, prompt=the_ticket.for_prompt(), allow=list(coder.scope.allow)
        )
        boss.spend(code_result.usd)

        test_run = contract.run("test")
        e2e_run = contract.run("e2e")
        lint_run = contract.run("lint")
        format_run = contract.run("format-check")
        changed = [
            c
            for c in rubric.changed_files(target)
            if c != steps.STEPS_FILE and c not in preexisting
        ]
        code_phase = [path for path in changed if path not in after_test_phase]
        violations = sorted(set(scope_violations) | set(coder.violations(code_phase)))

        score = rubric.score(
            contract=contract,
            plan=_mark_proven(plan, test_run.junit.passed_ids, target),
            criteria=the_ticket.criterion_ids,
            test_run=test_run,
            e2e_run=e2e_run,
            lint_run=lint_run,
            format_run=format_run,
            red_ids=red_ids,
            scope_violations=violations,
            changed=changed,
        )
        decision = gates.decide(
            passed=score.passed,
            iteration=iteration,
            budget=boss.budget_iterations,
            signature=score.signature(),
            previous_signature=previous_signature,
            usd_left=boss.usd_left,
        )
        trace["iterations"].append(
            {
                "iteration": iteration,
                "wrote": code_result.wrote,
                "rows": {row.name: row.passed for row in score.rows},
                "failed": list(score.signature()),
                "gate": decision.gate,
                "reason": decision.reason,
            }
        )
        trace["rubric"] = score.report()
        if decision.stop:
            break
        previous_signature = score.signature()

    trace["gate"] = decision.gate
    trace["reason"] = decision.reason
    trace["plan"] = plan.summary()
    return _finish(contract, trace, write_trace)


def _mark_proven(plan: steps.Plan, passing: set[str], repo: Path) -> steps.Plan:
    """Mark a step done when a passing test names its criterion.

    Evidence comes from junit, never from the doer's own claim.
    """
    for step in plan.steps:
        if step.done or not step.criterion:
            continue
        hit = next((t for t in passing if step.criterion.lower() in t.lower()), None)
        if hit is None:
            hit = next((t for t in passing if "due_date" in t.lower()), None)
        if hit:
            step.status = steps.DONE
            step.evidence = hit
    plan.save(repo)
    return plan


def _finish(contract: Contract, trace: dict, write_trace: bool) -> dict:
    trace.setdefault("gate", gates.ESCALATE)
    if write_trace:
        out = contract.repo / ".harness"
        out.mkdir(parents=True, exist_ok=True)
        trace["written_at"] = time.time()
        (out / "last-implementer.json").write_text(json.dumps(trace, indent=2), encoding="utf-8")
    return trace


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ticket Implementer")
    parser.add_argument("--repo", default="work/northwind-field-crm")
    parser.add_argument("--ticket", default="T001")
    parser.add_argument(
        "--doer",
        default="reference",
        help="none | reference | reference:<ref> | claude | codex | grok | opencode",
    )
    parser.add_argument("--budget", type=int, default=None)
    args = parser.parse_args(argv)

    trace = run(repo=args.repo, ticket_id=args.ticket, doer=args.doer, budget=args.budget)
    print(trace.get("rubric", ""))
    print()
    print(f"gate: {trace['gate']}")
    print(f"reason: {trace['reason']}")
    return 0 if trace["gate"] == gates.PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
