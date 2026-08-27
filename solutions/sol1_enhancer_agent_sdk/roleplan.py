"""The role table, in one place, in a form any runtime can read.

Three runtimes enforce write scope three different ways. Plain Python uses a
missing method. The Claude Agent SDK uses a tool list and a PreToolUse hook.
Deep Agents uses a per-subagent tool list. All three read the same table, which
comes from `.loop.yml` in the target repo.

Four loops, four casts. The implementer needs five roles. The fixer needs three.
The table below is the only place that difference is written down, so a runtime
never gets to invent a role or widen a scope.

If the table and a runtime ever disagree, the runtime is wrong. That is what
this folder's `tests/test_roleplan.py` and `tests/test_loop.py` check, and they
check it without either SDK installed.
"""

from __future__ import annotations

from dataclasses import dataclass

# Tools that can change a file. A role holding none of these cannot write.
WRITE_TOOLS = ("Edit", "Write", "NotebookEdit")
READ_TOOLS = ("Read", "Glob", "Grep")

# One cast per loop, in the order the loop uses them.
LOOPS = {
    "enhancer": ("orchestrator", "doer", "judge"),
    "implementer": (
        "orchestrator",
        "planner",
        "test_implementer",
        "code_implementer",
        "judge",
    ),
    "research": ("orchestrator", "researcher", "writer", "judge"),
    "fixer": ("orchestrator", "code_implementer", "judge"),
}

DEFAULT_LOOP = "implementer"

PURPOSE = {
    "orchestrator": "Owns the budget and the order. Writes nothing.",
    "doer": "Edits the ticket body. Nothing else in the repo.",
    "planner": "Writes steps.jsonl. Runs in its own context and returns a summary.",
    "test_implementer": "Writes the failing tests. Nothing else.",
    "code_implementer": "Writes the code until the tests pass. Cannot touch tests.",
    "researcher": "Calls the tool boundary and returns findings. Writes nothing.",
    "writer": "Assembles the brief from the findings. Writes the brief and nothing else.",
    "judge": "Scores the attempt. Reads reports and the diff. Holds no write path.",
}

# Roles that hold no tool that writes. The separation is the tool list, not a
# rule in a prompt, so there is nothing for a model to talk its way past.
READERS = ("orchestrator", "judge", "researcher")

TOOLS_FOR_READER = {
    "orchestrator": ("Task",),
    "judge": (*READ_TOOLS, "Bash"),
    "researcher": (*READ_TOOLS, "WebSearch"),
}

# Where a role may write when `.loop.yml` says nothing about it. A target repo
# declares scope for the implementer's roles. It has never heard of the others.
# Anything absent from both falls to "writes nothing", which is the safe way to
# be wrong.
FALLBACK_SCOPE = {
    "doer": (("tickets/**",), ()),
    "writer": (("brief.md", "work/research/**"), ()),
}
NO_WRITE_SCOPE = ((), ("**",))


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


def _scope(contract, name: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """What `.loop.yml` says about this role, or the fallback when it is silent.

    `contract.role()` fails closed for a name it does not know, which is right
    for the loops it was written for and wrong for a role it has never seen.
    Reading `config` directly is how we tell "declared as empty" apart from
    "never mentioned".
    """
    declared = contract.config["roles"] if contract is not None else {}
    if name in declared:
        config = declared[name]
        return (
            tuple(config.get("write_allow") or ()),
            tuple(config.get("write_deny") or ()),
        )
    return FALLBACK_SCOPE.get(name, NO_WRITE_SCOPE)


def plan(contract, loop: str = DEFAULT_LOOP) -> dict[str, RolePlan]:
    """Describe every role in one loop's cast, once.

    `contract` may be None. The research loop runs against a question, not a
    repo, so it has no `.loop.yml` to read.
    """
    if loop not in LOOPS:
        raise ValueError(f"unknown loop {loop!r}. Known: {', '.join(sorted(LOOPS))}")

    roles: dict[str, RolePlan] = {}
    for name in LOOPS[loop]:
        if name in READERS:
            roles[name] = RolePlan(
                name=name,
                purpose=PURPOSE[name],
                tools=TOOLS_FOR_READER[name],
            )
            continue
        allow, deny = _scope(contract, name)
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
