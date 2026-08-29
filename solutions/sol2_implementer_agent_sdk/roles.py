"""The five roles, as Claude Agent SDK subagents.

The Agent SDK enforces scope in two places, and you need both.

    tools=[...]        decides whether a role can write at all
    PreToolUse hook    decides which paths it may write

The orchestrator and the judge hold no `Edit` and no `Write`, so for them
there is nothing for a hook to guard. The planner, the test implementer, and
the code implementer each hold both, and the hook is what keeps each one
inside its own directory.

One hook serves the whole cast, not one hook per writer. Registering one per
writing role is how this port used to do it, and with three writers it does
not hold: every hook runs on every `Write`, an empty dict means "no opinion",
and the first role that shrugs lets another role's write through. The code
implementer writing `tests/test_x.py` was denied by its own hook and waved
through by the test implementer's, so the effective scope was the union of all
three allow lists. The separation this whole folder teaches did not survive a
real run.

This hook reads `agent_type` off the tool call instead, which the SDK
populates whenever the call comes from inside a spawned subagent, and looks up
that role's scope. A write with no `agent_type` came from the parent, and the
parent has no business writing anything.

Nothing here calls a model. `options_for` returns configuration, and a driver
is what runs it.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from load_agents import DEFAULT_MAX_TURNS, PARENT_PROMPT, PLUGIN, agent_files
from roleplan import DEFAULT_LOOP, RolePlan, plan
from write_scope import WriteScope

# Tool inputs that name a path. A hook has to know where to look.
PATH_KEYS = ("file_path", "path", "notebook_path")

WRITE_TOOL_NAMES = ("Edit", "Write", "NotebookEdit")

# Both names for "spawn a subagent". The CLI calls it `Task`, and some SDK
# versions expose it as `Agent`. Allowing a name that does not exist costs
# nothing. Allowing neither costs the whole run.
SPAWN_TOOLS = ("Task", "Agent")

# Tools a reader must never hold, restated on the AgentDefinition itself. The
# tool list is the allow side. This is the deny side, and having both means a
# widened list still fails closed.
NO_WRITE = ["Edit", "Write", "NotebookEdit", "Bash"]

# No role in this cast holds a shell, so deny it once at the top rather than
# rely on five tool lists all continuing to omit it. A shell is the path around
# the hook: it matches Edit, Write, and NotebookEdit, and none of those is
# `sed -i`.
GLOBAL_DENY = ["Bash"]


def agent_name(role_name: str) -> str:
    """The plugin agent file that holds this role's prompt."""
    return f"implementer-{role_name.replace('_', '-')}"


def _relative(repo: Path, raw: str) -> str | None:
    """The path this tool call would write, relative to the target repo."""
    try:
        return str(PurePosixPath(Path(raw).resolve().relative_to(repo.resolve())))
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


def scope_hook(repo: Path, roles: dict[str, RolePlan]):
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

        # `agent_type` is absent on the main thread. The orchestrator holds
        # only the spawn tool, so a write arriving without an agent is either
        # the parent breaking its contract or a subagent nobody configured.
        # Deny both rather than guess which.
        role = by_agent.get(input_data.get("agent_type") or "")
        if role is None:
            return _deny("the orchestrator", (), str(raw))

        scope = WriteScope(allow=list(role.allow), deny=list(role.deny))
        relative = _relative(repo, raw)
        if relative is not None and scope.permits(relative):
            return {}
        # A path outside the target repo is never in scope. Letting it through
        # because it did not match the allow list is the fail-open bug.
        where = relative or f"{raw} (outside the target repo)"
        return _deny(role.name, role.allow, where)

    return check


def agent_definitions(roles: dict[str, RolePlan], *, max_turns: int = DEFAULT_MAX_TURNS):
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
            # SDK and is swallowed by a fake that takes `**kwargs`.
            disallowedTools=NO_WRITE if not role.can_write else [],
            maxTurns=max_turns,
            # SDK 2.1.198 defaults a subagent to background. The driver needs
            # the verdict, so wait for it.
            background=False,
        )
    return agents


def options_for(
    contract,
    loop: str = DEFAULT_LOOP,
    *,
    max_usd: float | None = None,
    max_turns: int = DEFAULT_MAX_TURNS,
    role_names: frozenset[str] | None = None,
):
    """Build `ClaudeAgentOptions` with one subagent per role in this loop's cast.

    Imported lazily. This folder's tests run without the SDK installed.
    """
    from claude_agent_sdk import ClaudeAgentOptions, HookMatcher  # noqa: PLC0415

    repo = Path(contract.repo)
    roles = plan(contract, loop)
    if role_names is not None:
        unknown = role_names - set(roles)
        if unknown:
            raise ValueError(f"unknown Agent SDK role(s): {sorted(unknown)}")
        roles = {name: role for name, role in roles.items() if name in role_names}

    hook = scope_hook(repo, roles)
    hooks = [HookMatcher(matcher=tool, hooks=[hook]) for tool in WRITE_TOOL_NAMES]

    # `allowed_tools` is a session-wide permission allowlist, and it gates a
    # subagent's calls as well as the parent's. It is not the parent's tool
    # list. Each role is still narrowed by its own `tools`, and the parent is
    # kept from writing by the hook rather than by this list.
    allowed = sorted({tool for role in roles.values() for tool in role.tools} | set(SPAWN_TOOLS))

    return ClaudeAgentOptions(
        cwd=str(repo),
        agents=agent_definitions(roles, max_turns=max_turns),
        allowed_tools=allowed,
        disallowed_tools=GLOBAL_DENY,
        permission_mode="dontAsk",
        hooks={"PreToolUse": hooks},
        # A subagent inherits the project's MCP servers only with this set.
        setting_sources=["project"],
        plugins=[{"type": "local", "path": str(PLUGIN)}],
        system_prompt=PARENT_PROMPT,
        max_turns=max_turns,
        max_budget_usd=max_usd if max_usd is not None else _budget_usd(contract),
        # The built-in general-purpose agent ships with filesystem tools.
        # Leaving it enabled is how a scoped implementer edits a test.
        env={"CLAUDE_AGENT_SDK_DISABLE_BUILTIN_AGENTS": "1"},
    )


def _budget_usd(contract) -> float | None:
    """The cost ceiling from `.loop.yml`, when the target repo declares one."""
    try:
        value = contract.budget.get("usd")
    except AttributeError:
        return None
    return float(value) if value is not None else None
