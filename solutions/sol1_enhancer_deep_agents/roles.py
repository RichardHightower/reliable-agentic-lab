"""The five roles, as LangChain Deep Agents subagents.

Deep Agents scopes three ways, and this port uses all three.

1. Deep Agents supplies the read-only filesystem tools through its mounted
   backend. The judge receives no extra tools that could shadow those routes.
2. The doer's one custom write tool checks `tickets/**` before it touches disk.
3. The harness itself is fenced: no general-purpose subagent, no built-in
   `write_file` on the orchestrator, `FilesystemBackend(virtual_mode=True)`,
   and declarative `permissions=` that deny writes outside `tickets/**`.

(1) and (2) are what the tests pin down with no SDK installed. (3) is what
`build_agent` does, so a live run cannot walk around those tests through the
default general-purpose subagent. That subagent ships with the harness
filesystem tools. Leaving it enabled is how a "scoped" agent writes `app/`.

Nothing here calls a model. `subagents_for` returns configuration.
"""

from __future__ import annotations

import contextlib
import contextvars
from pathlib import Path

from roleplan import DEFAULT_LOOP, RolePlan, plan
from write_scope import ScopeViolation, WriteScope

# The scope for the call in flight, narrower than the role's declared scope.
#
# A role's row says where it may EVER write. One turn wants less than that. The
# doer's row allows `tickets/**`, which includes the real ticket the judge is
# grading and every other ticket in the repo. A doer that writes the real ticket
# directly has gone around the proper-subset gate, and the gate is the only
# reason a draft has to be an improvement before it counts.
#
# The orchestrator already computes the one path it wants per turn, so the turn
# carries it. A ContextVar rather than a constructor argument because the agent
# is built once and invoked many times.
CURRENT_ALLOW: contextvars.ContextVar[tuple[str, ...] | None] = contextvars.ContextVar(
    "current_allow", default=None
)


@contextlib.contextmanager
def write_allow(allow):
    """Narrow every write tool to `allow` for the duration of one call.

    An empty or absent list leaves each role at its declared scope, which is
    what the judge turn wants: it holds no write tool, so there is nothing to
    narrow.
    """
    token = CURRENT_ALLOW.set(tuple(allow) if allow else None)
    try:
        yield
    finally:
        CURRENT_ALLOW.reset(token)


HERE = Path(__file__).resolve().parent
SKILLS_DIR = HERE / "skills"
MEMORY_FILE = HERE / "AGENTS.md"
DEFAULT_MODEL = "anthropic:claude-sonnet-5"

# Built-in harness tools that write or execute. The orchestrator must not hold
# these. Deep Agents adds them by default unless a harness profile hides them.
ORCHESTRATOR_EXCLUDED_TOOLS = frozenset({"write_file", "edit_file", "delete", "execute"})

