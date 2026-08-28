#!/usr/bin/env python3
"""Lab 3. Research assistant on LangChain Deep Agents.

Python owns the budget and the brief check. Deep Agents isolates the researcher.
"""

from __future__ import annotations

import argparse

import brief
import researcher
import roleplan
import roles as deep

LOOP = "research"


def cast(contract):
    return roleplan.plan(contract, LOOP)


def build(contract, backend=None):
    return deep.subagents_for(contract, loop=LOOP, backend=backend)


def plan_questions(question: str) -> list[str]:
    return researcher.plan_questions(question)


def check_brief(body: str, sources: list[str]) -> brief.BriefScore:
    return brief.check(body, sources)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--question", default="sqlalchemy nullable datetime column")
    parser.add_argument("--backend", default="fixture", choices=["auto", "fixture", "websearch"])
    parser.add_argument("--out", default=None)
    parser.add_argument("--budget", type=int, default=3)
    parser.add_argument("--table-only", action="store_true")
    args = parser.parse_args(argv)

    print(roleplan.table(cast(None)))
    if args.table_only:
        return 0

    argv_run = ["--question", args.question, "--backend", args.backend, "--budget", str(args.budget)]
    if args.out:
        argv_run += ["--out", args.out]
    return researcher.main(argv_run)


if __name__ == "__main__":
    raise SystemExit(main())
