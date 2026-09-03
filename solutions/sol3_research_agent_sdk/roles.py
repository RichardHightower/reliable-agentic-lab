"""The research cast, as Claude Agent SDK subagents.

The Agent SDK enforces scope in two places, and you need both.

    tools=[...]        decides whether a role can write at all
    PreToolUse hook    decides which paths it may write

Six of the eight roles hold no `Edit` and no `Write`, so for them there is
nothing for a hook to guard. The writer holds `Write`, scoped to `sections/**`,
and the hook is what keeps it there and out of `paper.md`.

One hook serves the whole cast, not one hook per writer. sol1 registers one per
writing role because the enhancer has exactly one. That does not generalize:
register several hooks on `Write` and every one of them runs, an empty dict
means "no opinion", and the first role that shrugs lets another role's write
through. This hook reads `agent_type` off the tool call instead, which the SDK
populates whenever the call comes from inside a spawned subagent, and looks up
that role's scope. A write with no `agent_type` came from the parent, and the
parent has no business writing anything.

Nothing here calls a model. `options_for` returns configuration, and `paper.py`
is what runs it.
"""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath

from load_agents import DEFAULT_MAX_TURNS, PARENT_PROMPT, PLUGIN, agent_files
from roleplan import RolePlan, plan
from write_scope import WriteScope

LOOP = "research"
FOLDER = Path(__file__).resolve().parent
IMAGEN_DIAGRAMS_PLUGIN = FOLDER / ".cache" / "imagen-diagrams"
IMAGE_GEN_PLUGIN = FOLDER / ".cache" / "image-gen"

# Task resolves these same paths. Keep this local to the standalone port: an
# attendee can copy the folder and put a key beside it, beside `solutions/`, at
# the repo root, or one directory above that checkout. The nearest file wins.
DOTENV_PATHS = (
    FOLDER / ".env",
    FOLDER.parent / ".env",
    FOLDER.parents[1] / ".env",
    FOLDER.parents[2] / ".env",
)

# Tool inputs that name a path. A hook has to know where to look.
PATH_KEYS = ("file_path", "path", "notebook_path")

WRITE_TOOL_NAMES = ("Edit", "Write", "NotebookEdit")

# Both names for "spawn a subagent". The CLI calls it `Task`, and some SDK
# versions expose it as `Agent`. Allowing a name that does not exist costs
# nothing. Allowing neither costs the whole run.
SPAWN_TOOLS = ("Task", "Agent")

# No role in this cast holds a shell, so deny it once at the top rather than
# rely on six tool lists all continuing to omit it.
GLOBAL_DENY = ["Bash"]

# Tools a reader must never hold, restated on the AgentDefinition itself. The
# tool list is the allow side. This is the deny side, and having both means a
# widened list still fails closed.
NO_WRITE = ["Edit", "Write", "NotebookEdit", "Bash"]


def environment_value(name: str) -> str | None:
    """Find one unquoted dotenv value without executing dotenv syntax.

    An exported process variable wins. Otherwise inspect the four documented
    locations in nearest-first order. Only the selected value is passed to the
    MCP child; loading an entire dotenv file into this process would make a
    research run inherit unrelated settings and could evaluate shell syntax.
    """
    if name in os.environ:
        return os.environ[name] or None
    for path in DOTENV_PATHS:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for raw in lines:
            line = raw.strip()
            if line.startswith("export "):
                line = line[7:].lstrip()
            key, separator, value = line.partition("=")
            if separator != "=" or key.strip() != name:
                continue
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                value = value[1:-1]
            return value or None
    return None


def mcp_servers(brains=None) -> dict:
    """The research boundary, declared here rather than inherited.

    The obvious wiring is `setting_sources=["project"]` plus a `.mcp.json` at
    the repo root, and it is what this port used first. It is wrong for a folder
    that claims to be standalone. `.mcp.json` holds an API key, so it is
    routinely gitignored, and it is gitignored in this repo: a fresh clone, a
    worktree, or an attendee's checkout has no such file, and the researcher
    silently loses both servers with no error anywhere.

    Declaring them here, with `strict_mcp_config`, means the tool boundary is
    exactly what this folder says it is and does not change because of a file
    somewhere above it.

    Perplexity appears only when its key is set. A server started with an empty
    key answers every question with an auth error, which reads downstream as a
    topic nobody has written about.

    The corpus server is always present. It is in-process and read-only. An
    empty root list returns no hits; it does not fail the session.
    """
    servers: dict = {
        "context7": {"type": "http", "url": "https://mcp.context7.com/mcp"},
        "corpus": corpus_mcp_server(brains or []),
    }
    key = environment_value("PERPLEXITY_API_KEY")
    if key:
        servers["perplexity"] = {
            "type": "stdio",
            "command": "npx",
            # The official Perplexity MCP exposes `perplexity_search` and
            # `perplexity_ask`, including `search_domain_filter`.  `-q` keeps
            # npx installation chatter off stdout, where it would corrupt the
            # stdio JSON-RPC protocol on a first run.
            "args": ["-yq", "@perplexity-ai/mcp-server"],
            "env": {"PERPLEXITY_API_KEY": key},
        }
    return servers


