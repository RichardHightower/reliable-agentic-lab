"""Load the Claude Code agent markdown files as SDK AgentDefinition kwargs.

The files in `plugin/agents/` are the prompts. Python must not restate them. A
one-line `You are the researcher.` is how a port drifts from the plugin it
claims to be, and it drifts silently.

`AgentDefinition` field names are camelCase (`maxTurns`, `disallowedTools`,
`background`). Passing `max_turns` raises TypeError on the real SDK and is
swallowed by the fake used in tests. That is why the names are written here as
the wire format, not as Python.

Every schema below is a closed set. Structured output makes text parsing a
fallback rather than the happy path, and `additionalProperties: false` is what
stops a model from answering a question you did not ask.
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


def _schema(properties: dict, required: list[str]) -> dict:
    return {
        "type": "json_schema",
        "schema": {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        },
    }


_STRINGS = {"type": "array", "items": {"type": "string"}}

PLAN_SCHEMA = _schema(
    {
        "title": {"type": "string"},
        "abstract": {"type": "string"},
        "sections": {
            "type": "array",
            "items": _schema(
                {
                    "id": {"type": "string"},
                    "heading": {"type": "string"},
                    "goal": {"type": "string"},
                },
                ["id", "heading", "goal"],
            )["schema"],
        },
        "questions": {
            "type": "array",
            "items": _schema(
                {
                    "id": {"type": "string"},
                    "text": {"type": "string"},
                    "section": {"type": "string"},
                },
                ["id", "text", "section"],
            )["schema"],
        },
        "diagrams": {
            "type": "array",
            "items": _schema(
                {
                    "name": {"type": "string"},
                    "concept": {"type": "string"},
                    "section": {"type": "string"},
                },
                ["name", "concept", "section"],
            )["schema"],
        },
    },
    ["title", "sections", "questions"],
)

RESEARCH_SCHEMA = _schema(
    {
        "answer": {"type": "string"},
        "sources": {
            "type": "array",
            "items": _schema(
                {"url": {"type": "string"}, "title": {"type": "string"}},
                ["url", "title"],
            )["schema"],
        },
        "claims": {
            "type": "array",
            "items": _schema(
                {
                    "text": {"type": "string"},
                    "source_url": {"type": "string"},
                    "quote": {"type": "string"},
                },
                ["text", "source_url", "quote"],
            )["schema"],
        },
    },
    ["answer", "sources", "claims"],
)

# `unclear` is a first-class answer, not a failure. A verifier forced to choose
# between supports and contradicts invents a verdict, and an invented verdict is
# worse than an honest shrug.
VERIFY_SCHEMA = _schema(
    {
        "verdict": {"type": "string", "enum": ["supports", "contradicts", "unclear"]},
        "source_url": {"type": "string"},
        "excerpt": {"type": "string"},
    },
    ["verdict", "source_url", "excerpt"],
)

DIAGRAM_SCHEMA = _schema(
    {
        "language": {"type": "string", "enum": ["mermaid", "plantuml"]},
        "source": {"type": "string"},
        "caption": {"type": "string"},
    },
    ["language", "source", "caption"],
)

REVIEW_SCHEMA = _schema(
    {
        "done": {"type": "boolean"},
        "summary": {"type": "string"},
        "issues": {
            "type": "array",
            "items": _schema(
                {
                    "severity": {"type": "string", "enum": ["critical", "major", "minor"]},
                    "section": {"type": "string"},
                    "description": {"type": "string"},
                },
                ["severity", "section", "description"],
            )["schema"],
        },
    },
    ["done", "summary", "issues"],
)

# Parent prompt. Python is the harness. The model only spawns the named agent.
PARENT_PROMPT = (
    "You are the research orchestrator. Python already owns the phases, the "
    "budget, and every write it makes itself. Spawn only the named subagent. "
    "Return that subagent's final message verbatim. Do not invoke the "
    "research-loop skill. Do not write files. Do not run a shell. Do not spawn "
    "general-purpose."
)

# Appended to every prompt that generates prose or a claim. Lifted from the
# grounding contract in articles v3, which learned it the expensive way: a
# fabricated citation reads exactly like a real one, and no amount of asking a
# model to be careful prevents one.
GROUNDING = (
    "<grounding_contract>\n"
    "Never add a citation, statistic, percentage, version number, product or "
    "vendor name, person's name, or quotation unless it appears in the "
    "retrieved evidence you were given. If a specific would strengthen a claim "
    "but you cannot trace it to that evidence, state the claim qualitatively or "
    "flag it with <!-- NEEDS-SOURCE: ... -->. Never guess a plausible-looking "
    "value. A fabricated citation or statistic is a critical failure, worse "
    "than a vaguer but true statement.\n"
    "</grounding_contract>"
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
