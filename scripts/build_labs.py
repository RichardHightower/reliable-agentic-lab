#!/usr/bin/env python3
"""Generate the lab tree from one description per module.

Sixteen prompt files, four stubs, and four sets of docs all say the same things
in the same order. Writing them by hand guarantees they drift apart by Saturday.
This script is the single source, and re-running it is how a change to one lab
reaches all four tools.

    python scripts/build_labs.py
"""

from __future__ import annotations

import argparse
import shutil
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LABS = ROOT / "labs"

TOOLS = {
    "claude-code": (
        "Claude Code",
        'claude -p "$(cat prompts/claude-code.md)" --allowedTools "Read,Edit,Write,Bash,Glob,Grep"',
        "claude",
    ),
    "codex": ("Codex", 'codex exec "$(cat prompts/codex.md)"', "codex"),
    "grok-build": ("Grok Build", 'grok -p "$(cat prompts/grok-build.md)" --no-auto-update', "grok"),
    "opencode": ("OpenCode", 'opencode run "$(cat prompts/opencode.md)"', "opencode"),
}


@dataclass
class Lab:
    slug: str
    module: int
    title: str
    minutes: int
    artifact: str
    one_line: str
    stub_file: str
    fills: list[str]
    roles: str
    exit_when: list[str]
    verify: list[str]
    gate_note: str
    solution: str
    stub_body: str
    solved_body: str = ""
    reading: list[str] = field(default_factory=list)


