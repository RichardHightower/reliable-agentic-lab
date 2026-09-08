#!/usr/bin/env python3
"""Lab 2. Ticket Implementer on Claude Agent SDK.

Python holds the loop. The Agent SDK is the maker. The red gate is junit.xml.

The Agent SDK scopes in two places and you need both. `tools=[...]` decides
whether a role can write at all. A `PreToolUse` hook decides which paths it may
write. The judge holds neither Edit nor Write, so there is nothing left for a
hook to guard.

    python harness.py --table-only
    python harness.py --repo ../../work/northwind-field-crm --ticket T001 --doer reference
    python harness.py --repo ../../work/northwind-field-crm --ticket T001 --doer sdk
"""

from __future__ import annotations

import argparse
import os

import implementer
import roleplan
import roles as sdk
from contract import Contract, ContractError
from load_agents import DEFAULT_MAX_TURNS

LOOP = "implementer"


def cast(contract) -> dict[str, roleplan.RolePlan]:
    """The roles this loop runs.

    Read from this folder's `roleplan.py`, never restated here. A port that
    writes its own scopes is a port that drifts from the loop it claims to be.
    """
    return roleplan.plan(contract, LOOP)


def build(contract, *, max_turns: int = DEFAULT_MAX_TURNS, role_names=None):
    """This runtime's configuration for the cast.

    Needs `claude-agent-sdk` installed. `cast()` and the role table do not.
    """
    kwargs = {"max_turns": max_turns}
    if role_names is not None:
        kwargs["role_names"] = role_names
    return sdk.options_for(contract, loop=LOOP, **kwargs)


def backend(contract, *, max_turns: int = DEFAULT_MAX_TURNS):
    """A `doers.Backend` that runs each phase through its own Agent SDK graph."""
    from adapter import AgentSdkBackend, AgentSdkPhaseBackend  # noqa: PLC0415

    return AgentSdkPhaseBackend(
        test=AgentSdkBackend(
            build(contract, max_turns=max_turns, role_names=frozenset({"test_implementer"}))
        ),
        code=AgentSdkBackend(
            build(contract, max_turns=max_turns, role_names=frozenset({"code_implementer"}))
        ),
        judge=AgentSdkBackend(
            build(contract, max_turns=max_turns, role_names=frozenset({"judge"}))
        ),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo", default=os.environ.get("TARGET_REPO", "../../work/northwind-field-crm")
    )
    parser.add_argument("--ticket", default="T001")
    parser.add_argument("--doer", default="reference", help="reference | sdk | none")
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
    if doer == "sdk":
        doer = backend(contract)
    try:
        trace = implementer.run(
            repo=args.repo,
            ticket_id=args.ticket,
            doer=doer,
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
