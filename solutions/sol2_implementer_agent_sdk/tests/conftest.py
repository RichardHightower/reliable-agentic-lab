"""Fixtures. No SDK, no API key, no network, in any test in this folder.

`sys.path` gets this folder, so the flat modules import the way they do when
you run `python3 harness.py` by hand. There is no package here on purpose.

`fake_sdk` installs a stub at `sys.modules["claude_agent_sdk"]` through
`monkeypatch.setitem`, so teardown restores its absence rather than leaving a
fake behind for the next test.

`FakeAgentDefinition` is an explicit dataclass and not a `**kwargs` bag. That
is the whole reason this folder's `max_turns=` bug survived: a permissive fake
accepts any spelling, so a test can assert the turn cap was set and still be
passing over a call that raises `TypeError` on the real SDK.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import pytest

FOLDER = Path(__file__).resolve().parents[1]
if str(FOLDER) not in sys.path:
    sys.path.insert(0, str(FOLDER))

from contract import Contract  # noqa: E402  (needs the sys.path shim above)

TASKFILE = """version: '3'
tasks:
  setup:
    cmds: [echo setup]
  test:
    cmds: [echo test]
  lint:
    cmds: [echo lint]
  format-check:
    cmds: [echo format]
  e2e:
    cmds: [echo e2e]
"""

LOOP_YML = """budget:
  iterations: 3
  usd: 2.00
rubric:
  coverage_floor: 80
  require_red: true
roles:
  planner:
    write_allow: [steps.jsonl]
  test_implementer:
    write_allow: [tests/**]
  code_implementer:
    write_allow: [app/**]
    write_deny: [tests/**, .loop.yml, Taskfile.yml]
"""


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
    setting_sources: list = field(default_factory=list)
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


class FakeResultError(Exception):
    pass


def make_sdk_module(messages=None):
    import types  # noqa: PLC0415  (only the fake needs it)

    module = types.ModuleType("claude_agent_sdk")
    module.AgentDefinition = FakeAgentDefinition
    module.HookMatcher = FakeHookMatcher
    module.ClaudeAgentOptions = FakeClaudeAgentOptions
    module.ResultMessage = FakeResultMessage
    module.ResultError = FakeResultError

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
def repo(tmp_path) -> Path:
    """A target repo the contract can read, with the five required tasks."""
    root = tmp_path / "crm"
    (root / "tests").mkdir(parents=True)
    (root / "app").mkdir()
    (root / "reports").mkdir()
    (root / "Taskfile.yml").write_text(TASKFILE, encoding="utf-8")
    (root / ".loop.yml").write_text(LOOP_YML, encoding="utf-8")
    return root


@pytest.fixture
def contract(repo) -> Contract:
    return Contract(repo)
