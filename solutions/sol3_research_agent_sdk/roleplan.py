"""The role table, in one place, in a form any runtime can read.

Three runtimes enforce write scope three different ways. Plain Python uses a
missing method. The Claude Agent SDK uses a tool list and a PreToolUse hook.
Deep Agents uses a per-subagent tool list. All three read the same table.

Four loops, four casts. The research cast is the largest, at ten roles. A
role earns a line here by holding a tool set no other role holds, never by
being another name for work an existing role already does. The researcher
searches and cannot write. The verifier searches a second time and never sees
the researcher's answer. The diagrammer returns figure source; Python writes
it and runs the renderer. No role in this table holds `Bash`.

If the table and a runtime ever disagree, the runtime is wrong. This folder's
own tests check the cast with no SDK installed.
"""

from __future__ import annotations

from dataclasses import dataclass

# Tools that can change a file. A role holding none of these cannot write.
WRITE_TOOLS = ("Edit", "Write", "NotebookEdit")
READ_TOOLS = ("Read", "Glob", "Grep")

# The research boundary, as the MCP server names the coding agent sees. A role
# without these in its list cannot reach the outside world, whatever its prompt
# says it should do.
SEARCH_TOOLS = (
    "WebSearch",
    "mcp__corpus__corpus_search",
    "mcp__perplexity__perplexity_search",
    "mcp__perplexity__perplexity_ask",
    "mcp__context7__resolve-library-id",
    "mcp__context7__query-docs",
)

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
    "research": (
        "orchestrator",
        "outliner",
        "outline_judge",
        "researcher",
        "verifier",
        "section_judge",
        "ledger",
        "diagrammer",
        "writer",
        "judge",
    ),
    "fixer": ("orchestrator", "code_implementer", "judge"),
}

DEFAULT_LOOP = "implementer"

PURPOSE = {
    "orchestrator": "Owns the budget and the order. Writes nothing.",
    "doer": "Edits the ticket body. Nothing else in the repo.",
    "planner": "Writes steps.jsonl. Runs in its own context and returns a summary.",
    "outliner": "Turns the topic into a two-level outline. Returns it; Python writes the file.",
    "outline_judge": "Scores the outline. Reads it and returns a verdict. Holds no write path.",
    "test_implementer": "Writes the failing tests. Nothing else.",
    "code_implementer": "Writes the code until the tests pass. Cannot touch tests.",
    "researcher": "Calls the corpus first, then the live tool boundary, and returns findings. Writes nothing.",
    "verifier": "Checks a claim against the corpus and a second live source. Writes nothing.",
    "section_judge": "Grades one section against its outline row. Holds no write path.",
    "ledger": "Extracts the section's facts and terms. Python appends the ledger. Holds no write path.",
    "diagrammer": "Draws the figures and runs the renderer. Writes diagrams only.",
    "writer": "Assembles the paper from verified claims. Writes prose only.",
    "judge": "Scores the attempt. Reads reports and the diff. Holds no write path.",
}

# Roles that hold no tool that writes. The separation is the tool list, not a
# rule in a prompt, so there is nothing for a model to talk its way past.
READERS = (
    "orchestrator",
    "judge",
    "researcher",
    "verifier",
    "outliner",
    "outline_judge",
    "section_judge",
    "ledger",
)

