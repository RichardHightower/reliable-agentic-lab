"""The role table, in one place, in a form any runtime can read.

Three runtimes enforce write scope three different ways. Plain Python uses a
missing method. The Claude Agent SDK uses a tool list and a PreToolUse hook.
Deep Agents uses a per-subagent tool list. All three read the same table, which
comes from `.loop.yml` in the target repo.

If the table and a runtime ever disagree, the runtime is wrong. That is what
`loops/tests/test_runtime_ports.py` checks, and it checks it without either SDK
installed.
"""

from __future__ import annotations

from dataclasses import dataclass

# Tools that can change a file. A role holding none of these cannot write.
WRITE_TOOLS = ("Edit", "Write", "NotebookEdit")
READ_TOOLS = ("Read", "Glob", "Grep")


@dataclass(frozen=True)
class RolePlan:
    """One role, described the same way for every runtime."""

    name: str
    purpose: str
    tools: tuple[str, ...]
    allow: tuple[str, ...] = ()
    deny: tuple[str, ...] = ()

    @property
    def can_write(self) -> bool:
        return any(tool in WRITE_TOOLS for tool in self.tools)


PURPOSE = {
    "orchestrator": "Owns the budget and the order. Writes nothing.",
    "planner": "Writes steps.jsonl. Runs in its own context and returns a summary.",
    "test_implementer": "Writes the failing tests. Nothing else.",
    "code_implementer": "Writes the code until the tests pass. Cannot touch tests.",
    "judge": "Scores the attempt. Reads reports and the diff. Holds no write path.",
}


def plan(contract) -> dict[str, RolePlan]:
    """Read `.loop.yml` and describe every role once."""

    def scope(name: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
        config = contract.role(name)
        return (
            tuple(config.get("write_allow") or []),
            tuple(config.get("write_deny") or []),
        )

    roles: dict[str, RolePlan] = {
        "orchestrator": RolePlan(
            name="orchestrator",
            purpose=PURPOSE["orchestrator"],
            tools=("Task",),
        ),
        "judge": RolePlan(
            name="judge",
            purpose=PURPOSE["judge"],
            # No Edit and no Write. The separation is the tool list, not a rule.
            tools=(*READ_TOOLS, "Bash"),
        ),
    }
    for name in ("planner", "test_implementer", "code_implementer"):
        allow, deny = scope(name)
        roles[name] = RolePlan(
            name=name,
            purpose=PURPOSE[name],
            tools=(*READ_TOOLS, "Edit", "Write", "Bash"),
            allow=allow,
            deny=deny,
        )
    return roles


def table(roles: dict[str, RolePlan]) -> str:
    """The role table as text, for a slide or a run header."""
    lines = [f"{'role':<18}{'writes':<8}scope"]
    for role in roles.values():
        scope = ", ".join(role.allow) or "nothing"
        if role.deny:
            scope += f"   (denied: {', '.join(role.deny)})"
        lines.append(f"{role.name:<18}{'yes' if role.can_write else 'no':<8}{scope}")
    return "\n".join(lines)
