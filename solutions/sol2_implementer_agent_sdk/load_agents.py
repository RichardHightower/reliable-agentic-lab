"""Load the Claude Code agent markdown files as SDK AgentDefinition kwargs.

The files in `plugin/agents/` are the prompts. Python must not restate them.
This port used to build every system prompt as
`f"You are the {role.name}. {role.purpose}"`, which made the entire
instruction to the code implementer one sentence long. A one-line
`You are the doer.` is how a port drifts from the plugin it claims to be, and
it drifts silently.

`AgentDefinition` field names are camelCase (`maxTurns`, `disallowedTools`,
`background`). Passing `max_turns` raises TypeError on the real SDK. A test
fake that takes `**kwargs` swallows the difference, which is why the fake in
`tests/conftest.py` is an explicit dataclass.
"""

from __future__ import annotations

import re
from pathlib import Path

FRONT = re.compile(r"^---\n(.*?)\n---\n", re.S)

PLUGIN = Path(__file__).resolve().parent / "plugin"
AGENTS = PLUGIN / "agents"

# Per-query caps. The SDK ends a subagent when either fires. Python still
# decides the run-level exits: done, cost, or max turns across calls.
DEFAULT_MAX_TURNS = 12

# Parent prompt. Python is the harness. The model only spawns the named agent.
PARENT_PROMPT = (
    "You are the implementer orchestrator. Python already owns the loop, the "
    "budget, the test run, and the rubric. Spawn only the named subagent. "
    "Return that subagent's final message verbatim. Do not write files. Do not "
    "run a shell. Do not spawn general-purpose."
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
