#!/usr/bin/env python3
"""Lab 4. Unattended PR fixer on Claude Agent SDK.

query(), not a chat client. Python owns the exits. PreToolUse owns write scope.
"""

from __future__ import annotations

import argparse
import os

import fixer
import roleplan
import roles as sdk
from contract import Contract, ContractError

LOOP = "fixer"


def cast(contract):
    return roleplan.plan(contract, LOOP)


def build(contract):
    return sdk.options_for(contract, loop=LOOP)


def backend(contract):
    from adapter import AgentSdkBackend  # noqa: PLC0415

    return AgentSdkBackend(build(contract))


def summarize_failure(run_result) -> str:
    return fixer.failure_summary(run_result)


def repair_until_green(contract, budget: int = 3, doer: str = "reference") -> dict:
    if doer == "sdk":
        doer = backend(contract)
    return fixer.run(repo=contract.repo, budget=budget, doer=doer, research_backend=None)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo", default=os.environ.get("TARGET_REPO", "../../work/northwind-field-crm")
    )
    parser.add_argument("--branch", default="broken-pr")
    parser.add_argument("--doer", default="reference", help="reference | sdk")
    parser.add_argument("--budget", type=int, default=None)
    parser.add_argument("--table-only", action="store_true")
    args = parser.parse_args(argv)

    try:
        contract = Contract(args.repo)
    except ContractError:
        if not args.table_only:
            raise
        print(f"# no target repo at {args.repo}. Showing the declared scopes.")
        contract = None

    print(roleplan.table(cast(contract)))
    if args.table_only:
        return 0

    doer = args.doer
    if doer == "sdk":
        doer = backend(contract)
    trace = fixer.run(
        repo=args.repo,
        doer=doer,
        branch=args.branch,
        budget=args.budget,
        research_backend=None,
    )
    print(f"gate: {trace['gate']}")
    print(f"reason: {trace['reason']}")
    if trace.get("comment"):
        print()
        print(trace["comment"])
    return 0 if trace.get("green") else 1


if __name__ == "__main__":
    raise SystemExit(main())
