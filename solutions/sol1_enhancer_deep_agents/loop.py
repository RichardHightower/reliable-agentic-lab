#!/usr/bin/env python3
"""Lab 1. Ticket Enhancer, on LangChain Deep Agents.

The loop does not change. The rubric, the gates, and the exits are the same
objects lab 1 uses. What changes is how the runtime says "this role
may not write that file".

Deep Agents scopes by handing each subagent its own tool list. A subagent can
only call what it was given. Path scope moves inside the write tool, which
checks the scope before it touches the disk.

    python loop.py --table-only

Nothing here calls a model. This module returns configuration, and your driver
is what runs it.
"""

from __future__ import annotations

import argparse
import sys
from typing import TYPE_CHECKING

import roleplan
import roles as deep
from contract import Contract, ContractError

if TYPE_CHECKING:  # the annotation only. `adapter` stays out of the table path.
    from adapter import DeepAgentsBackend

LOOP = "enhancer"


def cast(contract) -> dict[str, roleplan.RolePlan]:
    """The roles this loop runs.

    Read from `roleplan.py` in this folder, never restated here. A port that
    writes its own scopes drifts from the loop it claims to be, and it drifts
    silently.
    """
    return roleplan.plan(contract, LOOP)


def build(contract):
    """This runtime's configuration for the cast.

    Needs `deepagents` installed. `cast()` and the role table do not, which
    is why the tests can check the separation without either SDK present.
    """
    return deep.subagents_for(contract, loop=LOOP)


def backend(contract) -> DeepAgentsBackend:
    """A `doers.Backend` that runs the doer role through this runtime.

    See `adapter.py`. Needs `deepagents` only once this is called.
    """
    from adapter import DeepAgentsBackend  # noqa: PLC0415  (keeps --table-only free of it)

    return DeepAgentsBackend(deep.build_agent(contract, loop=LOOP))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default="../../work/northwind-field-crm")
    parser.add_argument(
        "--table-only",
        action="store_true",
        help="print the role table and stop, so no SDK is needed",
    )
    args = parser.parse_args(argv)

    try:
        contract = Contract(args.repo)
    except ContractError:
        # The table is the one thing this folder can show with nothing cloned.
        # `roleplan.plan` already accepts None, and the enhancer cast reads the
        # same either way, because no `.loop.yml` declares a doer.
        if not args.table_only:
            raise
        print(f"no target repo at {args.repo}. Printing the fallback cast.", file=sys.stderr)
        contract = None

    print(roleplan.table(cast(contract)))
    if args.table_only:
        return 0
    print()
    print(build(contract))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
