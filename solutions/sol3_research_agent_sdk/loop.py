#!/usr/bin/env python3
"""Lab 3. Deep research over MCP, on the Claude Agent SDK.

A topic in, an evidence-backed white paper out. The same graph as the other
three loops on a different object, which is the point: swap the object, keep
the graph.

    plan       break the topic into sections and questions
    research   ask the boundary, inside a budget
    verify     ask again, independently, and record where the two disagree
    diagram    draw the figures and render them
    write      assemble from verified claims only
    check      grounding, citations, figures, and style, deterministically
    review     the judge, on what a script cannot score
    gate       pass, retry, or escalate

The tool boundary is the lesson. This loop can search and it can write inside
its own work directory. It cannot merge, deploy, or touch a repo.

    python3 loop.py --table-only
    python3 loop.py --topic "loop engineering exit criteria" --backend fixture
    python3 loop.py --topic "..." --publish

Nothing above `--table-only` calls a model, which is why the role table prints
on a machine with no SDK installed.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import roleplan

LOOP = "research"
FOLDER = Path(__file__).resolve().parent
FIXTURE = FOLDER / "fixtures" / "research.json"


def cast(contract=None) -> dict[str, roleplan.RolePlan]:
    """The roles this loop runs.

    Read from `roleplan.py`, never restated here. A port that writes its own
    scopes is a port that drifts from the loop it claims to be, and it drifts
    silently.
    """
    return roleplan.plan(contract, LOOP)


def build(work_dir, max_usd=None):
    """This runtime's configuration for the cast.

    Needs `claude-agent-sdk` installed. `cast()` and the role table do not,
    which is why the tests check the separation with no SDK present.
    """
    import roles as sdk  # noqa: PLC0415  (keeps --table-only free of the SDK)

    return sdk.options_for(work_dir, max_usd=max_usd, loop=LOOP)


def pick_turns(
    name: str,
    work_dir: Path,
    max_usd: float | None,
    on_cost,
    fixture: Path = FIXTURE,
):
    """Choose a runtime for the six model turns.

    `agent` is the real one: every turn is a named subagent holding the MCP
    tools. `perplexity` searches for real and templates the prose, which is
    useful when you want current sources and do not want to spend a model on
    the writing. `fixture` runs the whole pipeline with no network at all.
    """
    import research  # noqa: PLC0415  (keeps --table-only free of them)
    import turns as t  # noqa: PLC0415

    if name in ("agent", "auto"):
        try:
            import claude_agent_sdk  # noqa: F401, PLC0415  (presence check only)
            from adapter import AgentSdkBackend  # noqa: PLC0415

            return t.SdkTurns(
                backend=AgentSdkBackend(build(work_dir, max_usd)),
                work_dir=work_dir,
                on_cost=on_cost,
            )
        except ImportError:
            if name == "agent":
                raise
    if name == "perplexity" or (name == "auto" and research.PerplexityBackend().available()):
        return t.OfflineTurns(backend=research.PerplexityBackend())
    return t.OfflineTurns(backend=research.FixtureBackend(fixture))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--topic", help="the question or subject to research")
    parser.add_argument(
        "--table-only",
        action="store_true",
        help="print the role table and stop, so no SDK is needed",
    )
    parser.add_argument(
        "--backend",
        default="auto",
        choices=["auto", "agent", "perplexity", "fixture"],
        help="which runtime answers the six model turns",
    )
    parser.add_argument("--out", help="work directory (default: work/<slug>)")
    parser.add_argument(
        "--fixture",
        type=Path,
        help="recorded research fixture for --backend fixture (default: fixtures/research.json)",
    )
    parser.add_argument(
        "--brief-file",
        type=Path,
        help="a commissioning brief the planner must follow",
    )
    parser.add_argument("--area", default=None, help="RKC research area for the knowledge bundle")
    parser.add_argument("--max-usd", type=float, default=5.0, help="hard cost ceiling")
    parser.add_argument("--max-iterations", type=int, default=3, help="write and check attempts")
    parser.add_argument(
        "--max-questions", type=int, default=12, help="cap on the planner's question list"
    )
    parser.add_argument("--max-diagrams", type=int, default=4, help="cap on the figure list")
    parser.add_argument(
        "--max-claims", type=int, default=24, help="cap on how many claims get a second opinion"
    )
    parser.add_argument("--publish", action="store_true", help="push the paper to a private gist")
    parser.add_argument("--fresh", action="store_true", help="delete the work directory first")
    args = parser.parse_args(argv)

    print(roleplan.table(cast(None)))
    if args.table_only:
        return 0
    if not args.topic:
        parser.error("--topic is required unless you pass --table-only")

    import shutil  # noqa: PLC0415  (nothing above --table-only needs these)

    import paper  # noqa: PLC0415
    from turns import slugify  # noqa: PLC0415

    slug = slugify(args.topic)
    work = Path(args.out) if args.out else FOLDER / "work" / slug
    if args.fresh:
        shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True, exist_ok=True)
    brief = ""
    if args.brief_file:
        try:
            brief = args.brief_file.read_text(encoding="utf-8").strip()
        except OSError as exc:
            parser.error(f"could not read --brief-file {args.brief_file}: {exc}")

    state = paper.State.load_or_new(work, args.topic)
    run = paper.Run(
        topic=args.topic,
        work_dir=work,
        # The lambda is not redundant. `run` does not exist yet, so the cost
        # callback has to close over the name and resolve it when it fires.
        turns=pick_turns(
            args.backend,
            work,
            args.max_usd,
            lambda usd: run.spend(usd),
            args.fixture or FIXTURE,
        ),  # noqa: PLW0108
        state=state,
        area=args.area or paper.DEFAULT_AREA,
        max_usd=args.max_usd,
        max_iterations=args.max_iterations,
        max_questions=args.max_questions,
        max_diagrams=args.max_diagrams,
        max_claims=args.max_claims,
        brief=brief,
        should_publish=args.publish,
        enforce_research_policy=True,
    )

    print()
    print(f"topic:   {args.topic}")
    print(f"work:    {work}")
    print(f"turns:   {type(run.turns).__name__}")
    print()
    try:
        result = paper.run_paper(run)
    except paper.diagrams.ImageBackendUnavailable as exc:
        print()
        print(f"image backend unavailable: {exc}")
        return exc.exit_code
    except paper.RunFailed as exc:
        print()
        print(f"escalated: {exc}")
        return 1

    print()
    print(result["report"])
    print()
    print(f"paper:   {result['paper']}")
    print(
        f"spent:   ${result['usd']:.4f} over {result['turns']} turns, {result['iterations']} attempts"
    )
    print(f"know:    {json.dumps(result['knowledge'])}  valid={result['knowledge_valid']}")
    if result["gist"]:
        print(f"gist:    {result['gist']['url']}")
    print(f"gate:    {result['gate']}")
    print(f"reason:  {result['reason']}")
    return 0 if result["gate"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
