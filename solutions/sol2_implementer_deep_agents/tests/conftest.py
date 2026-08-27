"""Fixtures. No deepagents and no CRM clone required."""

from __future__ import annotations

import sys
import types
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
  planner:
    write_allow: ["steps.jsonl"]
  test_implementer:
    write_allow: ["tests/**"]
    write_deny: ["app/**"]
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
    (tmp_path / "tickets").mkdir()
    (tmp_path / "app").mkdir()
    (tmp_path / "tests").mkdir()
    return tmp_path


@pytest.fixture
def contract(target_repo: Path):
    return Contract(target_repo)


@pytest.fixture
def fake_langchain(monkeypatch: pytest.MonkeyPatch):
    def tool(name_or_func=None):
        if callable(name_or_func):
            return name_or_func
        return lambda func: func

    module = types.ModuleType("langchain.tools")
    module.tool = tool
    package = types.ModuleType("langchain")
    package.tools = module
    monkeypatch.setitem(sys.modules, "langchain", package)
    monkeypatch.setitem(sys.modules, "langchain.tools", module)
    return module
