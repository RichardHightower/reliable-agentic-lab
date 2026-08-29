#!/usr/bin/env python3
"""Lab 3. Research on LangChain Deep Agents.

Two entry points, one folder, one role table.

    loop.py --question "..."   the lab answer: a question in, a cited brief out
    loop.py --paper --topic "..."   the take-home: a topic in, a white paper out

The brief is the small version of the paper. Both plan questions, search through
one tool boundary, and refuse to ship anything uncited. The paper adds
corroboration against a second source, figures, and a publish step. The gates and
the exits are the same objects.

    python3 loop.py --table-only

`--table-only` never imports a runtime. That is the load-bearing convention in
this folder: the role table and the whole test suite run with no SDK installed,
so a reader can see what a role may write before installing anything.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import brief
import researcher
import roleplan

LOOP = "research"
PAPER_LOOP = "paper"
HERE = Path(__file__).resolve().parent


def cast(contract, loop: str = LOOP):
    """The roles this loop runs, read from `roleplan.py` and never restated.

    A port that writes its own scopes drifts from the loop it claims to be, and
    it drifts silently.
    """
    return roleplan.plan(contract, loop)


def build(contract, backend=None, loop: str = LOOP):
    """This runtime's configuration for the cast. Needs `deepagents` installed."""
    import roles as deep  # noqa: PLC0415  (keeps --table-only free of it)

    return deep.subagents_for(contract, loop=loop, backend=backend)


def plan_questions(question: str) -> list[str]:
    return researcher.plan_questions(question)


def check_brief(body: str, sources: list[str]) -> brief.BriefScore:
    return brief.check(body, sources)


def second_brain() -> Path | None:
    """Where prior research lives, when it is on this machine at all.

    Never a hard dependency. An attendee who cloned one folder has no brain, and
    the loop has to run for them exactly as it runs here.
    """
    raw = os.environ.get("SECOND_BRAIN")
    candidate = Path(raw) if raw else HERE / ".." / ".." / ".." / "loop_eng_2nd_brain" / "knowledge"
    return candidate if candidate.is_dir() else None


def run_paper(args) -> int:
    import paper  # noqa: PLC0415  (keeps --table-only free of it)

    run = paper.build(
        args.topic,
        backend_name=args.backend,
        work_root=args.work_root,
        brain=second_brain(),
        max_usd=args.max_usd,
        max_verify=args.max_verify,
        attempts=args.attempts,
        theme=args.theme,
        polish=not args.no_polish,
        publish=args.publish,
        debug=args.debug,
    )
    return run.run()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--question", default="sqlalchemy nullable datetime column")
    parser.add_argument("--backend", default="fixture", choices=["auto", "fixture", "websearch"])
    parser.add_argument("--out", default=None)
    parser.add_argument("--budget", type=int, default=3)
    parser.add_argument("--table-only", action="store_true")

    paper_args = parser.add_argument_group("white paper")
    paper_args.add_argument("--paper", action="store_true", help="run the nine stage pipeline")
    paper_args.add_argument("--topic", default=None, help="what the paper is about")
    paper_args.add_argument("--work-root", default=None, help="where runs are kept")
    paper_args.add_argument("--max-usd", type=float, default=5.0, help="the hard cost cap")
    paper_args.add_argument("--attempts", type=int, default=3, help="retries per stage")
    paper_args.add_argument(
        "--max-verify",
        type=int,
        default=12,
        help="how many claims one verify stage cross-checks. The verifier "
        "searches once per claim, so this is the size of the work.",
    )
    paper_args.add_argument("--theme", default="spillwave-light")
    paper_args.add_argument("--no-polish", action="store_true", help="SVG figures only")
    paper_args.add_argument("--publish", action="store_true", help="push to a secret gist")
    paper_args.add_argument(
        "--debug",
        action="store_true",
        help="stream parent-graph and delegated-subgraph diagnostics to stderr (live runs only)",
    )
    args = parser.parse_args(argv)

    loop = PAPER_LOOP if (args.paper or args.topic) else LOOP
    print(roleplan.table(cast(None, loop)))
    if args.table_only:
        return 0
    print()

    if loop == PAPER_LOOP:
        if not args.topic:
            parser.error("--paper needs --topic")
        return run_paper(args)

    argv_run = [
        "--question",
        args.question,
        "--backend",
        args.backend,
        "--budget",
        str(args.budget),
    ]
    if args.out:
        argv_run += ["--out", args.out]
    return researcher.main(argv_run)


if __name__ == "__main__":
    raise SystemExit(main())
