"""Research roles as LangChain Deep Agents subagents.

Researcher: search only. Writer: briefs only. Judge: read only.
The orchestrator never sees raw search dumps. It sees a summary.
"""

from __future__ import annotations

from pathlib import Path

from roleplan import DEFAULT_LOOP, RolePlan, plan
from write_scope import ScopeViolation, WriteScope


def scoped_write_tool(repo: Path, role: RolePlan):
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


def search_tool(backend):
    """One search call through the tool boundary. The loop never learns which backend."""
    from langchain.tools import tool  # noqa: PLC0415

    @tool
    def search(question: str) -> str:
        """Search through the research boundary. Returns answer plus citations."""
        finding = backend.search(question)
        cites = " ".join(finding.citations) or "(no citations)"
        return f"{finding.answer}\nCITATIONS: {cites}"

    return search


def subagents_for(contract, loop: str = DEFAULT_LOOP, backend=None) -> list[dict]:
    repo = Path(contract.repo) if contract is not None else Path(".")
    reader = read_tool(repo)
    out = []
    for role in plan(contract, loop).values():
        if role.name == "orchestrator":
            continue
        tools = [reader]
        if role.name == "researcher" and backend is not None:
            tools.append(search_tool(backend))
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


def build_agent(
    contract,
    loop: str = DEFAULT_LOOP,
    model: str = "anthropic:claude-sonnet-5",
    backend=None,
):
    from deepagents import create_deep_agent  # noqa: PLC0415

    return create_deep_agent(
        model=model,
        subagents=subagents_for(contract, loop, backend=backend),
    )
