"""The five roles, as Claude Agent SDK subagents.

The Agent SDK enforces scope in two places, and you need both.

    tools=[...]        decides whether a role can write at all
    PreToolUse hook    decides which paths it may write

The judge holds no `Edit` and no `Write`, so there is nothing for a hook to
guard. The code implementer holds both, so the hook is what keeps it out of
`tests/**`.

Nothing here calls a model. `options_for` returns configuration, and
`implementer.py` is what runs it.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from roleplan import DEFAULT_LOOP, RolePlan, plan
from write_scope import WriteScope

# Tool inputs that name a path. A hook has to know where to look.
PATH_KEYS = ("file_path", "path", "notebook_path")


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
    That is why `test_runtime_ports.py` asserts the deny shape directly.
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
        # A path outside the target repo is never in scope. Letting it through
        # because it did not match the allow list is the fail-open bug.
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


def options_for(contract, loop: str = DEFAULT_LOOP):
    """Build `ClaudeAgentOptions` with one subagent per role in this loop's cast.

    Imported lazily. The workshop's own tests run without the SDK installed.
    """
    from claude_agent_sdk import (  # noqa: PLC0415  (optional dependency)
        AgentDefinition,
        ClaudeAgentOptions,
        HookMatcher,
    )

    repo = Path(contract.repo)
    roles = plan(contract, loop)

    agents = {
        role.name.replace("_", "-"): AgentDefinition(
            description=role.purpose,
            prompt=f"You are the {role.name}. {role.purpose}",
            tools=list(role.tools),
            max_turns=12,
        )
        for role in roles.values()
        if role.name != "orchestrator"
    }

    hooks = [
        HookMatcher(matcher=tool, hooks=[scope_hook(repo, role)])
        for role in roles.values()
        if role.can_write
        for tool in ("Edit", "Write", "NotebookEdit")
    ]

    return ClaudeAgentOptions(
        cwd=str(repo),
        agents=agents,
        # Derived, not restated. A loop whose cast holds WebSearch needs it in
        # this list, and a loop whose cast writes nothing must not get Write.
        allowed_tools=sorted({tool for role in roles.values() for tool in role.tools}),
        permission_mode="dontAsk",
        hooks={"PreToolUse": hooks},
        # A subagent inherits the project's MCP servers only with this set.
        setting_sources=["project"],
    )
