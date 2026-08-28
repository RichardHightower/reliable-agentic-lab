"""The five implementer roles, as LangChain Deep Agents subagents.

Deep Agents scopes three ways, and this port uses all three.

1. Each subagent gets its own tool list. A subagent can only call what it was
   given, so the judge is separated the same way it is in every other runtime:
   it holds no tool that writes.
2. Path scope lives inside the write tool. The code implementer cannot weaken a
   test, because `tests/**` is not in its allow list.
3. The harness itself is fenced: no general-purpose subagent, no built-in
   `write_file` on the orchestrator, `FilesystemBackend(virtual_mode=True)` so
   `..` cannot walk off the repo, and declarative `permissions=` underneath
   everything.

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

DEFAULT_MODEL = "anthropic:claude-sonnet-5"

# Built-in harness tools that write or execute. The orchestrator must not hold
# these. Deep Agents adds them by default unless a harness profile hides them.
# `run_tests` is not among them: running the suite is a different permission
# from editing it, and the orchestrator needs the first one.
ORCHESTRATOR_EXCLUDED_TOOLS = frozenset({"write_file", "edit_file", "delete", "execute"})

# The last rule every role gets. First match wins, so anything not allowed above
# this line lands here.
DENY_EVERY_WRITE = {"operations": ["write"], "paths": ["/**", "**"], "mode": "deny"}


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
        rules.append({"operations": ["write"], "paths": _both_forms(role.deny), "mode": "deny"})
    rules.append({"operations": ["write"], "paths": _both_forms(role.allow), "mode": "allow"})
    rules.append(DENY_EVERY_WRITE)
    return rules


def _both_forms(patterns) -> list[str]:
    """Each pattern rooted and unrooted. The backend sees `/app/x`, the role
    table says `app/**`, and a rule that spells only one of them matches
    nothing."""
    out = []
    for pattern in patterns:
        out.append(pattern)
        if not pattern.startswith("/"):
            out.append("/" + pattern)
    return out


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
        out.append(
            {
                "name": role.name.replace("_", "-"),
                "description": role.purpose,
                "system_prompt": f"You are the {role.name}. {role.purpose}",
                "tools": tools,
                "permissions": permission_rules(role),
            }
        )
    return out


def _as_permissions(rules: list[dict]):
    from deepagents import FilesystemPermission  # noqa: PLC0415

    return [FilesystemPermission(**rule) for rule in rules]


def build_agent(contract, loop: str = DEFAULT_LOOP, model: str = DEFAULT_MODEL):
    """The orchestrator. Holds `run_tests`. Holds nothing that writes.

    Needs `deepagents>=0.7`. The default general-purpose subagent is turned off.
    Built-in write tools are hidden from the main agent. The target repo is
    mounted as a virtual filesystem so `..` cannot walk off it.
    """
    from deepagents import (  # noqa: PLC0415  (optional dependency)
        FilesystemPermission,
        GeneralPurposeSubagentProfile,
        HarnessProfile,
        create_deep_agent,
        register_harness_profile,
    )
    from deepagents.backends import FilesystemBackend  # noqa: PLC0415

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
        tools=[run_tests_tool(repo)],
        subagents=subagents,
        backend=FilesystemBackend(root_dir=str(repo), virtual_mode=True),
        permissions=[FilesystemPermission(**DENY_EVERY_WRITE)],
    )
