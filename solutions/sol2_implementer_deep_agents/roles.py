"""The five implementer roles, as LangChain Deep Agents subagents.

Deep Agents scopes three ways, and this port uses all three.

1. Each subagent gets its own tool list. A subagent can only call what it was
   given, so the judge is separated the same way it is in every other runtime:
   it holds no tool that writes.
2. Path scope lives inside the write tool. The code implementer cannot weaken a
   test, because `tests/**` is not in its allow list.
3. The harness itself is fenced: no general-purpose subagent, no built-in
   `write_file` on the orchestrator, `FilesystemBackend(virtual_mode=True)` so
   the built-in tools are *routed* at the repo root (routing, not a security
   boundary — custom tools still call `_inside`), and declarative
   `permissions=` underneath everything.

Layer 3 is the one people skip. The default general-purpose subagent ships with
the harness filesystem tools, and leaving it enabled is how a carefully scoped
agent writes anywhere it likes. `build_agent` turns it off.

(1) and (2) are what the tests pin down with no SDK installed. Python still owns
the red gate and the Pass / Retry / Escalate decision. The model never counts
its own retries.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from roleplan import DEFAULT_LOOP, RolePlan, plan
from write_scope import ScopeViolation, WriteScope

HERE = Path(__file__).resolve().parent
SKILLS_DIR = HERE / "skills"
MEMORY_DIR = HERE / "memory"
MEMORY_FILE = MEMORY_DIR / "AGENTS.md"
DEFAULT_MODEL = "anthropic:claude-sonnet-5"

# Built-in harness tools that write or execute. The orchestrator must not hold
# these. Deep Agents adds them by default unless a harness profile hides them.
# `run_tests` is not among them: running the suite is a different permission
# from editing it, and the orchestrator needs the first one.
ORCHESTRATOR_EXCLUDED_TOOLS = frozenset({"write_file", "edit_file", "delete", "execute"})

# The last rule every role gets. First match wins, so anything not allowed above
# this line lands here.
DENY_EVERY_WRITE = {"operations": ["write"], "paths": ["/**"], "mode": "deny"}


# The judge answers one question and names no gate.
#
# The consumer is the framework, not this folder's Python. From the Deep Agents
# docs: without `response_format` the parent receives the subagent's last
# message text as-is; with it the parent always gets valid JSON matching the
# schema, JSON-serialized into the ToolMessage the parent reads.
#
# `implementer.run` now passes `judge_done` to `gates.decide`. Unparseable is
# done=False. Naming a gate is still the one thing the judge may not do, the
# same reason sol1's schema forbids `ready`: a stop condition a model can
# phrase its way past is not a stop condition.
JUDGE_RESPONSE = {
    "type": "object",
    "title": "JudgeVerdict",
    "description": (
        "Whether the diff does what the ticket asked for. One question, one answer, one sentence "
        "of reason. Do not name a gate. Do not say pass, retry, or escalate. "
        "Do not score the rubric. Python does that."
    ),
    "properties": {
        "done": {"type": "boolean"},
        "why": {"type": "string"},
    },
    "required": ["done", "why"],
    "additionalProperties": False,
}

RESPONSE_FORMATS = {"judge": JUDGE_RESPONSE}


def _skill_path(name: str) -> str | None:
    """The mount path for one role's skill, or None when it has no directory.

    Mount, do not inline. Deep Agents loads a skill in two levels: its metadata
    sits in the system prompt at startup, and its instructions join the context
    only when the skill is invoked. Pasting the whole SKILL.md into
    `system_prompt` as well defeats that, because the body is then always
    resident and the mount saves nothing.
    """
    return f"/skills/{name}/" if (SKILLS_DIR / name).is_dir() else None


def _inside(repo: Path, path: str):
    """Resolve `path` under `repo`, or None when it escapes.

    `virtual_mode` on the Deep Agents backend is routing: built-in filesystem
    tools see paths relative to `root_dir`. It is not a security boundary, and
    it does not fence a tool this folder wrote. Without this check,
    `read_file("../../secrets")` walks straight off the target repo, and the
    harness never sees the call.

    The write scope refuses `..` by glob, which works only while every caller
    spells the escape the same way. Resolving first means the check does not
    depend on how the path was written.
    """
    target = (repo / path).resolve()
    root = Path(repo).resolve()
    return target if target == root or root in target.parents else None


def scoped_write_tool(repo: Path, role: RolePlan):
    """A write tool that refuses a path outside this role's scope."""
    from langchain.tools import tool  # noqa: PLC0415

    scope = WriteScope(allow=list(role.allow), deny=list(role.deny))
    allowed = ", ".join(role.allow) or "nothing"

    @tool(f"write_{role.name}")
    def write(path: str, content: str) -> str:
        """Write a file inside this role's declared scope."""
        try:
            scope.check(path)
        except ScopeViolation:
            return f"REFUSED. {role.name} may write {allowed}. {path} is outside that scope."
        target = _inside(repo, path)
        if target is None:
            return f"REFUSED. {path} is outside the target repo."
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"wrote {path}"

    return write


