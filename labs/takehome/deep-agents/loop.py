#!/usr/bin/env python3
"""Take-home. The Module 2 implementer, on LangChain Deep Agents.

Fill the two functions below.

Nothing about the loop changes. The rubric, the gate, and the red gate are the
same objects Module 2 used. What changes is how this runtime says "this role
may not write that file".

    python loop.py --repo ../../../work/northwind-field-crm --dry-run

`--dry-run` builds the configuration and prints it. It calls no model, so run
it first and read what you built before you spend anything.

Read `solutions.deep_agents.roles` only if you stall. It is the answer.
"""

from __future__ import annotations

import argparse

import roleplan
from contract import Contract
from observability import trace


def build(contract: Contract):
    """Return this runtime's configuration for the five roles.

    Read the scopes from `roleplan.plan(contract)`. Do not restate them here.
    There is one role table and it lives in the target repo's `.loop.yml`.

    The judge must end up holding no tool that can write. Check it with
    `task test -- loops/tests/test_runtime_ports.py`, which needs no API key.
    """
    raise NotImplementedError("fill me in")


def run(contract: Contract, ticket_id: str = "T001", budget: int = 3) -> dict:
    """Run the loop: plan, tests, red gate, code, rubric, gate.

    Python holds the loop. The model never counts its own retries. Score with
    `loops.rubric.score` and decide with `loops.gates.decide`, exactly as
    Module 2 does.
    """
    raise NotImplementedError("fill me in")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default="../../../work/northwind-field-crm")
    parser.add_argument("--ticket", default="T001")
    parser.add_argument("--budget", type=int, default=3)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="build the configuration, print the role table, and call no model",
    )
    args = parser.parse_args(argv)

    contract = Contract(args.repo)
    contract.validate()

    print(roleplan.table(roleplan.plan(contract)))
    if args.dry_run:
        print()
        print(build(contract))
        return 0

    with trace("deep_agents-implementer", ticket=args.ticket) as span:
        result = run(contract, args.ticket, args.budget)
        span.result(**{k: v for k, v in result.items() if k in ("gate", "reason")})
    print(f"\ngate: {result['gate']}\nreason: {result['reason']}")
    return 0 if result["gate"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
