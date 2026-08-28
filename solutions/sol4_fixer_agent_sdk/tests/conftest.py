from __future__ import annotations

import asyncio
import sys
import types
from dataclasses import dataclass, field
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contract import Contract  # noqa: E402

TASKFILE = """\
version: '3'
tasks:
  setup: {cmds: [echo setup]}
  test: {cmds: [echo test]}
  e2e: {cmds: [echo e2e]}
  lint: {cmds: [echo lint]}
  format-check: {cmds: [echo format-check]}
"""

LOOP_YML = """\
version: 1
roles:
  code_implementer:
    write_allow: ["app/**"]
    write_deny: ["tests/**"]
  judge:
    write_allow: []
rubric:
  coverage_floor: 78
  require_red: true
tickets:
  source: local
  path: tickets
budget:
  iterations: 3
  usd: 2.00
"""


@pytest.fixture
def target_repo(tmp_path: Path) -> Path:
    (tmp_path / "Taskfile.yml").write_text(TASKFILE, encoding="utf-8")
    (tmp_path / ".loop.yml").write_text(LOOP_YML, encoding="utf-8")
    (tmp_path / "app").mkdir()
    (tmp_path / "tests").mkdir()
    return tmp_path


@pytest.fixture
def contract(target_repo: Path):
    return Contract(target_repo)


def run_async(coro):
    return asyncio.run(coro)


@dataclass
class FakeAgentDefinition:
    """An explicit dataclass, not a `**kwargs` bag.

    The old fake took `**kwargs`, so it accepted `max_turns=12` happily while
    the real SDK raises `TypeError` on it. A test asserting the turn cap was
    set passed over a call that could never run.
    """

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
    env: dict = field(default_factory=dict)


@dataclass
class FakeResultMessage:
    result: str = ""
    total_cost_usd: float = 0.0
    is_error: bool = False
    subtype: str = "success"


@pytest.fixture
def fake_sdk(monkeypatch):
    def install(messages=None):
        module = types.ModuleType("claude_agent_sdk")
        module.AgentDefinition = FakeAgentDefinition
        module.HookMatcher = FakeHookMatcher
        module.ClaudeAgentOptions = FakeClaudeAgentOptions
        module.ResultMessage = FakeResultMessage

        async def query(*, prompt, options):
            module.last_options = options
            for message in messages or []:
                yield message

        module.query = query
        module.last_options = None
        monkeypatch.setitem(sys.modules, "claude_agent_sdk", module)
        return module

    return install