def read_tool(repo: Path):
    from langchain.tools import tool  # noqa: PLC0415

    @tool
    def read_file(path: str) -> str:
        """Read a file from the target repo."""
        target = _inside(repo, path)
        if target is None:
            return f"REFUSED. {path} is outside the target repo."
        if not target.exists():
            return f"no such file: {path}"
        return target.read_text(encoding="utf-8")

    return read_file


def run_tests_tool(repo: Path):
    """Mechanical. The orchestrator may run tests. It may not edit them."""
    from langchain.tools import tool  # noqa: PLC0415

    @tool
    def run_tests() -> str:
        """Run `task test` in the target repo and return the last 2000 characters."""
        proc = subprocess.run(
            ["task", "test"],
            cwd=repo,
            text=True,
            capture_output=True,
            check=False,
        )
        body = (proc.stdout or "") + (proc.stderr or "")
        return f"exit {proc.returncode}\n{body[-2000:]}"

    return run_tests


def permission_rules(role: RolePlan) -> list[dict]:
    """Declarative filesystem rules for one role. First match wins.

    Plain dicts so the tests can read them with no SDK. `build_agent` turns them
    into `FilesystemPermission` objects.
    """
    if not role.can_write or not role.allow:
        return [DENY_EVERY_WRITE]
    rules: list[dict] = []
    if role.deny:
        # Deny first. A role's own deny list beats its own allow list, the same
        # rule WriteScope enforces, so the two layers cannot disagree.
        rules.append({"operations": ["write"], "paths": _rooted_patterns(role.deny), "mode": "deny"})
    rules.append({"operations": ["write"], "paths": _rooted_patterns(role.allow), "mode": "allow"})
    rules.append(DENY_EVERY_WRITE)
    return rules


def _rooted_patterns(patterns) -> list[str]:
    """Normalize readable role patterns for the current Deep Agents SDK."""
    return [pattern if pattern.startswith("/") else "/" + pattern for pattern in patterns]


def subagents_for(
    contract, loop: str = DEFAULT_LOOP, *, cwd: Path | str | None = None
) -> list[dict]:
    """One Deep Agents subagent per role in this loop's cast, with its own tools.

    #543 follow-up. This is where a subagent's actual write and read tools
    are built (`scoped_write_tool`, `read_tool`), independently of the
    orchestrator's own `FilesystemBackend` in `build_agent`. `build_agent`'s
    `cwd` fix routed the orchestrator's backend and its `run_tests` tool at
    the worktree; it never reached here, so the test and code implementer
    subagents -- the two roles that actually call a write tool -- kept
    writing into `contract.repo` (the `--repo` clone) regardless. A live
    run proved it: an untracked, model-authored test file landed in the
    clone with this gap still open, the same defect #543 set out to fix.
    """
    repo = Path(cwd).resolve() if cwd is not None else Path(contract.repo).resolve()
    reader = read_tool(repo)
    out = []
    for role in plan(contract, loop).values():
        if role.name == "orchestrator":
            continue
        tools = [reader]
        if role.can_write:
            tools.append(scoped_write_tool(repo, role))
        spec = {
            "name": role.name.replace("_", "-"),
            "description": role.purpose,
            "system_prompt": f"You are the {role.name}. {role.purpose}",
            "tools": tools,
            "permissions": permission_rules(role),
        }
        if role.name in RESPONSE_FORMATS:
            spec["response_format"] = RESPONSE_FORMATS[role.name]
        skill = _skill_path(role.name)
        if skill:
            # The directory is named for the role, `code_implementer`, while the
            # subagent is named `code-implementer`. The mount path follows the
            # directory.
            spec["skills"] = [skill]
        out.append(spec)
    return out


