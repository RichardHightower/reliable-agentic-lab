"""Research roles as LangChain Deep Agents subagents.

Deep Agents scopes three ways, and this port uses all three. The earlier version
of this file used one, which is the same as using none.

1. Deep Agents supplies backend-aware, read-only filesystem tools. The
   reviewer receives no extra tool that could shadow those mounts, and no write
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
# An unbounded provider response can hold a resumed run hostage. The graph
# needs a sensible ceiling for plans and structured research, while a prose
# section has a tighter contract of its own.
GRAPH_MAX_TOKENS = 4_096
# The writer also binds the evidence ledger into a multi-section JSON outline.
# A 2,048-token prose ceiling truncated that outline mid-string on the live
# E2E. Section prompts ask for 400 to 1200 words; the transport ceiling
# must accommodate the writer's larger structured turn as well.
WRITER_MAX_TOKENS = 4_096
MODEL_TIMEOUT_SECONDS = 120
MODEL_MAX_RETRIES = 0

# Built-in harness tools that write or execute. The orchestrator must not hold
# these. Deep Agents adds them by default unless a harness profile hides them.
ORCHESTRATOR_EXCLUDED_TOOLS = frozenset({"write_file", "edit_file", "delete", "execute"})


def bounded_model(model: str, *, max_tokens: int):
    """Return an Anthropic client with explicit response and retry bounds.

    `create_deep_agent` accepts a prebuilt chat model. The profile registration
    below still resolves for it by its `anthropic:claude-*` identifier. An
    explicit timeout and no provider retry makes the paper's existing stage
    retry policy the single owner of retry decisions.

    The import stays inside the optional live wiring path. Offline tests can
    inspect the role plan without an Anthropic integration installed.
    """
    if not model.startswith("anthropic:"):
        return model
    try:
        from langchain_anthropic import ChatAnthropic  # noqa: PLC0415
    except ImportError:
        return model
    return ChatAnthropic(
        model_name=model.split(":", 1)[1],
        max_tokens=max_tokens,
        timeout=MODEL_TIMEOUT_SECONDS,
        max_retries=MODEL_MAX_RETRIES,
        effort="low",
    )


def bounded_writer_model(model: str):
    """Bound both the writer's prose and its larger structured outline turn."""
    return bounded_model(model, max_tokens=WRITER_MAX_TOKENS)

RESEARCHER_RESPONSE = {
    "type": "object",
    "title": "ResearchReport",
    "description": "Cited findings for exactly one research question.",
    "properties": {
        "answer": {"type": "string"},
        "sources": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "url": {"type": "string"},
                    "vendor": {"type": "string"},
                    "quote": {"type": "string"},
                },
                "required": ["title", "url", "vendor", "quote"],
                "additionalProperties": False,
            },
        },
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "confidence": {"type": "number"},
                    "source_urls": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["text", "confidence", "source_urls"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["answer", "sources", "claims"],
    "additionalProperties": False,
}

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

