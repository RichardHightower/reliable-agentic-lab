"""The roles, as Claude Agent SDK subagents loaded from the plugin.

Same files as `solutions/sol1_enhancer/.claude/agents/`. Same skill as
`.claude/skills/enhancer-loop/`. The SDK adds precision the plugin cannot:

    tools=[...]              the front matter list, not a union on the parent
    disallowedTools          Bash is gone from both agents
    background=False         wait for the verdict (SDK 2.1.198 defaults to bg)
    maxTurns                 camelCase, the real SDK field
    max_turns / max_budget_usd
                             the query ends on turns, cost, or a final message
    output_format            the judge returns validated JSON
    allowed_tools=["Agent"]  the parent cannot skip the subagent and write

The Agent SDK scopes in two places, and you still need both.

    tools=[...]        decides whether a role can write at all
    PreToolUse hook    decides which paths it may write

The judge and the doer both hold no Edit and no Write, matching the plugin.
Python writes the candidate. The hook is still there so a leaked Write fails
closed instead of writing `app/`.

Nothing here calls a model. `options_for` returns configuration, and
`loop.py` is what runs it.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from load_agents import DEFAULT_MAX_TURNS, PARENT_PROMPT, PLUGIN, agent_files
from roleplan import DEFAULT_LOOP, RolePlan, plan
from write_scope import WriteScope

PATH_KEYS = ("file_path", "path", "notebook_path")

# The plugin agents never hold a shell. A Bash call is how a Read-only agent
# writes anyway.
NO_SHELL = ["Bash"]
NO_WRITE = ["Edit", "Write", "NotebookEdit", "Bash"]


def _relative(repo: Path, raw: str) -> str | None:
    """The path this tool call would write, relative to the target repo."""
    try:
        return str(PurePosixPath(Path(raw).resolve().relative_to(repo.resolve())))
    except ValueError:
        return None


def scope_hook(repo: Path, role: RolePlan):
    """A PreToolUse hook that denies a write outside this role's scope.

    Returning an empty dict means "no opinion", which lets the call through.
    Denying needs the full hookSpecificOutput shape, so a typo here fails open.
    That is why `tests/test_roles.py` asserts the deny shape key by key.
    """
    scope = WriteScope(allow=list(role.allow), deny=list(role.deny))

    async def check(input_data, tool_use_id, context):
        if input_data["tool_name"] not in ("Edit", "Write", "NotebookEdit"):
            return {}
        raw = next(
            (input_data["tool_input"][k] for k in PATH_KEYS if k in input_data["tool_input"]),
            None,
        )
        if raw is None:
            return {}
        relative = _relative(repo, raw)
        if relative is not None and scope.permits(relative):
            return {}
        where = relative or f"{raw} (outside the target repo)"
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    f"{role.name} may write {', '.join(role.allow) or 'nothing'}. "
                    f"{where} is outside that scope."
                ),
            }
        }

    return check


def _budget_usd(contract) -> float | None:
    try:
        value = (contract.budget or {}).get("usd")
        return float(value) if value is not None else None
    except (TypeError, ValueError, AttributeError):
        return None


def options_for(contract, loop: str = DEFAULT_LOOP):
    """Build `ClaudeAgentOptions` from the plugin agents, with SDK precision.

    Imported lazily. The workshop's own tests run without the SDK installed.
    """
    from claude_agent_sdk import (  # noqa: PLC0415  (optional dependency)
        AgentDefinition,
        ClaudeAgentOptions,
        HookMatcher,
    )

    repo = Path(contract.repo)
    roles = plan(contract, loop)
    files = agent_files() if loop == "enhancer" else {}
    enhancer = loop == "enhancer"

    agents = {}
    for role in roles.values():
        if role.name == "orchestrator":
            continue
        plugin_name = f"enhancer-{role.name}" if enhancer else role.name.replace("_", "-")
        source = files.get(plugin_name) or files.get(role.name.replace("_", "-"))
        tools = list(source["tools"]) if source else list(role.tools)
        if enhancer:
            tools = [tool for tool in tools if tool not in NO_WRITE]
            if role.name == "doer":
                # Explore is a built-in read-only subagent. Python still owns
                # every candidate and real-ticket write.
                tools.append("Agent")
        prompt = source["prompt"] if source else f"You are the {role.name}. {role.purpose}"
        description = source["description"] if source else role.purpose
        name = source["name"] if source else plugin_name
        agents[name] = AgentDefinition(
            description=description,
            prompt=prompt,
            tools=tools,
            disallowedTools=NO_WRITE if enhancer or not role.can_write else NO_SHELL,
            maxTurns=DEFAULT_MAX_TURNS,
            background=False,
            model="sonnet",
        )

    writers = [role for role in roles.values() if role.can_write]
    hooks = [
        HookMatcher(matcher=tool, hooks=[scope_hook(repo, role)])
        for role in writers
        for tool in ("Edit", "Write", "NotebookEdit")
    ]

    kwargs = dict(
        cwd=str(repo),
        agents=agents,
        permission_mode="dontAsk",
        hooks={"PreToolUse": hooks},
        setting_sources=["project"],
        max_turns=DEFAULT_MAX_TURNS,
        max_budget_usd=_budget_usd(contract),
        # The parent only has Agent. The adapter selects one ticket-shaped
        # child result instead of concatenating an event stream.
        forward_subagent_text=True,
    )
    if enhancer:
        kwargs.update(
            allowed_tools=["Agent"],
            disallowed_tools=NO_WRITE,
            plugins=[{"type": "local", "path": str(PLUGIN)}],
            system_prompt=PARENT_PROMPT,
        )
    else:
        kwargs["allowed_tools"] = sorted(
            {tool for role in roles.values() for tool in role.tools}
        )

    return ClaudeAgentOptions(**kwargs)