def corpus_mcp_server(brains) -> object:
    """In-process MCP server. Search only. No write path on purpose."""
    from claude_agent_sdk import create_sdk_mcp_server, tool  # noqa: PLC0415

    import corpus as corpus_mod  # noqa: PLC0415

    roots = [Path(path) for path in (brains or [])]

    @tool(
        "corpus_search",
        "Search the configured research corpus. Read-only. Call this before live search.",
        {"query": str, "limit": int},
    )
    async def corpus_search(args):
        hits = corpus_mod.search(
            args.get("query") or "",
            roots,
            limit=int(args.get("limit") or 20),
        )
        return {"content": [{"type": "text", "text": corpus_mod.format_hits(hits)}]}

    return create_sdk_mcp_server(name="corpus", version="1.0.0", tools=[corpus_search])


def local_plugins() -> list[dict[str, str]]:
    """Plugins owned by this standalone folder, in deterministic order.

    The research cast is always present.  `task setup` installs the two image
    plugins under `.cache/`; include each only when its Claude plugin manifest
    exists so table and unit-test commands still work before setup.  No path in
    this list depends on `~/.claude` or another checkout.
    """
    plugins = [{"type": "local", "path": str(PLUGIN)}]
    for path in (IMAGEN_DIAGRAMS_PLUGIN, IMAGE_GEN_PLUGIN):
        if (path / ".claude-plugin" / "plugin.json").is_file():
            plugins.append({"type": "local", "path": str(path)})
    return plugins


def local_image_skills() -> list[str]:
    """The exact plugin-qualified image skills installed by ``task setup``.

    A non-empty SDK ``skills`` list is both discovery policy and tool policy.
    Keep it exact so the image plugins are available without also exposing the
    research-loop skill as a second orchestrator.
    """
    skills = []
    for path, name in (
        (IMAGEN_DIAGRAMS_PLUGIN, "imagen-diagrams:imagen-diagrams"),
        (IMAGE_GEN_PLUGIN, "image-gen:image-gen"),
    ):
        if (path / ".claude-plugin" / "plugin.json").is_file():
            skills.append(name)
    return skills


def agent_name(role_name: str) -> str:
    """The plugin agent file that holds this role's prompt."""
    return f"research-{role_name.replace('_', '-')}"


def _relative(root: Path, raw: str) -> str | None:
    """The path this tool call would write, relative to the work directory."""
    try:
        return str(PurePosixPath(Path(raw).resolve().relative_to(root.resolve())))
    except ValueError:
        return None


def _deny(who: str, allow: tuple[str, ...] | list[str], where: str) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                f"{who} may write {', '.join(allow) or 'nothing'}. {where} is outside that scope."
            ),
        }
    }


def scope_hook(root: Path, roles: dict[str, RolePlan]):
    """A PreToolUse hook that denies a write outside the calling role's scope.

    Returning an empty dict means "no opinion", which lets the call through.
    Denying needs the full `hookSpecificOutput` shape, so a typo here fails
    open. That is why the tests assert the deny envelope key by key.
    """
    by_agent = {agent_name(role.name): role for role in roles.values()}

    async def check(input_data, tool_use_id, context):
        if input_data["tool_name"] not in WRITE_TOOL_NAMES:
            return {}
        raw = next(
            (input_data["tool_input"][key] for key in PATH_KEYS if key in input_data["tool_input"]),
            None,
        )
        if raw is None:
            return {}

        # `agent_type` is absent on the main thread. The orchestrator holds only
        # `Agent`, so a write arriving without an agent is either the parent
        # breaking its contract or a subagent nobody configured. Deny both
        # rather than guess which.
        role = by_agent.get(input_data.get("agent_type") or "")
        if role is None:
            return _deny("the orchestrator", (), str(raw))

        scope = WriteScope(allow=list(role.allow), deny=list(role.deny))
        relative = _relative(root, raw)
        if relative is not None and scope.permits(relative):
            return {}
        # A path outside the work directory is never in scope. Letting it
        # through because it did not match the allow list is the fail-open bug.
        where = relative or f"{raw} (outside the work directory)"
        return _deny(role.name, role.allow, where)

    return check


