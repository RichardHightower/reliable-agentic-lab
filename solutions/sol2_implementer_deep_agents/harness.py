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


def cast(contract):
    return roleplan.plan(contract, LOOP)


def build(contract):
    return deep.subagents_for(contract, loop=LOOP)


def backend(contract):
    from adapter import DeepAgentsBackend  # noqa: PLC0415

    return DeepAgentsBackend(deep.build_agent(contract, loop=LOOP))


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
    if doer == "deep":
        doer = backend(contract)
    trace = implementer.run(repo=args.repo, ticket_id=args.ticket, doer=doer, budget=args.budget)
    print(trace.get("rubric", ""))
    print()
    print(f"gate: {trace['gate']}")
    print(f"reason: {trace['reason']}")
    return 0 if trace["gate"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
