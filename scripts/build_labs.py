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
import textwrap
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LABS = ROOT / "labs"
SOLUTIONS = ROOT / "solutions"

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

# One solution folder per tool. Claude Code is the base folder, so `sol1_enhancer`
# is the Claude Code answer and the other three carry a suffix. The code in all
# four is the same, because the tool you drive does not change the answer. What
# changes is the spec that tells you how to drive it.
VARIANTS = {
    "claude-code": "",
    "codex": "_codex",
    "grok-build": "_grok_build",
    "opencode": "_opencode",
}

# The two runtime ports. Unlike the four tools above, these are different code:
# the loop is the same, and the way the runtime keeps a role out of a path is
# not. Both read the cast from `solutions/roleplan.py`, so neither can invent a
# role or widen a scope.
#
# The shared `solutions.agent_sdk` / `solutions.deep_agents` packages were
# removed. Each remaining port carries a local `roles.py`. These keys only
# matter if a lab is added back to LABS_SPEC.
RUNTIMES = {
    "agent_sdk": {
        "name": "Claude Agent SDK",
        "module": "solutions.agent_sdk",
        "alias": "sdk",
        "call": "sdk.options_for(contract, loop=LOOP)",
        "enforces": (
            "The Agent SDK scopes in two places and you need both. `tools=[...]` "
            "decides whether a role can write at all. A `PreToolUse` hook decides "
            "which paths it may write. The judge holds neither Edit nor Write, so "
            "there is nothing left for a hook to guard."
        ),
        "package": "claude-agent-sdk",
    },
    "deep_agents": {
        "name": "LangChain Deep Agents",
        "module": "solutions.deep_agents",
        "alias": "deep",
        "call": "deep.subagents_for(contract, loop=LOOP)",
        "enforces": (
            "Deep Agents scopes by handing each subagent its own tool list. A "
            "subagent can only call what it was given. Path scope moves inside the "
            "write tool, which checks the scope before it touches the disk."
        ),
        "package": "deepagents",
    },
}

# Reach the root spine from inside a solution folder, exactly as a lab does.
SOLUTION_TASKFILE = """# Reach the root spine from inside a solution. `task test` works here.
version: '3'
includes:
  root:
    taskfile: ../../Taskfile.yml
    dir: ../..
    flatten: true
"""


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

    @property
    def sol_slug(self) -> str:
        """`lab1_enhancer` becomes `sol1_enhancer`. One source, two trees."""
        return self.slug.replace("lab", "sol", 1)

    @property
    def loop_key(self) -> str:
        """`lab1_enhancer` becomes `enhancer`, which is the key in `roleplan.LOOPS`."""
        return self.slug.split("_", 1)[1]

    @property
    def needs_repo(self) -> bool:
        """Research runs against a question. The other three need a target repo."""
        return self.loop_key != "research"


ROLE_CASTS = {
    "enhancer": ("orchestrator", "doer", "judge"),
    "implementer": (
        "orchestrator",
        "planner",
        "test_implementer",
        "code_implementer",
        "judge",
    ),
    "research": ("orchestrator", "researcher", "writer", "judge"),
    "fixer": ("orchestrator", "code_implementer", "judge"),
}

