"""The five implementer roles, as LangChain Deep Agents subagents.

Deep Agents scopes by handing each subagent its own tool list. A subagent can
only call what it was given, so the judge is separated the same way it is in
every other runtime: it holds no tool that writes.

Path scope lives inside the write tool. Python still owns the red gate and
the Pass / Retry / Escalate decision. The model never counts its own retries.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from roleplan import DEFAULT_LOOP, RolePlan, plan
from write_scope import ScopeViolation, WriteScope


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
        target = repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"wrote {path}"

    return write


def read_tool(repo: Path):
    from langchain.tools import tool  # noqa: PLC0415

    @tool
    def read_file(path: str) -> str:
        """Read a file from the target repo."""
        target = repo / path
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
            }
        )
    return out


def build_agent(contract, loop: str = DEFAULT_LOOP, model: str = "anthropic:claude-sonnet-5"):
    """The orchestrator. Holds `task` plus `run_tests`. Holds no write tool."""
    from deepagents import create_deep_agent  # noqa: PLC0415

    repo = Path(contract.repo)
    return create_deep_agent(
        model=model,
        tools=[run_tests_tool(repo)],
        subagents=subagents_for(contract, loop),
    )
