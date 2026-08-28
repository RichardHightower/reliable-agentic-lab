"""Load the Claude Code agent markdown files as SDK AgentDefinition kwargs.

The files in `plugin/agents/` are copies of `solutions/sol1_enhancer/.claude/agents/`.
The SDK port must not restate those prompts. A one-line `You are the doer.`
is how this port drifted from the plugin it claims to be.

`AgentDefinition` field names are camelCase (`maxTurns`, `disallowedTools`,
`background`). Passing `max_turns` raises TypeError on the real SDK and is
swallowed by the fake used in tests. That is why the names are written here
as the wire format, not as Python.
"""

from __future__ import annotations

import re
from pathlib import Path

FRONT = re.compile(r"^---\n(.*?)\n---\n", re.S)

PLUGIN = Path(__file__).resolve().parent / "plugin"
AGENTS = PLUGIN / "agents"

# Per-query caps. The SDK ends a subagent when either fires. Python still
# decides the poll-level exits: complete, cost, or max turns across calls.
DEFAULT_MAX_TURNS = 12

# The judge reports a closed set. Structured output makes parse_judge a fallback,
# not the happy path.
JUDGE_SCHEMA = {
    "type": "json_schema",
    "schema": {
        "type": "object",
        "properties": {
            "kind": {"type": "string", "enum": ["bug", "feature", "ui"]},
            "present_fields": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["kind", "present_fields"],
        "additionalProperties": False,
    },
}

# Parent prompt. Python is the harness. The model only spawns the named agent.
PARENT_PROMPT = (
    "You are the enhancer orchestrator. Python already owns the loop, the "
    "budget, and every write. Spawn only the named subagent. Return that "
    "subagent's final message verbatim. Do not invoke the enhancer-loop skill. "
    "Do not write files. Do not run a shell. Do not spawn general-purpose."
)


def parse_agent_md(path: Path) -> dict:
    """Front matter plus body from one Claude Code agent file."""
    text = path.read_text(encoding="utf-8")
    match = FRONT.match(text)
    meta: dict[str, str] = {}
    body = text
    if match:
        for line in match.group(1).splitlines():
            if ":" not in line:
                continue
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
        body = text[match.end() :].strip()
    tools = [part.strip() for part in meta.get("tools", "").split(",") if part.strip()]
    return {
        "name": meta.get("name", path.stem),
        "description": meta.get("description", ""),
        "tools": tools,
        "prompt": body,
    }


def agent_files() -> dict[str, dict]:
    """Every agent markdown file in the plugin, keyed by its front-matter name."""
    found = {}
    for path in sorted(AGENTS.glob("*.md")):
        parsed = parse_agent_md(path)
        found[parsed["name"]] = parsed
    return found
