"""Research roles as LangChain Deep Agents subagents.

Deep Agents scopes three ways, and this port uses all three. The earlier version
of this file used one, which is the same as using none.

1. Each subagent gets its own tool list. The reviewer is never handed a write
   tool, so "do not edit the paper" is not an instruction it can reinterpret.
2. The write tool checks the path against the role's scope before it touches the
   disk. The writer may write `paper/**` and the verifier may write
   `evidence/**`, and neither can reach the other.
3. The harness itself is fenced: no general-purpose subagent, no built-in
   `write_file` on the orchestrator, `FilesystemBackend(virtual_mode=True)` so
   `..` cannot walk out, and declarative `permissions=` underneath everything.

Layer 3 is the one people skip. The default general-purpose subagent ships with
the harness filesystem tools, so leaving it enabled is how a carefully scoped
agent writes anywhere it likes. `build_agent` turns it off.

(1) and (2) are what the tests pin down with no SDK installed. Nothing in this
module calls a model. `subagents_for` returns configuration.
"""

from __future__ import annotations

from pathlib import Path

from roleplan import DEFAULT_LOOP, RolePlan, plan
from write_scope import ScopeViolation, WriteScope

HERE = Path(__file__).resolve().parent
SKILLS_DIR = HERE / "skills"
MEMORY_FILE = HERE / "AGENTS.md"
DEFAULT_MODEL = "anthropic:claude-sonnet-5"

# Built-in harness tools that write or execute. The orchestrator must not hold
# these. Deep Agents adds them by default unless a harness profile hides them.
ORCHESTRATOR_EXCLUDED_TOOLS = frozenset({"write_file", "edit_file", "delete", "execute"})