LABS_SPEC = [
    Lab(
        slug="m1-enhancer",
        module=1,
        title="Ticket Enhancer",
        minutes=25,
        artifact="A working autonomous loop, running on your machine.",
        one_line="A vague ticket in, a ready contract out.",
        stub_file="loop.py",
        fills=["judge_ticket(ticket)", "decide_next(verdict, iteration, previous)"],
        roles=(
            "orchestrator owns the budget and the exits, a doer edits the ticket body "
            "and nothing else, and a judge scores the ticket against criteria for its kind"
        ),
        exit_when=[
            "the ticket is ready",
            "the budget is spent",
            "two rounds in a row find exactly the same gaps, which means the human "
            "has not acted and another round will not help",
        ],
        verify=["task loop:enhancer -- --ticket T001"],
        gate_note=(
            "This lab writes no code, so the push gate does not fire. You meet it in "
            "Module 2."
        ),
        solution="loops/enhancer.py and loops/criteria.py",
        stub_body='''"""Lab 1. The Ticket Enhancer.

Fill the two functions below. Everything else is written.

Read `loops/criteria.py` only if you stall. It is the answer.
"""

from __future__ import annotations

import _root  # noqa: F401  (puts the repo root on sys.path)

from loops import criteria, gates
from loops.ticket import Ticket


def judge_ticket(ticket: Ticket) -> criteria.Verdict:
    """Score one ticket. Return a Verdict.

    A judge holds no write tools. Read the ticket, decide, and report.

    Decide three things:
      1. What kind of ticket is this? Bug, feature, or user interface.
      2. Which required parts are missing for that kind?
      3. Is it ready?

    A user-interface ticket needs a wireframe. One acceptance criterion is not
    acceptance criteria.
    """
    raise NotImplementedError("fill me in")


def decide_next(
    verdict: criteria.Verdict,
    iteration: int,
    previous: tuple[str, ...] | None,
    budget: int = 3,
) -> gates.Decision:
    """Choose the next move: pass, retry, or escalate.

    There is no fourth exit. The one people miss is stable failure: when this
    round finds exactly the same gaps as the last one, another round changes
    nothing, so stop rather than spending the budget.
    """
    raise NotImplementedError("fill me in")
''',
        reading=["loops/criteria.py", "loops/gates.py", "loops/ticket.py"],
        solved_body='''"""Lab 1. The Ticket Enhancer. Filled in.

This is the `done-m1` answer. Each function hands the work to the reference
implementation, because that is where the lesson lives and duplicating it here
would let the two drift apart.

Read `loops/criteria.py` to see how the judge decides.
"""

from __future__ import annotations

import _root  # noqa: F401  (puts the repo root on sys.path)

from loops import criteria, gates
from loops.ticket import Ticket


def judge_ticket(ticket: Ticket) -> criteria.Verdict:
    """Score one ticket. Return a Verdict.

    `criteria.judge` classifies the ticket, looks up the parts that kind of
    ticket needs, and reports what is missing. It writes nothing.
    """
    return criteria.judge(ticket)


def decide_next(
    verdict: criteria.Verdict,
    iteration: int,
    previous: tuple[str, ...] | None,
    budget: int = 3,
) -> gates.Decision:
    """Choose the next move: pass, retry, or escalate.

    The signature is what is missing, not how it was worded. Two equal
    signatures mean the last round changed nothing, so the gate escalates
    rather than spending the rest of the budget on an identical failure.
    """
    return gates.decide(
        passed=verdict.ready,
        iteration=iteration,
        budget=budget,
        signature=verdict.signature(),
        previous_signature=previous,
    )
''',
    ),
    Lab(
        slug="m2-implementer",
        module=2,
        title="Ticket Implementer and the harness",
        minutes=25,
        artifact="A reusable evaluation harness that plans, executes, verifies, and iterates.",
        one_line="A ready ticket in, a green rubric out. This is the centre of the workshop.",
        stub_file="harness.py",
        fills=["red_gate(before, after)", "score_attempt(...)", "run_loop(...)"],
        roles=(
            "orchestrator writes nothing, a test implementer owns tests/ only, a code "
            "implementer owns app/ and is denied tests/, and a judge holds no write path at all"
        ),
        exit_when=[
            "every rubric row passes",
            "the same rows fail twice",
            "the iteration or money budget is spent",
        ],
        verify=[
            "task loop:implementer -- --ticket T001 --doer reference",
            "task loop:implementer -- --ticket T001 --doer none",
        ],
        gate_note=(
            "You will hit the push gate in this lab. Your agent will try to push and be "
            "refused until `task test` is green. Read the refusal. It is the lesson."
        ),
        solution="loops/implementer.py, loops/rubric.py, and loops/gates.py",
        stub_body='''"""Lab 2. The harness. The centre of the workshop.

Fill the three functions below.

The order is fixed and it is the whole point:

    tests first  ->  prove them red  ->  code until green  ->  judge  ->  gate

Read `loops/implementer.py` only if you stall.
"""

from __future__ import annotations

import _root  # noqa: F401  (puts the repo root on sys.path)

from loops import gates, rubric
from loops.contract import Contract, RunResult


def red_gate(before: RunResult, after: RunResult) -> set[str]:
    """Return the test ids that are failing now and did not exist before.

    This is the proof that the new tests test something. A test that passes
    before any code is written proves nothing, so an empty result must stop the
    loop rather than let it continue.
    """
    raise NotImplementedError("fill me in")


def score_attempt(contract: Contract, **evidence) -> rubric.Score:
    """Score one attempt against the ten rubric rows.

    Every row is computed from junit.xml, coverage.xml, exit codes, steps.jsonl,
    and the diff. No model call, so no model can be talked into a pass.

    "The tests passed" is one row of ten.
    """
    raise NotImplementedError("fill me in")


def run_loop(contract: Contract, budget: int = 3) -> dict:
    """Run the harness until it passes, stalls, or runs out of budget.

    Hold the loop in Python. The model does not get to count its own retries.
    """
    raise NotImplementedError("fill me in")
''',
        reading=["loops/rubric.py", "loops/gates.py", "loops/roles.py", "loops/steps.py"],
        solved_body='''"""Lab 2. The harness. Filled in.

This is the `done-m2` answer. The order is the lesson:

    tests first  ->  prove them red  ->  code until green  ->  judge  ->  gate

Read `loops/implementer.py` for the full run, and `loops/rubric.py` for the
ten rows.
"""

from __future__ import annotations

import _root  # noqa: F401  (puts the repo root on sys.path)

from loops import gates, implementer, rubric
from loops.contract import Contract, RunResult


def red_gate(before: RunResult, after: RunResult) -> set[str]:
    """Return the test ids that are failing now and did not exist before.

    An empty result is not a small problem. It means the new tests passed
    against code that was never written, so they prove nothing and the loop
    must stop rather than continue to the code implementer.
    """
    seen = before.junit.passed_ids | before.junit.failed_ids
    return implementer._new_test_ids(seen, after.junit.failed_ids)


def score_attempt(contract: Contract, **evidence) -> rubric.Score:
    """Score one attempt against the ten rubric rows.

    Every argument left out becomes a failing row. Absent evidence is never a
    pass, which is why this forwards the keywords instead of filling defaults.
    """
    return rubric.score(contract=contract, **evidence)


def run_loop(contract: Contract, budget: int = 3, ticket_id: str = "T001") -> dict:
    """Run the harness until it passes, stalls, or runs out of budget.

    Python holds the loop. `implementer.run` plans, writes the tests, checks
    the red gate, writes the code, scores, and asks the gate what to do next.
    """
    return implementer.run(
        repo=contract.repo,
        ticket_id=ticket_id,
        budget=budget,
        doer="reference",
    )


def decide(score: rubric.Score, iteration: int, previous=None, budget: int = 3) -> gates.Decision:
    """The gate. Kept here so the three exits stay visible in this file."""
    return gates.decide(
        passed=score.passed,
        iteration=iteration,
        budget=budget,
        signature=score.signature(),
        previous_signature=previous,
    )
''',
    ),
    Lab(
        slug="m3-research",
        module=3,
        title="Research Assistant over MCP",
        minutes=25,
        artifact="A working research assistant that cites what it retrieved.",
        one_line="A question in, a cited brief out. Same graph, different object.",
        stub_file="loop.py",
        fills=["plan_questions(question)", "check_brief(body, sources)"],
        roles=(
            "orchestrator owns the budget, a researcher calls the tool boundary, a writer "
            "assembles the brief, and a judge checks grounding and style without a model"
        ),
        exit_when=[
            "the brief is grounded and clean",
            "the search budget is spent",
            "no source could be found, which escalates rather than shipping an uncited brief",
        ],
        verify=[
            'task loop:research -- --question "sqlalchemy nullable datetime column" --backend fixture'
        ],
        gate_note=(
            "The boundary is the lesson. This loop can search and write into its own "
            "output folder. It cannot merge, deploy, or touch the repo."
        ),
        solution="loops/researcher.py, loops/research.py, and loops/brief.py",
        stub_body='''"""Lab 3. The research assistant.

Fill the two functions below.

Perplexity is optional. If you have no key, pass `--backend websearch` and use
your agent's own search tool, or `--backend fixture` to run offline. The loop
does not know which one it is holding.

Read `loops/researcher.py` and `loops/brief.py` only if you stall.
"""

from __future__ import annotations

import _root  # noqa: F401  (puts the repo root on sys.path)

from loops import brief


def plan_questions(question: str) -> list[str]:
    """Break one question into the sub-questions a brief needs.

    A plan step you cannot check is a wish. Each sub-question should be one you
    can tell was answered or not.
    """
    raise NotImplementedError("fill me in")


def check_brief(body: str, sources: list[str]) -> brief.BriefScore:
    """Check the brief without asking a model.

    Two things are arithmetic, not judgement:

      grounded  every citation marker resolves to a source actually retrieved
      cited     every claim paragraph carries a citation

    A confident sentence nobody can trace is the failure that matters.
    """
    raise NotImplementedError("fill me in")
''',
        reading=["loops/brief.py", "loops/research.py", "MCP.md"],
        solved_body='''"""Lab 3. The research assistant. Filled in.

This is the `done-m3` answer.

The backend does not appear anywhere in this file. That is the point of a tool
boundary: the loop calls one function and never learns whether Perplexity, the
built-in WebSearch tool, or a recorded fixture answered it.
"""

from __future__ import annotations

import _root  # noqa: F401  (puts the repo root on sys.path)

from loops import brief, researcher


def plan_questions(question: str) -> list[str]:
    """Break one question into the sub-questions a brief needs.

    Each sub-question is one you can tell was answered or not. A plan step you
    cannot check is a wish.
    """
    return researcher.plan_questions(question)


def check_brief(body: str, sources: list[str]) -> brief.BriefScore:
    """Check the brief without asking a model.

    `brief.check` resolves every citation marker against the sources actually
    retrieved, and finds every claim paragraph that carries no citation. Both
    are arithmetic. A confident sentence nobody can trace is the failure that
    matters, and a model judge is the wrong tool for catching it.
    """
    return brief.check(body, sources)
''',
    ),
    Lab(
        slug="m4-fixer",
        module=4,
        title="Broken PR Fixer, unattended",
        minutes=18,
        artifact="A production-ready architecture you can hand to your engineering org.",
        one_line="A failing branch in, a green one out, or an honest explanation of why not.",
        stub_file="loop.py",
        fills=["summarize_failure(run_result)", "repair_until_green(contract, budget)"],
        roles=(
            "orchestrator owns the budget, a code implementer repairs inside its scope, "
            "and a judge reads the suite"
        ),
        exit_when=[
            "the suite is green",
            "the same tests fail twice",
            "the budget is spent, and it leaves a comment saying why",
        ],
        verify=["task loop:fixer -- --doer reference"],
        gate_note=(
            "Nobody is watching this one. Its exits matter more than its successes, and "
            "the same gate that blocks your push blocks its push."
        ),
        solution="loops/fixer.py",
        stub_body='''"""Lab 4. The Broken PR Fixer.

Fill the two functions below.

This loop runs unattended. Nobody is watching to stop it, so the exits matter
more than the successes, and giving up silently is the one thing it may not do.

Read `loops/fixer.py` only if you stall.
"""

from __future__ import annotations

import _root  # noqa: F401  (puts the repo root on sys.path)

from loops.contract import Contract, RunResult


def summarize_failure(run_result: RunResult) -> str:
    """Say what is broken, in a few lines a human can act on.

    The orchestrator sees this, not the whole log. Name the failing tests and
    the first real error line.
    """
    raise NotImplementedError("fill me in")


def repair_until_green(contract: Contract, budget: int = 3) -> dict:
    """Repair until the suite is green, or stop and explain.

    Stopping is designed. Stopping without an explanation is a bug: the next
    person to look at this pull request has to know why the agent walked away.
    """
    raise NotImplementedError("fill me in")
''',
        reading=["loops/fixer.py", "loops/gates.py"],
        solved_body='''"""Lab 4. The Broken PR Fixer. Filled in.

This is the `done-m4` answer.

Nobody is watching this loop, so the exits matter more than the successes.
Giving up is allowed. Giving up silently is the bug.
"""

from __future__ import annotations

import _root  # noqa: F401  (puts the repo root on sys.path)

from loops import fixer
from loops.contract import Contract, RunResult


def summarize_failure(run_result: RunResult) -> str:
    """Say what is broken, in a few lines a human can act on.

    The orchestrator reads this, not the whole log. Sending the log would put
    the failure in the middle of a long context, which is where accuracy is
    worst.
    """
    return fixer.failure_summary(run_result)


def repair_until_green(contract: Contract, budget: int = 3) -> dict:
    """Repair until the suite is green, or stop and explain.

    The returned trace carries the gate and the reason. The next person to open
    this pull request has to know why the agent walked away.
    """
    return fixer.run(repo=contract.repo, budget=budget, doer="reference")
''',
    ),
]