RESPONSE_FORMATS = {
    "researcher": RESEARCHER_RESPONSE,
    "verifier": VERIFIER_RESPONSE,
    "reviewer": REVIEWER_RESPONSE,
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


def search_tool(backend, budget=None):
    """One search call through the tool boundary.

    The loop never learns which backend answered. That is the same contract MCP
    offers and the same one the repo boundary offers: name the boundary, keep
    the caller ignorant of what is behind it.
    """
    from langchain.tools import tool  # noqa: PLC0415
    from research import Backend, BudgetExceeded  # noqa: PLC0415

    @tool
    def search(question: str) -> str:
        """Run the one filtered research boundary and return its source bundle."""
        try:
            if budget is not None:
                budget.reserve_tool()
            if isinstance(backend, Backend):
                finding = backend.search(question, budget.charge if budget is not None else None)
            else:
                # The lab deliberately accepts a tiny hand-written backend for
                # a classroom recording. It cannot make nested provider calls,
                # so preserve the original one-charge tool contract.
                if budget is not None:
                    budget.charge(getattr(backend, "cost_per_call", 0.0))
                finding = backend.search(question)
        except BudgetExceeded as exc:
            return f"NO ANSWER. {exc}"
        if finding.empty:
            return f"NO ANSWER. {finding.note or 'the boundary returned nothing'}"
        cites = " ".join(finding.citations) or "(no citations)"
        return f"{finding.answer}\nCITATIONS: {cites}"

    return search


def docs_tool(backend, budget=None):
    """Vendor documentation, for the verifier only.

    A second Perplexity query is not an independent source. It is the same index
    ranked differently, and treating it as corroboration is how a loop confirms
    its own mistake. Context7 reads the library's published docs instead.
    """
    from langchain.tools import tool  # noqa: PLC0415
    from research import Backend, BudgetExceeded  # noqa: PLC0415

    @tool
    def check_docs(query: str) -> str:
        """Check a library, API, or version claim. Pass 'library :: question'."""
        try:
            if budget is not None:
                budget.reserve_tool()
            if isinstance(backend, Backend):
                finding = backend.search(query, budget.charge if budget is not None else None)
            else:
                if budget is not None:
                    budget.charge(getattr(backend, "cost_per_call", 0.0))
                finding = backend.search(query)
        except BudgetExceeded as exc:
            return f"NO ANSWER. {exc}"
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
    into `FilesystemPermission` objects. Deep Agents 0.7 rejects relative
    paths, so the SDK-facing copy is absolute even though the role plan and
    custom `WriteScope` deliberately use relative repo paths.
    """
    if not role.can_write:
        return [{"operations": ["write"], "paths": ["/**"], "mode": "deny"}]
    rules: list[dict] = []
    if role.deny:
        paths = [pattern if pattern.startswith("/") else "/" + pattern for pattern in role.deny]
        # Deny first. A role's own deny list beats its own allow list, the same
        # rule WriteScope enforces, so the two layers cannot disagree.
        rules.append({"operations": ["write"], "paths": paths, "mode": "deny"})
    allow = list(role.allow) or ["work/**"]
    paths = [pattern if pattern.startswith("/") else "/" + pattern for pattern in allow]
    rules.append({"operations": ["write"], "paths": paths, "mode": "allow"})
    rules.append({"operations": ["write"], "paths": ["/**"], "mode": "deny"})
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
    budget=None,
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
    out = []
    for role in plan(contract, loop).values():
        if role.name == "orchestrator":
            continue
        # `Paper.stage_write` owns persistence: it gates the returned prose and
        # checkpoints `sections.json` after every accepted section. Letting the
        # writer also browse or write the run directory creates a second,
        # ungated paper and makes a resumed run depend on stale side files.
        # Keep the educational role's normal write scope outside this pipeline;
        # the live paper writer is an answer-only subagent.
        answer_only_writer = loop == "paper" and role.name == "writer"
        # `create_deep_agent` adds backend-aware filesystem tools. A custom
        # function named `read_file` wins the duplicate tool name and cannot
        # resolve the `/skills/**` and `/memory/**` mounts, so custom tools
        # begin empty here.
        tools = []
        if role.name == "researcher" and backend is not None:
            tools.append(search_tool(backend, budget))
        if role.name == "verifier":
            if docs_backend is not None:
                tools.append(docs_tool(docs_backend, budget))
            if backend is not None:
                tools.append(search_tool(backend, budget))
        if role.name == "planner":
            tools.append(second_brain_tool(brain))
        if role.can_write and not answer_only_writer:
            tools.append(scoped_write_tool(root, role))

        prompt = f"You are the {role.name}. {role.purpose}"
        skill_dir = SKILLS_DIR / role.name
        if answer_only_writer:
            prompt += (
                "\n\n" + _skill_text(role.name) + "\n\n"
                "The delegation message contains the complete evidence and output contract. "
                "Return the requested section body directly. Do not read, list, search, "
                "glob, grep, or write any file."
            )
        elif skill_dir.is_dir():
            prompt += (
                f" Before you work, use the built-in read_file tool to read "
                f"/skills/{role.name}/SKILL.md and follow it."
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
            "permissions": (
                [{"operations": ["read", "write"], "paths": ["/**"], "mode": "deny"}]
                if answer_only_writer
                else permission_rules(role)
            ),
        }
        if role.name in RESPONSE_FORMATS:
            spec["response_format"] = RESPONSE_FORMATS[role.name]
        if skill_dir.is_dir() and not answer_only_writer:
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
    budget=None,
    repo: Path | None = None,
    brain: Path | None = None,
    debug: bool = False,
):
    """The orchestrator, holding the subagents and nothing that writes.

    Needs `deepagents>=0.7`. The default general-purpose subagent is turned off.
    Built-in write tools are hidden from the main agent. The working directory is
    mounted as a virtual filesystem so `..` cannot walk off it.

    `debug` is deliberately a parent-graph switch. Deep Agents compiles one
    parent graph, and the dict subagent specs do not have a per-role debug
    field. The caller pairs it with LangGraph streaming when it needs to see
    namespaces and task events from the delegated subgraphs.
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
    runtime_model = bounded_model(model, max_tokens=GRAPH_MAX_TOKENS)
    subagents = []
    writer_model = bounded_writer_model(model)
    for spec in subagents_for(
        contract, loop, backend, docs_backend=docs_backend, budget=budget, repo=root, brain=brain
    ):
        item = dict(spec)
        item["permissions"] = _as_permissions(spec["permissions"])
        if spec["name"] == "writer":
            item["model"] = writer_model
        subagents.append(item)

    memory = ["/memory/AGENTS.md"] if MEMORY_FILE.exists() else None
    skills = ["/skills/"] if SKILLS_DIR.is_dir() else None
    return create_deep_agent(
        model=runtime_model,
        system_prompt=(
            "You are the orchestrator. You own the budget and the order. "
            "You write nothing. Delegate searching to the researcher subagent, "
            "corroboration to the verifier, drafting to the writer, and grading "
            "to the reviewer. Never write a file yourself. Never publish."
        ),
        subagents=subagents,
        backend=fs,
        permissions=[FilesystemPermission(operations=["write"], paths=["/**"], mode="deny")],
        memory=memory,
        skills=skills,
        debug=debug,
    )


def build_paper_agents(  # noqa: PLR0913 (the dependencies are deliberate wiring)
    contract,
    loop: str = DEFAULT_LOOP,
    model: str = DEFAULT_MODEL,
    backend=None,
    *,
    docs_backend=None,
    budget=None,
    repo: Path | None = None,
    brain: Path | None = None,
    debug: bool = False,
) -> dict[str, object]:
    """Compile one role-local Deep Agent graph for the paper pipeline.

    A parent `task` handoff preserves tool execution but does not reliably
    preserve the delegated role's final prose in the parent state. The pipeline
    needs that exact result for its evidence gates, so it invokes a compiled
    graph for the named role directly. This is still Deep Agents: each graph
    has the SDK's filesystem, skills, response-format, and permission
    middleware. It simply avoids treating a parent's tool receipt as prose.

    `build_agent` remains the parent-graph constructor for the explicit parent
    debug probe. This factory is the paper runtime's per-role execution path.
    """
    from deepagents import (  # noqa: PLC0415
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
    runtime_model = bounded_model(model, max_tokens=GRAPH_MAX_TOKENS)
    writer_model = bounded_writer_model(model)
    agents: dict[str, object] = {}
    for spec in subagents_for(
        contract, loop, backend, docs_backend=docs_backend, budget=budget, repo=root, brain=brain
    ):
        item = dict(spec)
        permissions = _as_permissions(spec["permissions"])
        role_model = writer_model if spec["name"] == "writer" else runtime_model
        agents[spec["name"].replace("-", "_")] = create_deep_agent(
            model=role_model,
            system_prompt=spec["system_prompt"],
            tools=spec["tools"],
            backend=fs,
            permissions=permissions,
            skills=spec.get("skills"),
            response_format=spec.get("response_format"),
            debug=debug,
        )
    return agents