# The verifier reports which claims it could corroborate. It does not report
# whether the paper is ready, and there is no field here for it to say so.
VERIFIER_RESPONSE = {
    "type": "object",
    "title": "VerifierReport",
    "description": (
        "For each claim you checked, the second source you found and whether it "
        "agreed. Do not compute a truth state. Do not decide whether the claim "
        "may be used. corroborate_status is agreed, disagreed, or not_found."
    ),
    "properties": {
        "checked": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim_id": {"type": "string"},
                    "second_source_url": {"type": "string"},
                    "corroborate_status": {
                        "type": "string",
                        "enum": ["agreed", "disagreed", "not_found"],
                    },
                    "quote": {"type": "string"},
                },
                "required": ["claim_id", "corroborate_status"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["checked"],
    "additionalProperties": False,
}

# The reviewer names failing rows. It does not name a verdict, because a verdict
# is arithmetic over the rows and `paper_check` already owns that arithmetic.
REVIEWER_RESPONSE = {
    "type": "object",
    "title": "ReviewVerdict",
    "description": (
        "Which rubric rows this draft fails, and why, in one sentence each. "
        "Do not decide whether to ship. Do not decide whether to retry."
    ),
    "properties": {
        "failed_rows": {"type": "array", "items": {"type": "string"}},
        "notes": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["failed_rows"],
    "additionalProperties": False,
}

RESPONSE_FORMATS = {"verifier": VERIFIER_RESPONSE, "reviewer": REVIEWER_RESPONSE}


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
        """Read a file from the working directory."""
        target = _inside(repo, path)
        if target is None:
            return f"REFUSED. {path} is outside the target repo."
        if not target.exists():
            return f"no such file: {path}"
        return target.read_text(encoding="utf-8")

    return read_file


def search_tool(backend):
    """One search call through the tool boundary.

    The loop never learns which backend answered. That is the same contract MCP
    offers and the same one the repo boundary offers: name the boundary, keep
    the caller ignorant of what is behind it.
    """
    from langchain.tools import tool  # noqa: PLC0415

    @tool
    def search(question: str) -> str:
        """Search through the research boundary. Returns an answer plus citations."""
        finding = backend.search(question)
        if finding.empty:
            return f"NO ANSWER. {finding.note or 'the boundary returned nothing'}"
        cites = " ".join(finding.citations) or "(no citations)"
        return f"{finding.answer}\nCITATIONS: {cites}"

    return search


def docs_tool(backend):
    """Vendor documentation, for the verifier only.

    A second Perplexity query is not an independent source. It is the same index
    ranked differently, and treating it as corroboration is how a loop confirms
    its own mistake. Context7 reads the library's published docs instead.
    """
    from langchain.tools import tool  # noqa: PLC0415

    @tool
    def check_docs(query: str) -> str:
        """Check a library, API, or version claim. Pass 'library :: question'."""
        finding = backend.search(query)
        if finding.empty:
            return f"NO ANSWER. {finding.note or 'the documentation boundary returned nothing'}"
        cites = " ".join(finding.citations) or "(no citations)"
        return f"{finding.answer}\nCITATIONS: {cites}"

    return check_docs


def second_brain_tool(root: Path | None):
    """Prior knowledge, read only, from the second brain when it is present.

    Grep and read, never write. The brain is a shared, curated thing, and a
    research loop that can edit it can quietly launder its own output into
    everybody's prior knowledge.
    """
    from langchain.tools import tool  # noqa: PLC0415

    @tool
    def recall(query: str) -> str:
        """Search prior research in the second brain. Read only. Returns excerpts."""
        if root is None or not Path(root).is_dir():
            return "NO BRAIN. The second brain is not available here. Continue without it."
        import re  # noqa: PLC0415

        pattern = re.compile(re.escape(query), re.I)
        hits = []
        for path in sorted(Path(root).rglob("*.md")):
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for line in text.split("\n"):
                if pattern.search(line):
                    hits.append(f"{path.name}: {line.strip()[:200]}")
                    break
            if len(hits) >= 12:
                break
        return "\n".join(hits) if hits else f"no prior research mentions {query!r}"

    return recall


def permission_rules(role: RolePlan) -> list[dict]:
    """Declarative filesystem rules for one role. First match wins.

    Plain dicts so the tests can read them with no SDK. `build_agent` turns them
    into `FilesystemPermission` objects.
    """
    if not role.can_write:
        return [{"operations": ["write"], "paths": ["/**", "**"], "mode": "deny"}]
    rules: list[dict] = []
    if role.deny:
        paths = []
        for pattern in role.deny:
            paths.append(pattern)
            if not pattern.startswith("/"):
                paths.append("/" + pattern)
        # Deny first. A role's own deny list beats its own allow list, the same
        # rule WriteScope enforces, so the two layers cannot disagree.
        rules.append({"operations": ["write"], "paths": paths, "mode": "deny"})
    allow = list(role.allow) or ["work/**"]
    paths = []
    for pattern in allow:
        paths.append(pattern)
        if not pattern.startswith("/"):
            paths.append("/" + pattern)
    rules.append({"operations": ["write"], "paths": paths, "mode": "allow"})
    rules.append({"operations": ["write"], "paths": ["/**", "**"], "mode": "deny"})
    return rules


def _skill_text(name: str) -> str:
    path = SKILLS_DIR / name / "SKILL.md"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def subagents_for(  # noqa: PLR0913  (one keyword per wiring point)
    contract,
    loop: str = DEFAULT_LOOP,
    backend=None,
    *,
    docs_backend=None,
    repo: Path | None = None,
    brain: Path | None = None,
) -> list[dict]:
    """One Deep Agents subagent per role in this loop's cast, with its own tools.

    The tool assignment is the whole security model, so read this list as the
    contract it is. Only the researcher gets `search`. Only the verifier gets
    `check_docs`. Only the planner gets `recall`. Nobody else can reach outside
    the process at all.
    """
    root = (
        Path(repo)
        if repo is not None
        else Path(contract.repo)
        if contract is not None
        else Path(".")
    )
    reader = read_tool(root)
    out = []
    for role in plan(contract, loop).values():
        if role.name == "orchestrator":
            continue
        tools = [reader]
        if role.name == "researcher" and backend is not None:
            tools.append(search_tool(backend))
        if role.name == "verifier":
            if docs_backend is not None:
                tools.append(docs_tool(docs_backend))
            if backend is not None:
                tools.append(search_tool(backend))
        if role.name == "planner":
            tools.append(second_brain_tool(brain))
        if role.can_write:
            tools.append(scoped_write_tool(root, role))

        prompt = f"You are the {role.name}. {role.purpose}"
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
        if role.name in RESPONSE_FORMATS:
            spec["response_format"] = RESPONSE_FORMATS[role.name]
        if (SKILLS_DIR / role.name).is_dir():
            spec["skills"] = [f"/skills/{role.name}/"]
        out.append(spec)
    return out


def _as_permissions(rules: list[dict]):
    from deepagents import FilesystemPermission  # noqa: PLC0415

    return [FilesystemPermission(**rule) for rule in rules]


def build_agent(  # noqa: PLR0913  (one keyword per wiring point)
    contract,
    loop: str = DEFAULT_LOOP,
    model: str = DEFAULT_MODEL,
    backend=None,
    *,
    docs_backend=None,
    repo: Path | None = None,
    brain: Path | None = None,
):
    """The orchestrator, holding the subagents and nothing that writes.

    Needs `deepagents>=0.7`. The default general-purpose subagent is turned off.
    Built-in write tools are hidden from the main agent. The working directory is
    mounted as a virtual filesystem so `..` cannot walk off it.
    """
    from deepagents import (  # noqa: PLC0415  (optional dependency)
        FilesystemPermission,
        GeneralPurposeSubagentProfile,
        HarnessProfile,
        create_deep_agent,
        register_harness_profile,
    )
    from deepagents.backends import CompositeBackend, FilesystemBackend  # noqa: PLC0415

    root = (
        Path(repo).resolve()
        if repo is not None
        else Path(contract.repo).resolve()
        if contract is not None
        else Path(".").resolve()
    )
    fs = CompositeBackend(
        default=FilesystemBackend(root_dir=str(root), virtual_mode=True),
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
    for spec in subagents_for(
        contract, loop, backend, docs_backend=docs_backend, repo=root, brain=brain
    ):
        item = dict(spec)
        item["permissions"] = _as_permissions(spec["permissions"])
        subagents.append(item)

    memory = ["/memory/AGENTS.md"] if MEMORY_FILE.exists() else None
    skills = ["/skills/"] if SKILLS_DIR.is_dir() else None
    return create_deep_agent(
        model=model,
        system_prompt=(
            "You are the orchestrator. You own the budget and the order. "
            "You write nothing. Delegate searching to the researcher subagent, "
            "corroboration to the verifier, drafting to the writer, and grading "
            "to the reviewer. Never write a file yourself. Never publish."
        ),
        subagents=subagents,
        backend=fs,
        permissions=[FilesystemPermission(operations=["write"], paths=["/**", "**"], mode="deny")],
        memory=memory,
        skills=skills,
    )