TOOLS_FOR_READER = {
    "orchestrator": ("Task",),
    "judge": (*READ_TOOLS, "Bash"),
    "researcher": (*READ_TOOLS, "WebSearch"),
    "verifier": ("Read", *SEARCH_TOOLS),
    "outliner": READ_TOOLS,
    "outline_judge": READ_TOOLS,
    "section_judge": READ_TOOLS,
    "ledger": ("Read",),
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

# Where one loop needs a role to differ from the tables above. The key is
# (loop, role) and the value names only the fields that change.
#
# An override that names `allow` must also name `deny`. The fallback for an
# undeclared role is "deny everything", and deny beats allow in `WriteScope`,
# so an override that sets only `allow` produces a role that looks scoped in
# the table and can write nothing at all.
#
# Two roles share a name across casts and mean different things. The
# implementer's planner writes `steps.jsonl` against a repo. The research
# outliner returns an outline against a topic. Overriding here is how a
# research role stays in one table without inheriting another loop's write
# scope.
OVERRIDES: dict[tuple[str, str], dict] = {
    ("research", "outliner"): {
        "purpose": "Turns the topic into a two-level outline. Returns it; Python writes the file.",
        # No write tool. The outline comes back as schema-checked structured
        # output and Python writes `outline.json` from it.
        "tools": READ_TOOLS,
        "allow": (),
        "deny": ("**",),
        "model": "claude-sonnet-5",
    },
    ("research", "outline_judge"): {
        "purpose": "Scores the outline. Reads it and returns a verdict. Holds no write path.",
        "tools": READ_TOOLS,
        "allow": (),
        "deny": ("**",),
        "model": "claude-opus-5",
        "effort": "high",
    },
    ("research", "researcher"): {
        "tools": (*READ_TOOLS, *SEARCH_TOOLS),
        "model": "claude-sonnet-5",
    },
    ("research", "verifier"): {
        "model": "claude-sonnet-5",
    },
    ("research", "section_judge"): {
        "purpose": "Grades one section against its outline row. Holds no write path.",
        "tools": READ_TOOLS,
        "allow": (),
        "deny": ("**",),
        "model": "claude-sonnet-5",
    },
    ("research", "ledger"): {
        "purpose": "Extracts the section's facts and terms. Python appends the ledger. Holds no write path.",
        "tools": ("Read",),
        "allow": (),
        "deny": ("**",),
        "model": "claude-haiku-4-5",
        "effort": "low",
    },
    ("research", "diagrammer"): {
        # No write tool and no shell. It returns the diagram source, and Python
        # writes it and runs the renderer. A research tool that hands a model a
        # shell has widened its blast radius from "a wrong paper" to "anything
        # this machine can run", and it bought nothing: the renderer is one
        # subprocess with fixed arguments.
        "tools": READ_TOOLS,
        "allow": (),
        "deny": ("**",),
        "model": "claude-sonnet-5",
    },
    ("research", "writer"): {
        # The one role in this cast that writes, and the reason the PreToolUse
        # hook is not decorative. A section is long prose, and returning it
        # through a message costs a round trip and invites truncation.
        #
        # It cannot reach `paper.md`. Assembly is deterministic, in Python, so
        # a writer that decided to rewrite the whole paper is denied.
        "tools": (*READ_TOOLS, "Write"),
        "allow": ("sections/**",),
        "deny": (),
        "model": "claude-opus-5",
    },
    ("research", "judge"): {
        # No `Bash` here. The enhancer's judge reads a junit file, which is why
        # it has a shell. This one reads markdown and a JSON check report.
        "tools": READ_TOOLS,
        "model": "claude-opus-5",
        "effort": "high",
    },
}



@dataclass(frozen=True)
class RolePlan:
    """One role, described the same way for every runtime."""

    name: str
    purpose: str
    tools: tuple[str, ...]
    allow: tuple[str, ...] = ()
    deny: tuple[str, ...] = ()
    model: str | None = None
    effort: str | None = None

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

    `contract` may be None. The research loop runs against a topic, not a repo,
    so it has no `.loop.yml` to read.
    """
    if loop not in LOOPS:
        raise ValueError(f"unknown loop {loop!r}. Known: {', '.join(sorted(LOOPS))}")

    roles: dict[str, RolePlan] = {}
    for name in LOOPS[loop]:
        override = OVERRIDES.get((loop, name), {})
        if name in READERS:
            fields = {
                "purpose": PURPOSE[name],
                "tools": TOOLS_FOR_READER[name],
                "allow": (),
                "deny": (),
            }
        else:
            allow, deny = _scope(contract, name)
            fields = {
                "purpose": PURPOSE[name],
                "tools": (*READ_TOOLS, "Edit", "Write", "Bash"),
                "allow": allow,
                "deny": deny,
            }
        fields.update(override)
        # An override that widens a reader into a writer is a mistake, not a
        # feature. Catching it here beats finding it in a diff of the CRM.
        if name in READERS and any(tool in WRITE_TOOLS for tool in fields["tools"]):
            raise ValueError(f"{loop}/{name} is a reader but its override grants a write tool")
        if "allow" in override and "deny" not in override:
            raise ValueError(f"{loop}/{name} overrides allow without deny. Deny beats allow.")
        roles[name] = RolePlan(name=name, **fields)
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
