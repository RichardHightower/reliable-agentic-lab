"""Fixtures for this folder's tests. No SDK, no network, no CRM clone.

Every module here imports its siblings flat (`import roleplan`), the way
`loop.py` does when you run it from this directory. The sys.path shim below is
what makes that work under pytest, and it matches the one the target CRM repo
already uses in `work/northwind-field-crm/tests/conftest.py`.

`fake_sdk` is the only way to reach `roles.options_for` and the success path of
`adapter.AgentSdkBackend.run`. Both import `claude_agent_sdk` lazily, inside the
function, so a stub in `sys.modules` is enough. Installing the real package is
never required, and the suite must stay green without it.
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


def sdk_installed() -> bool:
    """True when the real package is importable. Collection-time skipif uses this."""
    try:
        import claude_agent_sdk  # noqa: F401
    except ImportError:
        return False
    return True


from contract import Contract  # noqa: E402  (needs the sys.path shim above)

# A target repo declares scope for the implementer's roles. It has never heard
# of `doer`, which is the whole point: the enhancer's doer must fall back to
# roleplan.FALLBACK_SCOPE rather than find a declaration here.
LOOP_YML = """\
roles:
  planner:
    write_allow: [steps.jsonl]
    write_deny: []
  test_implementer:
    write_allow: [tests/**]
    write_deny: []
  code_implementer:
    write_allow: [app/**, src/**]
    write_deny: [tests/**]
rubric:
  coverage_floor: 75.0
  require_red: true
budget:
  iterations: 5
  usd: 4.0
"""

TASKFILE = """\
version: '3'

tasks:
  setup:
    cmds: [echo setup]
  test:
    cmds: [echo test]
  e2e:
    cmds: [echo e2e]
  lint:
    cmds: [echo lint]
  format-check:
    cmds: [echo format-check]
"""

TICKET = """\
---
id: T001
state: draft
kind: feature
---
# Export contacts to CSV

A rep wants the contact list as a file they can open in a spreadsheet.

## Success criteria

- The export includes every contact the rep can see.
- (AC-7) The file opens in Excel without a warning.
"""


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A target repo that satisfies the contract, with one draft ticket."""
    (tmp_path / "Taskfile.yml").write_text(TASKFILE, encoding="utf-8")
    (tmp_path / ".loop.yml").write_text(LOOP_YML, encoding="utf-8")
    (tmp_path / "tickets").mkdir()
    (tmp_path / "tickets" / "T001.md").write_text(TICKET, encoding="utf-8")
    (tmp_path / "reports").mkdir()
    return tmp_path


@pytest.fixture
def contract(repo: Path):
    return Contract(repo)


# -- the stub SDK ----------------------------------------------------------


@dataclass
class FakeAgentDefinition:
    description: str = ""
    prompt: str = ""
    tools: list = field(default_factory=list)
    maxTurns: int = 0
    disallowedTools: list | None = None
    background: bool | None = None
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
    skills: list | str | None = None
    system_prompt: str | None = None
    max_turns: int | None = None
    max_budget_usd: float | None = None
    output_format: dict | None = None
    forward_subagent_text: bool = False
    env: dict = field(default_factory=dict)


@dataclass
class FakeResultMessage:
    result: str = ""
    total_cost_usd: float = 0.0
    structured_output: dict | None = None
    is_error: bool | None = False
    subtype: str = "success"


def make_sdk_module(messages: list | None = None) -> types.ModuleType:
    """A stand-in for `claude_agent_sdk`, holding only what this folder imports.

    `query` is an async generator, because `adapter.collect()` drives it with
    `async for`. A plain list would raise, and the broad `except` in `run()`
    would turn that into a false "backend failed" instead of a real check.
    """
    module = types.ModuleType("claude_agent_sdk")
    module.AgentDefinition = FakeAgentDefinition
    module.HookMatcher = FakeHookMatcher
    module.ClaudeAgentOptions = FakeClaudeAgentOptions
    module.ResultMessage = FakeResultMessage

    async def query(*, prompt: str, options):
        for message in messages or []:
            yield FakeResultMessage(result=message) if isinstance(message, str) else message

    module.query = query
    return module


@pytest.fixture
def fake_sdk(monkeypatch: pytest.MonkeyPatch):
    """Install the stub at `sys.modules["claude_agent_sdk"]` for one test.

    monkeypatch removes the entry on teardown, so a test that asserts the SDK is
    absent still sees it absent.
    """
    module = make_sdk_module()
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", module)
    return module