def prompt_for(lab: Lab, tool_key: str) -> str:
    name, headless, binary = TOOLS[tool_key]
    fills = "\n".join(f"- `{item}`" for item in lab.fills)
    exits = "\n".join(f"{n}. {item}" for n, item in enumerate(lab.exit_when, 1))
    verify = "\n".join(lab.verify)
    reading = "\n".join(f"- `{item}`" for item in lab.reading)
    return f"""# Prompt for {name}

You do not need {name}. Any of the four tools works. See
[labs/HOW-TO-RUN.md](../../HOW-TO-RUN.md).

Run it from this folder:

```bash
cd labs/{lab.slug}
{headless}
```

Interactive: run `{binary}` here and paste everything below the line.

---

Fill `{lab.stub_file}` in this folder. Fill only that file.

{lab.one_line}

## What to implement

{fills}

## The roles

This loop has {lab.roles}.

Write scope is not advice. It is declared in `.loop.yml` in the target repo and
enforced at the tool boundary. The code implementer cannot weaken a test to
reach green, because it holds no write path to one.

## When the loop stops

There are three exits and no fourth: pass, retry, escalate.

{exits}

## Verify

```bash
{verify}
```

## The gate

{lab.gate_note}

## Rules

- Fill only `{lab.stub_file}`. Do not edit anything under `loops/`.
- Do not edit the target repo's tests to make something pass.
- Stop at the documented exit. Do not add a fourth one.
- If you stall, read {lab.solution}. It is the answer, not a hint.

## Worth reading

{reading}
"""


