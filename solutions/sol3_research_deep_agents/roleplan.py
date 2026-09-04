"""The role table, in one place, in a form any runtime can read.

Three runtimes enforce write scope three different ways. Plain Python uses a
missing method. The Claude Agent SDK uses a tool list and a PreToolUse hook.
Deep Agents uses a per-subagent tool list. All three read the same table, which
comes from `.loop.yml` in the target repo.

Four loops, four casts. The implementer needs five roles. The fixer needs three.
The table below is the only place that difference is written down, so a runtime
never gets to invent a role or widen a scope.

If the table and a runtime ever disagree, the runtime is wrong. That is what
This folder's own tests check the cast, without either SDK
installed.
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
    # The white paper cast. Each one earns its separation by holding a
    # different tool list. A role that would hold the same tools as its
    # neighbour is not a role, it is a prompt, and it belongs in a skill.
    "paper": (
        "orchestrator",
        "planner",
        "outline_judge",
        "researcher",
        "verifier",
        "section_judge",
        "ledger",
        "diagrammer",
        "chartist",
        "writer",
        "reviewer",
    ),
}

DEFAULT_LOOP = "research"

PURPOSE = {
    "orchestrator": "Owns the budget and the order. Writes nothing.",
    "doer": "Edits the ticket body. Nothing else in the repo.",
    "planner": "Writes steps.jsonl. Runs in its own context and returns a summary.",
    "test_implementer": "Writes the failing tests. Nothing else.",
    "code_implementer": "Writes the code until the tests pass. Cannot touch tests.",
    "researcher": "Calls the tool boundary and returns findings. Writes nothing.",
    "writer": "Assembles the brief from the findings. Writes the brief and nothing else.",
    "judge": "Scores the attempt. Reads reports and the diff. Holds no write path.",
    "verifier": (
        "Cross-checks each important claim against a second, independent source. "
        "Writes evidence records. Cannot touch the paper."
    ),
    "diagrammer": (
        "Draws mermaid and plantuml sources for the concepts the plan flagged. "
        "Writes diagram sources only, so it cannot put a claim into the prose."
    ),
    "chartist": (
        "Returns a chart spec from data tables. Python renders the pixels. "
        "Holds no write path."
    ),
    "reviewer": (
        "Grades the draft against the rubric and returns verdicts. "
        "Holds no write path, so it cannot fix its own complaint."
    ),
    "outline_judge": (
        "Scores the outline before any research spend. Holds no write path."
    ),
    "section_judge": (
        "Grades one section against its outline row. Holds no write path."
    ),
    "ledger": (
        "Extracts facts and terms from one finished section. Holds no write path. "
        "Python appends the ledger."
    ),
}

# Roles that hold no tool that writes. The separation is the tool list, not a
# rule in a prompt, so there is nothing for a model to talk its way past.
READERS = (
    "orchestrator",
    "judge",
    "researcher",
    "reviewer",
    "outline_judge",
    "section_judge",
    "ledger",
    "chartist",
)

TOOLS_FOR_READER = {
    "orchestrator": ("Task",),
    "judge": (*READ_TOOLS, "Bash"),
    "researcher": (*READ_TOOLS, "WebSearch"),
    "reviewer": (*READ_TOOLS,),
    "outline_judge": (*READ_TOOLS,),
    "section_judge": (*READ_TOOLS,),
    "ledger": (*READ_TOOLS,),
    "chartist": (*READ_TOOLS,),
}

# Where a role may write when `.loop.yml` says nothing about it. A target repo
# declares scope for the implementer's roles. It has never heard of the others.
# Anything absent from both falls to "writes nothing", which is the safe way to
# be wrong.
FALLBACK_SCOPE = {
    "doer": (("tickets/**",), ()),
    # The writer owns the prose and nothing else. It cannot write an evidence
    # record, which is what stops it inventing a source to cite.
    "writer": (("brief.md", "paper/**", "work/research/**", "sections/**"), ("evidence/**",)),
    # The planner owns the plan. The verifier owns the evidence. The diagrammer
    # owns diagram source and not one rendered figure, because a figure is the
    # renderer's output and a role that can write one can fake one.
    "planner": (("plan.json",), ()),
    "verifier": (("evidence/**",), ("paper/**",)),
    "diagrammer": (("diagrams/*.mmd", "diagrams/*.puml"), ("paper/**", "evidence/**")),
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
