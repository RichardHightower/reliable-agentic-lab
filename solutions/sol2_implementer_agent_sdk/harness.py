#!/usr/bin/env python3
"""Lab 2. Ticket Implementer and the harness, on Claude Agent SDK.

The loop does not change. The rubric, the gates, and the exits are the same
objects lab 2 uses. What changes is how the runtime says "this role
may not write that file".

The Agent SDK scopes in two places and you need both. `tools=[...]` decides
whether a role can write at all. A `PreToolUse` hook decides which paths it may
write. The judge holds neither Edit nor Write, so there is nothing left for a
hook to guard.

    python harness.py --table-only

Nothing here calls a model. This module returns configuration, and your driver
is what runs it.
"""

from __future__ import annotations

import argparse

from contract import Contract, ContractError
import roleplan
import roles as sdk
from adapter import AgentSdkBackend

LOOP = "implementer"


def cast(contract) -> dict[str, roleplan.RolePlan]:
    """The roles this loop runs.

    Read from `solutions/roleplan.py`, never restated here. A port that writes
    its own scopes is a port that drifts from the loop it claims to be, and it
    drifts silently.
    """
    return roleplan.plan(contract, LOOP)


def build(contract):
    """This runtime's configuration for the cast.

    Needs `claude-agent-sdk` installed. `cast()` and the role table do not, which
    is why the tests can check the separation without either SDK present.
    """
    return sdk.options_for(contract, loop=LOOP)


def backend(contract) -> AgentSdkBackend:
    """A `doers.Backend` that runs a role's prompt through this runtime.

    This is what a driver hands to `loops.implementer.run(doer=...)` in place
    of the `reference` stand-in, per GitHub issue #2. Needs `claude-agent-sdk`
    installed; `build()` is what raises if it is not.
    """
    return AgentSdkBackend(build(contract))


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
        # The table is the one thing this folder can show with nothing cloned,
        # and SPEC.md tells a reader to run it before `task setup`.
        # `roleplan.plan` already accepts None and falls back to the declared
        # scope. Anything past the table needs the real repo, so the error
        # still fires there.
        if not args.table_only:
            raise
        print(f"# no target repo at {args.repo}. Showing the declared scopes.")
        contract = None

    print(roleplan.table(cast(contract)))
    if args.table_only:
        return 0
    print()
    print(build(contract))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