LABS_SPEC = [
    # All four labs are hand-maintained now, not generated. Each lab/solution
    # folder is standalone (own copies of the shared modules it needs, no
    # `includes:` Taskfile block reaching into the repo root), which this
    # generator's shared-import template does not produce. Re-add a Lab(...)
    # entry for a module only if it goes back to being a generated,
    # shared-import Python stub.
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

In this loop, {lab.roles}.

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

- Fill only `{lab.stub_file}`. Do not edit anything under `solutions/`.
- Do not edit the target repo's tests to make something pass.
- Stop at the documented exit. Do not add a fourth one.
- If you stall, read {lab.solution}. It is the answer, not a hint.

## Worth reading

{reading}
"""


def spec_for(lab: Lab, tool_key: str) -> str:
    """The step-by-step build for one lab, driven by one tool.

    The answer code is the same for all four tools. This is the part that
    differs, so it is the part each solution folder carries.
    """
    name, headless, binary = TOOLS[tool_key]
    folder = f"{lab.sol_slug}{VARIANTS[tool_key]}"

    step = 3  # steps 1 and 2 are fixed
    fill_steps = []
    for item in lab.fills:
        fill_steps.append(
            f"{step}. Fill `{item}`. The docstring in the stub says what it must decide."
        )
        step += 1
    exits = "\n".join(f"   - {item}" for item in lab.exit_when)
    verify = "\n".join(f"   {line}" for line in lab.verify)
    reading = "\n".join(f"- `{item}`" for item in lab.reading)
    fills_md = "\n".join(fill_steps)

    return f"""# Spec. Lab {lab.module}. {lab.title}, with {name}

{lab.one_line}

**Artifact: {lab.artifact} About {lab.minutes} minutes.**

This folder holds the finished answer. `{lab.stub_file}` here runs as it stands.
The stub you start from is `labs/{lab.slug}/{lab.stub_file}`, and the prompt that
drives {name} is `labs/{lab.slug}/prompts/{tool_key}.md`.

## Build it step by step

1. Work from the lab folder, not from this one.

   ```bash
   cd labs/{lab.slug}
   ```

2. Drive {name} with the lab's prompt, or fill `{lab.stub_file}` by hand.

   ```bash
   {headless}
   ```

   Interactive: run `{binary}` in the lab folder and paste everything below the
   line in the prompt file.

{fills_md}
{step}. Stop at one of three exits. Do not add a fourth.

{exits}

{step + 1}. Verify.

   ```bash
{verify}
   ```

{step + 2}. Compare your answer against this folder.

   ```bash
   diff {lab.stub_file} ../../solutions/{folder}/{lab.stub_file}
   ```

## The roles

In this loop, {lab.roles}.

Write scope is not advice. It is declared in `.loop.yml` in the target repo and
enforced at the tool boundary. The code implementer cannot weaken a test to
reach green, because it holds no write path to one.

## The gate

{lab.gate_note}

## The reference

{lab.solution}

## Worth reading

{reading}

## Run the finished answer

```bash
cd solutions/{folder}
task test
```
"""


def port_for(lab: Lab, runtime_key: str) -> str:
    """The runtime port for one lab. Configuration, not a second loop."""
    rt = RUNTIMES[runtime_key]
    enforces = textwrap.fill(rt["enforces"], width=79)
    if lab.needs_repo:
        repo_arg = '    parser.add_argument("--repo", default="../../work/northwind-field-crm")\n'
        contract_expr = "Contract(args.repo)"
        contract_import = "\nfrom contract import Contract"
    else:
        # The research loop runs against a question, not a repo. There is no
        # `.loop.yml` to read, so the cast falls back to the table's own scopes.
        repo_arg = ""
        contract_expr = "None"
        contract_import = ""

    return f'''#!/usr/bin/env python3
"""Lab {lab.module}. {lab.title}, on {rt["name"]}.

The loop does not change. The rubric, the gates, and the exits are the same
objects lab {lab.module} uses. What changes is how the runtime says "this role
may not write that file".

{enforces}

    python {lab.stub_file} --table-only

Nothing here calls a model. This module returns configuration, and your driver
is what runs it.
"""

from __future__ import annotations

import argparse

import _root  # noqa: F401  (puts the repo root on sys.path)
{contract_import}
from solutions import roleplan
from {rt["module"]} import roles as {rt["alias"]}

LOOP = "{lab.loop_key}"


def cast(contract) -> dict[str, roleplan.RolePlan]:
    """The roles this loop runs.

    Read from `solutions/roleplan.py`, never restated here. A port that writes
    its own scopes is a port that drifts from the loop it claims to be, and it
    drifts silently.
    """
    return roleplan.plan(contract, LOOP)


def build(contract):
    """This runtime's configuration for the cast.

    Needs `{rt["package"]}` installed. `cast()` and the role table do not, which
    is why the tests can check the separation without either SDK present.
    """
    return {rt["call"]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
{repo_arg}    parser.add_argument(
        "--table-only",
        action="store_true",
        help="print the role table and stop, so no SDK is needed",
    )
    args = parser.parse_args(argv)

    contract = {contract_expr}
    print(roleplan.table(cast(contract)))
    if args.table_only:
        return 0
    print()
    print(build(contract))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def port_spec_for(lab: Lab, runtime_key: str) -> str:
    """The step-by-step build for one runtime port."""
    rt = RUNTIMES[runtime_key]
    enforces = textwrap.fill(rt["enforces"], width=79)
    folder = f"{lab.sol_slug}_{runtime_key}"
    repo_flag = " --repo ../../work/northwind-field-crm" if lab.needs_repo else ""
    role_lines = "\n".join(f"- `{name}`" for name in ROLE_CASTS[lab.loop_key])

    return f"""# Spec. Lab {lab.module}. {lab.title}, on {rt["name"]}

The same loop, in a different runtime. The point is not that it runs. The point
is that the rubric, the red gate, the write scope, and the exits did not have to
change to make it run.

## The cast for this loop

{role_lines}

`solutions/roleplan.py` is where that list lives. Read it there. Do not restate
a scope in this folder.

## How this runtime enforces scope

{enforces}

## Build it step by step

1. Install the runtime.

   ```bash
   pip install -r requirements-takehome.txt
   ```

2. Read the cast before you configure anything.

   ```bash
   cd solutions/{folder}
   python {lab.stub_file} --table-only{repo_flag}
   ```

   The judge must print `no` in the writes column. If it prints `yes`, stop.
   Nothing downstream is worth building on that.

3. Translate the cast into this runtime, one role at a time. `cast(contract)`
   returns a `RolePlan` per role, carrying the tools, the allow list, and the
   deny list. `build(contract)` turns those into the runtime's own objects.

4. Give the writing roles their path check. A role holding `Edit` or `Write`
   without a path check can reach any file in the repo, and the first thing an
   agent under pressure reaches for is the failing test.

5. Print the configuration and read it.

   ```bash
   python {lab.stub_file}{repo_flag}
   ```

## Verify

```bash
task test
```

Those checks need no SDK and no key. They run this folder's own tests.

## What this folder is not

A shared engine. Copy this folder somewhere else and it runs. If a port
imports a library to do that, the design leaked.
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

Stop typing and watch. Then copy the answer into this folder:

```bash
cp ../../solutions/{lab.sol_slug}/{lab.stub_file} .
```

You continue the next module with a working artifact. See `FALL-BEHIND.md`.
"""


def fall_behind_for(lab: Lab) -> str:
    return f"""# If you fall behind

Nobody is graded here. Falling behind on one lab must not cost you the next one.

## Do this

1. Stop typing and watch Rick finish the build.
2. Save your attempt. The next step overwrites it.

   ```bash
   cp {lab.stub_file} {lab.stub_file}.my-attempt
   ```

3. Copy the answer in.

   ```bash
   cp ../../solutions/{lab.sol_slug}/{lab.stub_file} .
   ```

4. You now have a working {lab.title.lower()}. Continue with the next module.

## What you get

{lab.artifact}

## Read what you copied

`solutions/{lab.sol_slug}/SPEC.md` is the step-by-step build for this lab. The same
answer sits in `solutions/{lab.sol_slug}_codex`, `_grok_build`, and `_opencode`, one
per tool, each with the spec written for that tool.

## Coming back later

Put the empty stub back and try again:

```bash
git checkout -- {lab.stub_file}
```

That restores this one file. Everything you need is in `prompts/`, and
`{lab.solution}` is the reference the answer calls.
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

Stop and copy the answer in:

```bash
cp ../../solutions/{lab.sol_slug}/{lab.stub_file} .
```

See [FALL-BEHIND.md](FALL-BEHIND.md).

## Something is genuinely broken

Tell Rick. A fresh clone plus `task setup` plus `task test` should be green, and
anything else is a real bug.
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
        for stale in ("langgraph.md",):
            (folder / "prompts" / stale).unlink(missing_ok=True)

    # The solution tree. One folder per lab per tool, always filled in. The
    # `--solved` switch controls the labs only, because a solution that is a
    # stub is not a solution.
    solutions = 0
    for lab in LABS_SPEC:
        for tool_key, suffix in VARIANTS.items():
            folder = SOLUTIONS / f"{lab.sol_slug}{suffix}"
            folder.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(LABS / "_root.py", folder / "_root.py")
            write(folder / lab.stub_file, lab.solved_body)
            write(folder / "SPEC.md", spec_for(lab, tool_key))
            write(folder / "Taskfile.yml", SOLUTION_TASKFILE)
            solutions += 4

    # The runtime ports. Different code, not a different prompt, so they get
    # their own writer.
    ports = 0
    for lab in LABS_SPEC:
        for runtime_key in RUNTIMES:
            folder = SOLUTIONS / f"{lab.sol_slug}_{runtime_key}"
            folder.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(LABS / "_root.py", folder / "_root.py")
            write(folder / lab.stub_file, port_for(lab, runtime_key))
            write(folder / "SPEC.md", port_spec_for(lab, runtime_key))
            write(folder / "Taskfile.yml", SOLUTION_TASKFILE)
            ports += 4

    filled = args.solved if args.solved else ("all" if args.solved is not None else "none")
    print(f"wrote {written} files across {len(LABS_SPEC)} labs (solved: {filled})")
    print(f"wrote {solutions} files across {len(LABS_SPEC) * len(VARIANTS)} solutions")
    print(f"wrote {ports} files across {len(LABS_SPEC) * len(RUNTIMES)} runtime ports")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
