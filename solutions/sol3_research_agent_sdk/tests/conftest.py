"""Fixtures. No SDK, no API key, no network, in any test in this folder.

Two mechanisms make that true.

`sys.path` gets this folder, so the flat modules import the way they do when you
run `python3 loop.py` by hand. There is no package here on purpose.

`fake_sdk` installs a stub module at `sys.modules["claude_agent_sdk"]` through
`monkeypatch.setitem`, so teardown restores its absence rather than leaving a
fake behind for the next test. `query` is a real async generator because
`adapter` drives it with `async for`. A list there raises, and the adapter's
broad `except` would report a false "backend failed" instead.

`FakeClaudeAgentOptions` enumerates exactly the fields `roles.options_for` sets.
A permissive `**kwargs` fake would swallow a typo, which is the bug the fake
exists to catch.
"""

from __future__ import annotations

import sys
import types
from dataclasses import dataclass, field
from pathlib import Path

import pytest

FOLDER = Path(__file__).resolve().parents[1]
if str(FOLDER) not in sys.path:
    sys.path.insert(0, str(FOLDER))


@dataclass
class FakeAgentDefinition:
    description: str = ""
    prompt: str = ""
    tools: list = field(default_factory=list)
    disallowedTools: list = field(default_factory=list)  # the SDK's wire name
    maxTurns: int = 0  # the SDK's wire name, not Python's
    background: bool = False
    model: str | None = None


@dataclass
class FakeHookMatcher:
    matcher: str = ""
    hooks: list = field(default_factory=list)


@dataclass
class FakeClaudeAgentOptions:
    cwd: str = ""
    agents: dict = field(default_factory=dict)
    allowed_tools: list = field(default_factory=list)
    disallowed_tools: list = field(default_factory=list)
    permission_mode: str = ""
    hooks: dict = field(default_factory=dict)
    mcp_servers: dict = field(default_factory=dict)
    strict_mcp_config: bool = False
    plugins: list = field(default_factory=list)
    skills: list = field(default_factory=list)
    system_prompt: str = ""
    max_turns: int = 0
    max_budget_usd: float | None = None
    output_format: dict | None = None
    env: dict = field(default_factory=dict)


@dataclass
class FakeResultMessage:
    result: str = ""
    total_cost_usd: float = 0.0
    structured_output: dict | None = None
    is_error: bool = False
    subtype: str = "success"


def make_sdk_module(messages=None):
    module = types.ModuleType("claude_agent_sdk")
    module.AgentDefinition = FakeAgentDefinition
    module.HookMatcher = FakeHookMatcher
    module.ClaudeAgentOptions = FakeClaudeAgentOptions
    module.ResultMessage = FakeResultMessage

    async def query(*, prompt: str, options):
        module.last_prompt = prompt
        module.last_options = options
        for message in messages or []:
            yield message

    module.query = query
    module.last_prompt = None
    module.last_options = None
    return module


@pytest.fixture
def fake_sdk(monkeypatch):
    def install(messages=None):
        module = make_sdk_module(messages)
        monkeypatch.setitem(sys.modules, "claude_agent_sdk", module)
        return module

    return install


@pytest.fixture
def work(tmp_path) -> Path:
    """An empty work directory, the way a run starts."""
    path = tmp_path / "work" / "a-topic"
    path.mkdir(parents=True)
    return path


class RecordingTurns:
    """A `Turns` that answers from canned data and records what it was asked.

    Verifying that the verifier is never handed the researcher's source needs a
    record of the arguments, not of the result.
    """

    def __init__(self, *, verdict="supports", claims=None, done=True, root=None):
        self.asked: list[tuple] = []
        self.verdict = verdict
        self.claims = claims
        self.done = done
        # None means "a writer that answered but never wrote the file", which
        # is the fallback path and therefore the default under test.
        self.root = root

    def plan(self, topic, prior_art, budget=None):
        self.asked.append(("plan", topic, prior_art, budget))
        return {
            "title": f"On {topic}",
            "abstract": "An abstract.",
            "sections": [{"id": "s1", "heading": "The problem", "goal": "State it."}],
            "questions": [{"id": "q1", "text": f"what is {topic}", "section": "s1"}],
            "diagrams": [],
        }

    def research(self, question):
        self.asked.append(("research", question))
        claims = self.claims
        if claims is None:
            claims = [
                {
                    "text": "A thing is true.",
                    "source_url": "https://example.invalid/doc",
                    "quote": "a thing is true",
                }
            ]
        return {
            "answer": "A thing is true.",
            "sources": [{"url": "https://example.invalid/doc", "title": "Doc"}],
            "claims": claims,
        }

    def verify(self, claim):
        self.asked.append(("verify", claim))
        return {
            "verdict": self.verdict,
            "source_url": "https://example.invalid/other",
            "excerpt": "a thing is true",
        }

    def diagram(self, name, concept, feedback=""):
        self.asked.append(("diagram", name, concept, feedback))
        return {"language": "mermaid", "source": "flowchart LR\n  A[A] --> B[B]", "caption": "Cap."}

    def write(self, section, claims, figures, notes, path=""):
        self.asked.append(("write", section["id"], notes, path))
        lines = [f"## {section['heading']}", ""]
        for figure in figures:
            lines += [f"![Figure: {figure['name']}]({figure['path']})", "", "Cap.", ""]
        for claim in claims:
            lines += [f"{claim['text']} [{claim.get('number', 1)}]", ""]
        body = "\n".join(lines)
        if self.root is not None and path:
            target = Path(self.root) / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(body, encoding="utf-8")
        return body

    def review(self, paper, report):
        self.asked.append(("review", report))
        return {"done": self.done, "summary": "ok", "issues": []}


@pytest.fixture
def turns():
    return RecordingTurns
