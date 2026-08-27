"""The five roles, as LangChain Deep Agents subagents.

Deep Agents scopes by handing each subagent its own tool list. A subagent can
only call what it was given, so the judge is separated the same way it is in
every other runtime: it holds no tool that writes.

Path scope needs one more step. The write tool itself checks the scope before
it touches the disk, which is the same idea as the Agent SDK's PreToolUse hook
moved inside the tool.

Nothing here calls a model. `subagents_for` returns configuration.
"""

from __future__ import annotations

from pathlib import Path

from loops.roles import ScopeViolation, WriteScope
from solutions.roleplan import DEFAULT_LOOP, RolePlan, plan


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
        target = repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"wrote {path}"

    return write


def read_tool(repo: Path):
    from langchain.tools import tool  # noqa: PLC0415  (optional dependency)

    @tool
    def read_file(path: str) -> str:
        """Read a file from the target repo."""
        target = repo / path
        if not target.exists():
            return f"no such file: {path}"
        return target.read_text(encoding="utf-8")

    return read_file


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
    """The orchestrator, holding the subagents and nothing that writes."""
    from deepagents import create_deep_agent  # noqa: PLC0415  (optional dependency)

    return create_deep_agent(model=model, subagents=subagents_for(contract, loop))
