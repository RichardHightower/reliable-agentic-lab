#!/usr/bin/env python3
"""Lab 1. Ticket Enhancer, on Claude Agent SDK.

The loop does not change. The rubric, the gates, and the exits are the same
objects lab 1 uses. What changes is how the runtime says "this role
may not write that file".

The Agent SDK scopes in two places and you need both. `tools=[...]` decides
whether a role can write at all. A `PreToolUse` hook decides which paths it may
write. The judge holds neither Edit nor Write, so there is nothing left for a
hook to guard.

    python loop.py --table-only

Nothing here calls a model. This module returns configuration, and your driver
is what runs it.
"""

from __future__ import annotations

import argparse

import roleplan
import roles as sdk
from contract import Contract

LOOP = "enhancer"


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


def backend(contract) -> "AgentSdkBackend":
    """A `doers.Backend` that runs the doer role through this runtime.

    See `adapter.py`. Needs `claude-agent-sdk` only once `.run()` is called.
    """
    from adapter import AgentSdkBackend  # noqa: PLC0415  (keeps --table-only free of it)

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

    contract = Contract(args.repo)
    print(roleplan.table(cast(contract)))
    if args.table_only:
        return 0
    print()
    print(build(contract))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