def readme_for(lab: Lab) -> str:
    exits = "\n".join(f"- {item}" for item in lab.exit_when)
    verify = "\n".join(lab.verify)
    return f"""# Lab {lab.module}. {lab.title}

{lab.one_line}

**{lab.minutes} minutes. Artifact: {lab.artifact}**

## Work from this folder

```bash
cd labs/{lab.slug}
```

Your coding agent runs here, not at the repo root. This folder has its own
`.claude/`, so the tool scope and the skills for this lab apply and nothing
else does.

## Fill one file

`{lab.stub_file}`. Nothing else.

## Start

Pick one tool and paste its prompt.

| Tool | Command |
|---|---|
| Claude Code | `claude -p "$(cat prompts/claude-code.md)"` |
| Codex | `codex exec "$(cat prompts/codex.md)"` |
| Grok Build | `grok -p "$(cat prompts/grok-build.md)"` |
| OpenCode | `opencode run "$(cat prompts/opencode.md)"` |

## Verify

```bash
{verify}
```

## When it stops

{exits}

## The gate

{lab.gate_note}

## If you fall behind

Stop typing and watch. Then:

```bash
git checkout done-m{lab.module}
```

You continue the next module with a working artifact. See `FALL-BEHIND.md`.
"""


def fall_behind_for(lab: Lab) -> str:
    return f"""# If you fall behind

Nobody is graded here. Falling behind on one lab must not cost you the next one.

## Do this

1. Stop typing and watch Rick finish the build.
2. When he is done, run:

   ```bash
   git checkout done-m{lab.module}
   ```

3. You now have a working {lab.title.lower()}. Continue with the next module.

## What you get

{lab.artifact}

## Coming back later

`start-m{lab.module}` is this lab with the stub empty again. Everything you need
is in `prompts/`, and `{lab.solution}` is the answer whenever you want it.
"""


