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
    effort: str | None = None


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
    setting_sources: list | None = None
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

    def tool(name, description, schema):
        def decorator(fn):
            fn.mcp_name = name
            fn.mcp_description = description
            fn.mcp_schema = schema
            return fn

        return decorator

    def create_sdk_mcp_server(*, name, version="1.0.0", tools=()):
        return {"type": "sdk", "name": name, "version": version, "tools": list(tools)}

    module.tool = tool
    module.create_sdk_mcp_server = create_sdk_mcp_server
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

    def outline(self, topic, prior_art, budget=None, note="", brief=""):
        self.asked.append(("outline", topic, prior_art, budget, note, brief))
        words = int((budget or {}).get("words") or 400)
        return {
            "title": f"On {topic}",
            "audience": "engineers",
            "thesis": "An abstract.",
            "word_target_total": words,
            "sections": [
                {
                    "id": "s1",
                    "heading": "The problem",
                    "objective": "State it.",
                    "abstract": "This section states the problem.",
                    "key_questions": [
                        f"what is {topic}",
                        f"why does {topic} fail",
                    ],
                    "claims_to_support": ["The problem is structural."],
                    "required_evidence": ["a primary specification"],
                    "word_target": words,
                    "figures": [],
                    "depends_on": [],
                }
            ],
        }

    def plan(self, topic, prior_art, budget=None, note="", brief=""):
        return self.outline(topic, prior_art, budget, note, brief)

    def judge_outline(self, drafted, note=""):
        self.asked.append(("judge_outline", note))
        return {
            "passed": True,
            "score": 1.0,
            "blocking_issues": [],
            "actionable_changes": [],
        }

    def research(self, question, note=""):
        self.asked.append(("research", question, note))
        already = sum(1 for item in self.asked if item[0] == "research")
        if already > 1:
            # One canned finding, not a copy on every key question.
            return {"answer": "", "sources": [], "claims": []}
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

    def chart_spec(self, figure, rows, note=""):
        self.asked.append(("chart_spec", figure.get("name"), len(rows), note))
        if not rows:
            return {}
        import charts as charts_mod  # noqa: PLC0415

        return charts_mod.default_spec(figure, rows)

    def write(self, section, claims, figures, notes, path=""):
        self.asked.append(("write", section["id"], notes, path))
        lines = [f"## {section['heading']}", ""]
        for figure in figures:
            lines += [f"![Figure: {figure['name']}]({figure['path']})", "", "Cap.", ""]
        for claim in claims:
            lines += [f"{claim['text']} [{claim.get('number', 1)}]", ""]
        for question in section.get("key_questions") or []:
            marker = f"[{claims[0].get('number', 1)}]" if claims else ""
            if claims:
                lines += [f"This section answers: {question} {marker}".strip(), ""]
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