JUDGE_RESPONSE = {
    "type": "object",
    "title": "JudgeVerdict",
    "description": (
        "Inventory of which required fields the ticket currently has. "
        "Do not compute ready. Do not list missing fields. "
        "kind is bug, feature, or ui."
    ),
    "properties": {
        "kind": {"type": "string", "enum": ["bug", "feature", "ui"]},
        "present_fields": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["kind", "present_fields"],
    "additionalProperties": False,
}


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

    root = Path(repo).resolve()

    @tool(f"write_{role.name}")
    def write(path: str, content: str) -> str:
        """Write a file inside the scope this turn allows."""
        # The turn's scope, or the role's when the turn did not narrow it.
        # Deny always comes from the row: a turn may shrink what a role can
        # write, never widen it.
        turn = CURRENT_ALLOW.get()
        allow = list(turn) if turn else list(role.allow)
        scope = WriteScope(allow=allow, deny=list(role.deny))
        allowed = ", ".join(allow) or "nothing"

        # Canonicalize first, then scope-check the canonical relative path.
        # The glob in `WriteScope` does not resolve `..`, so `tickets/../app/x.py`
        # matches `tickets/**` as text while landing in `app/`. Checking the
        # path the write will actually use removes the difference between what
        # the scope reads and what the disk receives.
        target = _inside(repo, path)
        if target is None:
            return f"REFUSED. {path} is outside the target repo."
        relative = target.relative_to(root).as_posix()
        try:
            scope.check(relative)
        except ScopeViolation:
            return f"REFUSED. {role.name} may write {allowed} this turn. {relative} is not that."
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"wrote {relative}"

    return write


def permission_rules(role: RolePlan) -> list[dict]:
    """Declarative filesystem rules for one role. First match wins.

    These are plain dicts so the tests can read them with no SDK. `build_agent`
    turns them into `FilesystemPermission` objects.
    """
    if not role.can_write:
        return [
            {
                "operations": ["write"],
                "paths": ["/**"],
                "mode": "deny",
            }
        ]
    allow = list(role.allow) or ["tickets/**"]
    paths = [pattern if pattern.startswith("/") else "/" + pattern for pattern in allow]
    return [
        {"operations": ["write"], "paths": paths, "mode": "allow"},
        {"operations": ["write"], "paths": ["/**"], "mode": "deny"},
    ]


def _skill_text(name: str) -> str:
    path = SKILLS_DIR / name / "SKILL.md"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def subagents_for(contract, loop: str = DEFAULT_LOOP) -> list[dict]:
    """One Deep Agents subagent per role in this loop's cast, with its own tools."""
    repo = Path(contract.repo)
    out = []
    for role in plan(contract, loop).values():
        if role.name == "orchestrator":
            continue
        # `create_deep_agent` adds its backend-aware filesystem tools. Do not
        # add a custom function named `read_file`: it wins the duplicate tool
        # name and cannot resolve the `/skills/**` and `/memory/**` mounts.
        tools = []
        if role.can_write:
            tools.append(scoped_write_tool(repo, role))
        # Mount or inline, not both. Deep Agents loads a skill in two levels:
        # its metadata sits in the system prompt at startup, and its
        # instructions join the context only when the skill is invoked. Pasting
        # the body in here as well makes it always resident, which is the exact
        # cost the mount exists to avoid. A role with a directory gets the
        # mount below. A role without one keeps its prompt line.
        prompt = f"You are the {role.name}. {role.purpose}"
        skill_dir = SKILLS_DIR / role.name
        if skill_dir.is_dir():
            prompt += (
                f" Before you grade or draft, use the built-in read_file tool "
                f"to read /skills/{role.name}/SKILL.md and follow it."
            )
        else:
            skill = _skill_text(role.name)
            if skill:
                prompt = f"{prompt}\n\n{skill}"
        spec = {
            "name": role.name.replace("_", "-"),
            "description": role.purpose,
            "system_prompt": prompt,
            "tools": tools,
            "permissions": permission_rules(role),
        }
        if role.name == "judge":
            spec["response_format"] = JUDGE_RESPONSE
        # Every role with a directory, not just the doer. `skills/judge/SKILL.md`
        # has existed since this folder was written and never mounted, because
        # this line named one role. Its text still reached the judge through the
        # prompt above, which is the inline half of the same idea, so nothing
        # looked broken.
        if skill_dir.is_dir():
            spec["skills"] = [f"/skills/{role.name}/"]
        out.append(spec)
    return out


def _as_permissions(rules: list[dict]):
    from deepagents import FilesystemPermission  # noqa: PLC0415

    return [FilesystemPermission(**rule) for rule in rules]


def build_agent(
    contract,
    loop: str = DEFAULT_LOOP,
    model: str = DEFAULT_MODEL,
    *,
    debug: bool = False,
):
    """The orchestrator, holding the subagents and nothing that writes.

    Needs `deepagents>=0.7`. The default general-purpose subagent is turned
    off. Built-in write tools are hidden from the main agent. The CRM is
    mounted as a virtual filesystem so `..` cannot walk off the repo.
    """
    from deepagents import (  # noqa: PLC0415  (optional dependency)
        FilesystemPermission,
        GeneralPurposeSubagentProfile,
        HarnessProfile,
        create_deep_agent,
        register_harness_profile,
    )
    from deepagents.backends import CompositeBackend, FilesystemBackend

    repo = Path(contract.repo).resolve()
    backend = CompositeBackend(
        default=FilesystemBackend(root_dir=str(repo), virtual_mode=True),
        routes={
            "/skills/": FilesystemBackend(root_dir=str(SKILLS_DIR), virtual_mode=True),
            "/memory/": FilesystemBackend(root_dir=str(HERE), virtual_mode=True),
        },
    )
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
    orchestrator_permissions = [
        FilesystemPermission(operations=["write"], paths=["/**"], mode="deny"),
    ]
    memory = ["/memory/AGENTS.md"] if MEMORY_FILE.exists() else None
    skills = ["/skills/"] if SKILLS_DIR.is_dir() else None
    return create_deep_agent(
        model=model,
        system_prompt=(
            "You are the orchestrator. You own the budget and the order. "
            "You write nothing. Delegate drafting to the doer subagent. "
            "Delegate grading to the judge subagent. Never edit application code."
        ),
        subagents=subagents,
        backend=backend,
        permissions=orchestrator_permissions,
        memory=memory,
        skills=skills,
        debug=debug,
    )