def _as_permissions(rules: list[dict]):
    from deepagents import FilesystemPermission  # noqa: PLC0415

    return [FilesystemPermission(**rule) for rule in rules]


def build_agent(
    contract,
    loop: str = DEFAULT_LOOP,
    model: str = DEFAULT_MODEL,
    subagent_names: frozenset[str] | None = None,
    cwd: Path | str | None = None,
):
    """The orchestrator. Holds `run_tests`. Holds nothing that writes.

    Needs `deepagents>=0.7`. The default general-purpose subagent is turned off.
    Built-in write tools are hidden from the main agent. The target repo is
    mounted as a virtual filesystem so `..` cannot walk off it.

    #543. `cwd` is where the live session actually works: `contract.repo`
    when unset, matching every caller before this ticket, or the caller's
    own worktree path when `implementer.run` executes somewhere other than
    `contract.repo` itself (the `--repo` clone). `contract` still supplies
    the subagent config either way -- `.loop.yml` lives in the clone, and a
    worktree that does not exist yet at build time has none to read.
    """
    from deepagents import (  # noqa: PLC0415  (optional dependency)
        FilesystemPermission,
        GeneralPurposeSubagentProfile,
        HarnessProfile,
        create_deep_agent,
        register_harness_profile,
    )
    from deepagents.backends import CompositeBackend, FilesystemBackend  # noqa: PLC0415

    repo = Path(cwd).resolve() if cwd is not None else Path(contract.repo).resolve()
    register_harness_profile(
        model,
        HarnessProfile(
            excluded_tools=ORCHESTRATOR_EXCLUDED_TOOLS,
            general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False),
        ),
    )
    # #543 follow-up. `repo` above is already the resolved `cwd` when one
    # was given; this is the same worktree-vs-clone fix `subagents_for`
    # itself now needs, threaded through rather than repeating the
    # `cwd or contract.repo` choice a second time.
    specs = subagents_for(contract, loop, cwd=repo)
    if subagent_names is not None:
        available = {spec["name"] for spec in specs}
        unknown = subagent_names - available
        if unknown:
            raise ValueError(f"unknown Deep Agents subagent(s): {sorted(unknown)}")
        specs = [spec for spec in specs if spec["name"] in subagent_names]

    subagents = []
    for spec in specs:
        item = dict(spec)
        item["permissions"] = _as_permissions(spec["permissions"])
        subagents.append(item)
    return create_deep_agent(
        model=model,
        system_prompt=(
            "You are the orchestrator. You own the budget and the order. "
            "You write nothing. Delegate only to the subagents available in this graph. "
            "Never edit a test to make the suite green."
        ),
        tools=[run_tests_tool(repo)],
        subagents=subagents,
        backend=CompositeBackend(
            default=FilesystemBackend(root_dir=str(repo), virtual_mode=True),
            routes={
                "/skills/": FilesystemBackend(root_dir=str(SKILLS_DIR), virtual_mode=True),
                # `memory/`, not the solution folder. Routing at HERE would put
                # roles.py, write_scope.py, and tests/ inside the agent's reach,
                # in the folder whose lesson is that the coder may not write
                # tests/**.
                "/memory/": FilesystemBackend(root_dir=str(MEMORY_DIR), virtual_mode=True),
            },
        ),
        memory=["/memory/AGENTS.md"] if MEMORY_FILE.exists() else None,
        skills=["/skills/"] if SKILLS_DIR.is_dir() else None,
        permissions=[FilesystemPermission(**DENY_EVERY_WRITE)],
    )