def architecture_for(lab: Lab) -> str:
    reading = "\n".join(f"- `{item}`" for item in lab.reading)
    return f"""# Architecture. Lab {lab.module}

{lab.one_line}

## The shape

Every loop in this workshop is the same three parts. Only the object changes.

```
orchestrator  owns the budget and the exits. Writes nothing.
     |
     +-- doer    writes files inside a declared scope
     |
     +-- judge   scores the result. Holds no write path.
```

For this lab: {lab.roles}.

## Why write scope matters

Scope is declared in `.loop.yml` in the target repo and enforced at the tool
boundary. It is not an instruction in a prompt, because an agent can talk its
way past an instruction and cannot talk its way past a missing tool.

The judge has no `write` method to call. That is why it cannot grade its own
homework.

## The exits

Three, and no fourth: pass, retry, escalate. Python holds the loop, so the model
never counts its own retries.

The exit people forget is stable failure. When this round fails in exactly the
same way as the last one, the loop is not converging, and spending the rest of
the budget to watch it fail identically buys a surprise bill rather than a fix.

## Where the code lives

The answer for this lab is `{lab.solution}`.

Worth reading:

{reading}
"""


def troubleshooting_for(lab: Lab) -> str:
    return f"""# Troubleshooting. Lab {lab.module}

## `ModuleNotFoundError: No module named 'loops'`

Your stub is missing its first import. Every stub starts with:

```python
import _root  # noqa: F401
```

`_root.py` sits in this folder and puts the repo root on `sys.path`. No
PYTHONPATH needed.

## `task: command not found`

Install Task. See [SETUP.md](../../SETUP.md).

## `task test` says no target repo

Run `task clone` from the repo root. The demo repository lands in `work/`.

## Your agent was refused a push

```
BLOCKED by pre-tool hook: git push
```

Working as designed. Run `task test`, get it green, push again. The gate reads
`.harness/receipt.json` and nothing else, and a receipt only counts when the
suite passed against exactly this tree.

## `NotImplementedError: fill me in`

That is the stub. Fill it.

## The loop escalates and you expected a pass

Read the reason it printed. It names the row that failed and why it stopped.
That reading is the skill this workshop is about, not a sign something broke.

## You are out of time

Stop and run `git checkout done-m{lab.module}`. See [FALL-BEHIND.md](FALL-BEHIND.md).

## Something is genuinely broken

Tell Rick. A fresh clone plus `task setup` plus `task test` should be 129 green
checks, and anything else is a real bug.
"""


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--solved",
        nargs="*",
        metavar="SLUG",
        help=(
            "write the filled answer instead of the stub, for these lab slugs. "
            "No slugs means every lab. This is how done-m<n> is built."
        ),
    )
    args = parser.parse_args(argv)
    written = 0
    for lab in LABS_SPEC:
        folder = LABS / lab.slug
        folder.mkdir(parents=True, exist_ok=True)
        # A copy per lab, so a stub imports it with no PYTHONPATH.
        shutil.copyfile(LABS / "_root.py", folder / "_root.py")
        solved = args.solved is not None and (not args.solved or lab.slug in args.solved)
        body = lab.solved_body if solved else lab.stub_body
        write(folder / lab.stub_file, body)
        write(folder / "README.md", readme_for(lab))
        write(folder / "FALL-BEHIND.md", fall_behind_for(lab))
        write(folder / "ARCHITECTURE.md", architecture_for(lab))
        write(folder / "TROUBLESHOOTING.md", troubleshooting_for(lab))
        # One SETUP and one INSTRUCTIONS for all four labs. Four copies drift.
        for stale in ("SETUP.md", "INSTRUCTIONS.md"):
            (folder / stale).unlink(missing_ok=True)
        written += 5
        for tool_key in TOOLS:
            write(folder / "prompts" / f"{tool_key}.md", prompt_for(lab, tool_key))
            written += 1
        for stale in ("agent-sdk.md", "langgraph.md"):
            (folder / "prompts" / stale).unlink(missing_ok=True)
    filled = args.solved if args.solved else ("all" if args.solved is not None else "none")
    print(f"wrote {written} files across {len(LABS_SPEC)} labs (solved: {filled})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