def agent_definitions(roles: dict[str, RolePlan]):
    """One `AgentDefinition` per role, with the prompt read from the plugin.

    The role table is authoritative on tools. When an agent file and the table
    disagree, that is drift, and drift in a tool list is how a reader quietly
    becomes a writer. Raising here beats finding it in a diff.
    """
    from claude_agent_sdk import AgentDefinition  # noqa: PLC0415  (optional dependency)

    files = agent_files()
    agents = {}
    for role in roles.values():
        if role.name == "orchestrator":
            continue
        name = agent_name(role.name)
        source = files.get(name)
        if source is None:
            raise FileNotFoundError(f"{name}.md is missing from {PLUGIN / 'agents'}")
        if sorted(source["tools"]) != sorted(role.tools):
            raise ValueError(
                f"{name}.md declares {sorted(source['tools'])} but the role table "
                f"says {sorted(role.tools)}. Fix one of them."
            )
        agents[name] = AgentDefinition(
            description=source["description"],
            prompt=source["prompt"],
            tools=list(role.tools),
            # camelCase on purpose. `max_turns=` raises TypeError on the real
            # SDK and is swallowed by the fake used in tests.
            disallowedTools=NO_WRITE if not role.can_write else [],
            maxTurns=DEFAULT_MAX_TURNS,
            background=False,
            **(
                {"model": role.model} if role.model else {}
            ),
            **(
                {"effort": role.effort} if role.effort else {}
            ),
        )

    return agents


def options_for(work_dir: Path | str, *, max_usd: float | None = None, loop: str = LOOP, brains=None):
    """Build `ClaudeAgentOptions` with one subagent per role in the cast.

    `work_dir` is the run's own directory, not a repo clone. A research run has
    no target checkout, so `cwd` is where the paper is being built and the write
    scopes are relative to it.

    Imported lazily. This folder's tests run with no SDK installed.
    """
    from claude_agent_sdk import ClaudeAgentOptions, HookMatcher  # noqa: PLC0415

    root = Path(work_dir).resolve()
    roles = plan(None, loop)

    hook = scope_hook(root, roles)
    hooks = [HookMatcher(matcher=tool, hooks=[hook]) for tool in WRITE_TOOL_NAMES]

    # `allowed_tools` is a session-wide permission allowlist, and it gates a
    # subagent's calls as well as the parent's. It is not the parent's tool
    # list, which is the reading that broke the first live run: with
    # `allowed_tools=["Agent"]` and `dontAsk`, the researcher had Perplexity,
    # Context7, and WebSearch in its own list and every one of them came back
    # denied. It reported that honestly and produced no claims, which is the
    # anti-fabrication contract working and the wiring not.
    #
    # So this is the union of what the cast holds. Each role is still narrowed
    # by its own `tools` list, and the parent is still kept from writing, by the
    # PreToolUse hook that denies any write arriving without an `agent_type`.
    allowed = sorted({tool for role in roles.values() for tool in role.tools} | set(SPAWN_TOOLS))

    return ClaudeAgentOptions(
        cwd=str(root),
        agents=agent_definitions(roles),
        allowed_tools=allowed,
        disallowed_tools=GLOBAL_DENY,
        permission_mode="dontAsk",
        hooks={"PreToolUse": hooks},
        # The two lines that give the researcher and the verifier their search
        # tools. `strict_mcp_config` means these are the only servers in the
        # run, so a machine with a broken or extra server in its own config
        # cannot change what this folder can reach.
        mcp_servers=mcp_servers(brains),
        strict_mcp_config=True,
        # The plugin is what makes the agent markdown visible, because `cwd`
        # is the work directory and not this folder. Enable only the two image
        # skills when setup installed them. The research-loop skill stays on
        # disk as the readable specification and is deliberately not loaded: a
        # parent that can invoke it is a second orchestrator.
        plugins=local_plugins(),
        skills=local_image_skills(),
        # Plugin paths above are explicit. Do not also discover settings or
        # skills from this machine's ~/.claude or from a parent checkout.
        setting_sources=[],
        system_prompt=PARENT_PROMPT,
        max_turns=DEFAULT_MAX_TURNS,
        max_budget_usd=max_usd,
        env={"CLAUDE_AGENT_SDK_DISABLE_BUILTIN_AGENTS": "1"},
    )
