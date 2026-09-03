#!/usr/bin/env python3
"""Lab 3. Deep research over MCP, on the Claude Agent SDK.

A topic in, an evidence-backed white paper out. The same graph as the other
three loops on a different object, which is the point: swap the object, keep
the graph.

    outline    two-level outline, judged, then stamped
    research   ask the boundary, inside a budget
    verify     ask again, independently, and record where the two disagree
    diagram    draw the figures and render them
    write      unpack verified claims into sections
    check      grounding, citations, figures, length, and style, deterministically
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

PROFILES = {
    "demo": {
        "max_questions": 12,
        "max_diagrams": 4,
        "max_claims": 40,
        "max_usd": 12.0,
        "max_iterations": 3,
        "word_target_total": 2000,
    },
    "paper": {
        "max_questions": 20,
        "max_diagrams": 4,
        "max_claims": 60,
        "max_usd": 40.0,
        "max_iterations": 3,
        "word_target_total": 4000,
    },
    "whitepaper": {
        "max_questions": 32,
        "max_diagrams": 6,
        "max_claims": 100,
        "max_usd": 80.0,
        "max_iterations": 3,
        "word_target_total": 6000,
    },
}


def cast(contract=None) -> dict[str, roleplan.RolePlan]:
    """The roles this loop runs.

    Read from `roleplan.py`, never restated here. A port that writes its own
    scopes is a port that drifts from the loop it claims to be, and it drifts
    silently.
    """
    return roleplan.plan(contract, LOOP)


def build(work_dir, max_usd=None, brains=None):
    """This runtime's configuration for the cast.

    Needs `claude-agent-sdk` installed. `cast()` and the role table do not,
    which is why the tests check the separation with no SDK present.
    """
    import roles as sdk  # noqa: PLC0415  (keeps --table-only free of the SDK)

    return sdk.options_for(work_dir, max_usd=max_usd, loop=LOOP, brains=brains)


def pick_turns(
    name: str,
    work_dir: Path,
    max_usd: float | None,
    on_cost,
    fixture: Path = FIXTURE,
    brains=None,
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
                backend=AgentSdkBackend(build(work_dir, max_usd, brains=brains)),
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
    parser.add_argument(
        "--profile",
        choices=sorted(PROFILES),
        default="demo",
        help="demo is the 2000-word paper; paper is 4000; whitepaper is 6000",
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
        help="a commissioning brief the outliner must follow",
    )
    parser.add_argument("--area", default=None, help="RKC research area for the knowledge bundle")
    parser.add_argument("--max-usd", type=float, default=None, help="hard cost ceiling")
    parser.add_argument("--max-iterations", type=int, default=None, help="write and check attempts")
    parser.add_argument(
        "--max-questions", type=int, default=None, help="cap on the outliner's question list"
    )
    parser.add_argument("--max-diagrams", type=int, default=None, help="cap on the figure list")
    parser.add_argument(
        "--max-claims", type=int, default=None, help="cap on how many claims get a second opinion"
    )
    parser.add_argument(
        "--word-target",
        type=int,
        default=None,
        help="paper word_target_total passed to the outliner",
    )
    parser.add_argument(
        "--approve",
        action="store_true",
        help="stop after the outline judge for a human to edit outline.json, exit 3",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="continue from an approved or judged outline; re-judge if outline.json changed",
    )
    parser.add_argument(
        "--enforce-loop-doctrine",
        action="store_true",
        help="require the paper to teach done, then cost, then max turns. E2E only.",
    )
    parser.add_argument(
        "--brain",
        action="append",
        type=Path,
        dest="brains",
        help="corpus root (repeatable). Default: sibling loop_eng_2nd_brain/knowledge",
    )
    parser.add_argument(
        "--corpus-subjects",
        default=None,
        help="comma-separated subject globs, e.g. seminar-*,harness-ch03",
    )
    parser.add_argument("--publish", action="store_true", help="push the paper to a private gist")
    parser.add_argument("--fresh", action="store_true", help="delete the work directory first")
    args = parser.parse_args(argv)

    print(roleplan.table(cast(None)))
    if args.table_only:
        return 0
    if not args.topic:
        parser.error("--topic is required unless you pass --table-only")

    import os  # noqa: PLC0415
    import shutil  # noqa: PLC0415  (nothing above --table-only needs these)

    import corpus as corpus_mod  # noqa: PLC0415
    import paper  # noqa: PLC0415
    from turns import slugify  # noqa: PLC0415

    slug = slugify(args.topic)
    work = Path(args.out) if args.out else FOLDER / "work" / slug
    if args.fresh and not args.resume:
        shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True, exist_ok=True)
    brief = ""
    if args.brief_file:
        try:
            brief = args.brief_file.read_text(encoding="utf-8").strip()
        except OSError as exc:
            parser.error(f"could not read --brief-file {args.brief_file}: {exc}")

    profile = dict(PROFILES[args.profile])
    if args.max_usd is not None:
        profile["max_usd"] = args.max_usd
    if args.max_iterations is not None:
        profile["max_iterations"] = args.max_iterations
    if args.max_questions is not None:
        profile["max_questions"] = args.max_questions
    if args.max_diagrams is not None:
        profile["max_diagrams"] = args.max_diagrams
    if args.max_claims is not None:
        profile["max_claims"] = args.max_claims
    if args.word_target is not None:
        profile["word_target_total"] = args.word_target

    brains = corpus_mod.default_roots(
        extra=args.brains,
        env=os.environ.get("RESEARCH_BRAINS"),
    )
    subjects = None
    if args.corpus_subjects:
        subjects = [item.strip() for item in args.corpus_subjects.split(",") if item.strip()]

    state = paper.State.load_or_new(work, args.topic)
    run = paper.Run(
        topic=args.topic,
        work_dir=work,
        # The lambda is not redundant. `run` does not exist yet, so the cost
        # callback has to close over the name and resolve it when it fires.
        turns=pick_turns(
            args.backend,
            work,
            profile["max_usd"],
            lambda usd: run.spend(usd),
            args.fixture or FIXTURE,
            brains=brains,
        ),  # noqa: PLW0108
        state=state,
        area=args.area or paper.DEFAULT_AREA,
        max_usd=profile["max_usd"],
        max_iterations=profile["max_iterations"],
        max_questions=profile["max_questions"],
        max_diagrams=profile["max_diagrams"],
        max_claims=profile["max_claims"],
        word_target_total=profile["word_target_total"],
        brief=brief,
        should_publish=args.publish,
        require_approval=args.approve,
        resume=args.resume,
        enforce_research_policy=True,
        enforce_loop_doctrine=args.enforce_loop_doctrine,
        brain=brains[0] if brains else None,
        brains=brains,
        corpus_subjects=subjects,
    )

    print()
    print(f"topic:   {args.topic}")
    print(f"work:    {work}")
    print(f"turns:   {type(run.turns).__name__}")
    print(f"profile: {args.profile}")
    print(
        f"budget:  {profile['word_target_total']} words, "
        f"{profile['max_questions']} questions, "
        f"{profile['max_claims']} verified claims, "
        f"${profile['max_usd']:.2f}, "
        f"{profile['max_iterations']} iterations"
    )
    print()
    try:
        result = paper.run_paper(run)
    except paper.AwaitingApproval as exc:
        print()
        print(f"outline ready for approval: {exc.path}")
        print("edit outline.json if needed, then re-run with --resume")
        return exc.exit_code
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
