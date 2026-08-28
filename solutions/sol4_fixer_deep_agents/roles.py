"""The three roles, as LangChain Deep Agents subagents.

Deep Agents scopes three ways, and this port uses all three.

1. Each subagent gets its own tool list. The judge is never handed a write tool.
2. The code implementer's write tool checks `app/**` before it touches the disk,
   and `tests/**` is denied, so a failing test cannot be edited into passing.
3. The harness itself is fenced: no general-purpose subagent, no built-in
   `write_file` on the orchestrator, `FilesystemBackend(virtual_mode=True)`,
   and declarative `permissions=` that deny every write the role table does not
   grant.

(1) and (2) are what the tests pin down with no SDK installed. (3) is what
`build_agent` does, so a live run cannot walk around those tests through the
default general-purpose subagent. That subagent ships with the harness
filesystem tools. Leaving it enabled is how a "scoped" fixer rewrites the
broken test instead of the broken code.

Nothing here calls a model. `subagents_for` returns configuration.
"""

from __future__ import annotations

from pathlib import Path

from roleplan import DEFAULT_LOOP, RolePlan, plan
from write_scope import ScopeViolation, WriteScope

DEFAULT_MODEL = "anthropic:claude-sonnet-5"

HERE = Path(__file__).resolve().parent
SKILLS_DIR = HERE / "skills"
MEMORY_DIR = HERE / "memory"
MEMORY_FILE = MEMORY_DIR / "AGENTS.md"

# Built-in harness tools that write or execute. The orchestrator must not hold
# these. Deep Agents adds them by default unless a harness profile hides them.
ORCHESTRATOR_EXCLUDED_TOOLS = frozenset({"write_file", "edit_file", "delete", "execute"})


# The judge answers one question and names no gate.
#
# The consumer is the framework, not this folder's Python. From the Deep Agents
# docs: without `response_format` the parent receives the subagent's last
# message text as-is; with it the parent always gets valid JSON matching the
# schema, JSON-serialized into the ToolMessage the parent reads.
#
# `gates.decide` takes a `judge_done` argument and this folder ships no loop driver, so nothing
# calls it yet. Naming a gate is
# still the one thing the judge may not do, the same reason sol1's schema
# forbids `ready`: a stop condition a model can phrase its way past is not a
# stop condition.
JUDGE_RESPONSE = {
    "type": "object",
    "title": "JudgeVerdict",
    "description": (
        "Whether the diff does what the broken pull request needed. One question, one answer, one sentence "
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

    sol1 does both. This folder does one.
    """
    return f"/skills/{name}/" if (SKILLS_DIR / name).is_dir() else None


def _inside(repo: Path, path: str):
    """Resolve `path` under `repo`, or None when it escapes.

    `virtual_mode` on the Deep Agents backend fences the built-in filesystem
    tools. It does not fence a tool this folder wrote. Without this check,
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
    """A write tool that refuses a path outside this role's scope.

    Returning the refusal as text, rather than raising, is deliberate. An
    unformatted exception string in an agent's context tends to start a retry
    loop. A short sentence that names the scope tends to change the next action.
    """
    from langchain.tools import tool  # noqa: PLC0415  (optional dependency)

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
    from langchain.tools import tool  # noqa: PLC0415  (optional dependency)

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


def permission_rules(role: RolePlan) -> list[dict]:
    """Declarative filesystem rules for one role. First match wins.

    The deny list comes first on purpose. The code implementer is allowed
    `app/**` and denied `tests/**`, and a target repo is free to declare an
    allow pattern that overlaps its own deny pattern. Put allow first and the
    overlap silently resolves in favour of writing.

    These are plain dicts so the tests can read them with no SDK. `build_agent`
    turns them into `FilesystemPermission` objects.
    """
    if not role.can_write:
        return [{"operations": ["write"], "paths": ["/**", "**"], "mode": "deny"}]
    rules = []
    if role.deny:
        rules.append({"operations": ["write"], "paths": _both_roots(role.deny), "mode": "deny"})
    if role.allow:
        # A target repo that names no scope for this role gets no allow rule at
        # all. An allow rule with an empty path list is a rule that matches
        # nothing, and it reads like a grant.
        rules.append({"operations": ["write"], "paths": _both_roots(role.allow), "mode": "allow"})
    rules.append({"operations": ["write"], "paths": ["/**", "**"], "mode": "deny"})
    return rules


def _both_roots(patterns) -> list[str]:
    """Each pattern twice, relative and rooted.

    The virtual filesystem addresses a file as `/app/x.py`. The role table
    writes the same file as `app/x.py`. A rule that carries only one spelling
    matches only half the paths the agent will ask for.
    """
    paths = []
    for pattern in patterns:
        paths.append(pattern)
        if not pattern.startswith("/"):
            paths.append("/" + pattern)
    return paths


def subagents_for(contract, loop: str = DEFAULT_LOOP) -> list[dict]:
    """One Deep Agents subagent per role in this loop's cast, with its own tools."""
    repo = Path(contract.repo)
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
    from deepagents import FilesystemPermission  # noqa: PLC0415  (optional dependency)

    return [FilesystemPermission(**rule) for rule in rules]


def build_agent(contract, loop: str = DEFAULT_LOOP, model: str = DEFAULT_MODEL):
    """The orchestrator, holding the subagents and nothing that writes.

    Needs `deepagents>=0.7`. The default general-purpose subagent is turned
    off. Built-in write tools are hidden from the main agent. The target repo
    is mounted as a virtual filesystem so `..` cannot walk off it.
    """
    from deepagents import (  # noqa: PLC0415  (optional dependency)
        FilesystemPermission,
        GeneralPurposeSubagentProfile,
        HarnessProfile,
        create_deep_agent,
        register_harness_profile,
    )
    from deepagents.backends import CompositeBackend, FilesystemBackend  # noqa: PLC0415

    repo = Path(contract.repo).resolve()
    register_harness_profile(
        model,
        HarnessProfile(
            excluded_tools=ORCHESTRATOR_EXCLUDED_TOOLS,
            general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False),
        ),
    )
    subagents = []
    for spec in subagents_for(contract, loop):
        item = dict(spec)
        item["permissions"] = _as_permissions(spec["permissions"])
        subagents.append(item)
    return create_deep_agent(
        model=model,
        system_prompt=(
            "You are the orchestrator. You own the budget and the order. "
            "You write nothing. Delegate the fix to the code-implementer "
            "subagent. Delegate grading to the judge subagent. Never edit a "
            "test to make the suite green."
        ),
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
        permissions=[FilesystemPermission(operations=["write"], paths=["/**", "**"], mode="deny")],
    )
