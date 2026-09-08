#!/usr/bin/env python3
"""Lab 2. Ticket Implementer on LangChain Deep Agents.

Python holds the loop. Deep Agents is the maker. The red gate is junit.xml.
"""

from __future__ import annotations

import argparse
import os

import implementer
import roleplan
import roles as deep
from contract import Contract, ContractError

LOOP = "implementer"
# #539. Left at 16 rather than raised: a `GraphRecursionError` now names
# itself and this number in the escalate reason (`adapter._describe_exc`),
# so a run that genuinely needs more turns says so instead of reading as an
# honest empty reply. Raise this if a live T001 code phase keeps naming it.
LIVE_RECURSION_LIMIT = 16


def cast(contract):
    return roleplan.plan(contract, LOOP)


def build(contract):
    return deep.subagents_for(contract, loop=LOOP)


def backend(contract):
    from adapter import DeepAgentsBackend  # noqa: PLC0415

    # One graph per implementation phase. A test-phase graph has no code
    # implementer to delegate to, so the role split is structural rather than
    # a request the parent model can ignore.
    return DeepAgentsBackend(
        phase_agents={
            "test": deep.build_agent(
                contract, loop=LOOP, subagent_names=frozenset({"test-implementer"})
            ),
            "code": deep.build_agent(
                contract, loop=LOOP, subagent_names=frozenset({"code-implementer"})
            ),
            # A9 (#437 #422). --planner deep reads this graph through
            # `plan()`. Built unconditionally, the way the other two are: it
            # is inert unless `_plan_from_backend` calls it.
            "plan": deep.build_agent(
                contract, loop=LOOP, subagent_names=frozenset({"planner"})
            ),
        },
        judge_agent=deep.build_agent(
            contract, loop=LOOP, subagent_names=frozenset({"judge"})
        ),
        # The runtime's recursion guard is the model-turn ceiling for this
        # live probe. It leaves time for the deterministic test/rubric pass and
        # receipt instead of letting the outer 420-second watchdog kill it.
        recursion_limit=LIVE_RECURSION_LIMIT,
    )


def red_gate(before, after) -> set[str]:
    seen = before.junit.passed_ids | before.junit.failed_ids
    return implementer._new_test_ids(seen, after.junit.failed_ids)


def run_loop(contract, budget: int = 3, ticket_id: str = "T001", doer: str = "reference") -> dict:
    """Python owns Pass / Retry / Escalate. `doer` may be a Deep Agents backend."""
    return implementer.run(
        repo=contract.repo,
        ticket_id=ticket_id,
        budget=budget,
        doer=doer,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo", default=os.environ.get("TARGET_REPO", "../../work/northwind-field-crm")
    )
    parser.add_argument("--ticket", default="T001")
    parser.add_argument("--doer", default="reference", help="reference | deep | none")
    parser.add_argument(
        "--planner",
        default="derived",
        help=(
            "derived | sdk | deep. derived is plan_for and calls no model. "
            "--doer none or reference forces derived regardless of this flag."
        ),
    )
    parser.add_argument("--budget", type=int, default=None)
    parser.add_argument("--table-only", action="store_true")
    parser.add_argument(
        "--cleanup", action="store_true", help="remove the worktree after the run"
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="re-enter the last killed run from its own state.json, instead of starting over.",
    )
    args = parser.parse_args(argv)

    try:
        contract = Contract(args.repo)
    except ContractError as exc:
        # Folded finding, judge of PR #497 (A5). This used to bare `raise`,
        # which meant `harness.py --repo <nonexistent>` printed a traceback
        # instead of the one line `implementer.main` already prints for the
        # same error.
        if not args.table_only:
            print(f"error: {exc}")
            return 1
        print(f"# no target repo at {args.repo}. Showing the declared scopes.")
        contract = None

    print(roleplan.table(cast(contract)))
    if args.table_only:
        return 0

    doer = args.doer
    if doer == "deep":
        doer = backend(contract)
    try:
        trace = implementer.run(
            repo=args.repo,
            ticket_id=args.ticket,
            doer=doer,
            planner=args.planner,
            budget=args.budget,
            cleanup=args.cleanup,
            resume=args.resume,
        )
    except ContractError as exc:
        print(f"error: {exc}")
        return 1

    print(trace.get("rubric", ""))
    print()
    print(f"gate: {trace['gate']}")
    print(f"reason: {trace['reason']}")
    implementer._print_worktree_status(trace)
    return 0 if trace["gate"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
