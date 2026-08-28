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
import json
import os
import sys
from pathlib import Path
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


def _contract(repo: str, *, table_only: bool):
    """The target repo, or None when only the table was asked for.

    The table is the one thing this folder can show with nothing cloned, and
    `--table-only` is the first command SPEC.md tells a reader to run, so it has
    to work before `task clone` has fetched anything. `roleplan.plan` already
    accepts None, and the enhancer cast reads the same either way, because no
    `.loop.yml` declares a doer.

    Anything past the table needs the real repo, so the error still fires there.
    """
    try:
        return Contract(repo)
    except ContractError:
        if not table_only:
            raise
        print(f"no target repo at {repo}. Printing the fallback cast.", file=sys.stderr)
        return None


def config(folder: Path | None = None) -> dict:
    """`config.json`, next to this file. It names the fork the loop talks to.

    Read from this module's own directory, not the caller's cwd. A relative path
    here depends on the invoking process starting in exactly the right place,
    and when it does not, this port can end up polling a different checkout that
    happens to also have a config.json.
    """
    path = Path(folder or Path(__file__).resolve().parent) / "config.json"
    if not path.exists():
        raise SystemExit(
            f"no {path}. Copy config.json.example to config.json and fill in your GitHub username."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def run(argv_repo: str, *, ticket: str | None, simulate: str | None) -> int:
    """One poll-and-act step. Needs `deepagents`, a key, and a target repo."""
    from enhancer import (  # noqa: PLC0415  (keeps --table-only free of it)
        Enhancer,
        EnhancerError,
        Gh,
    )

    settings = config()
    contract = Contract(argv_repo)
    try:
        runtime_backend = backend(contract)
    except ModuleNotFoundError as exc:
        if exc.name != "deepagents":
            raise
        print(
            "Deep Agents is not installed in this Python environment.\n"
            "From this folder, run:\n"
            "  task setup"
        )
        return 1
    engine = Enhancer(
        repo=Path(contract.repo),
        backend=runtime_backend,
        gh=Gh(settings["fork_owner"], settings["repo_name"]),
        budget=int(contract.budget.get("iterations", 3)),
        max_usd=float(contract.budget.get("usd", 2.0)),
    )
    try:
        outcomes = engine.poll(ticket, simulate_comment=simulate)
    except EnhancerError as exc:
        print(f"enhancer stopped: {exc}")
        return 1
    for outcome in outcomes:
        print(outcome)
    if not outcomes:
        print("no open enhancer tickets")
    elif any(outcome.status == "waiting" for outcome in outcomes):
        interval = settings.get("poll_interval", "10m")
        print(
            f"\nSome tickets are still waiting. Poll again: task poll-forever, "
            f"or /loop {interval} task run --"
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo", default=os.environ.get("TARGET_REPO", "../../work/northwind-field-crm")
    )
    parser.add_argument(
        "--table-only",
        action="store_true",
        help="print the role table and stop, so no SDK is needed",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="run one poll-and-act step over the open tickets",
    )
    parser.add_argument("--ticket", help="act on this ticket only")
    parser.add_argument(
        "--simulate-comment",
        help="use this text in place of the newest issue comment. Needs --ticket",
    )
    args = parser.parse_args(argv)

    if args.once or args.ticket:
        return run(args.repo, ticket=args.ticket, simulate=args.simulate_comment)

    contract = _contract(args.repo, table_only=args.table_only)
    print(roleplan.table(cast(contract)))
    if args.table_only:
        return 0
    print()
    print(build(contract))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
