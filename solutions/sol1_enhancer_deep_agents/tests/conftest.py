"""Fixtures for this folder's tests.

The folder's modules are flat top-level names (`roleplan`, `contract`, ...), so
the folder root has to be on `sys.path`. pytest only prepends `tests/`.

Nothing here imports `deepagents` or `langchain`. The suite has to run with
neither installed, which is the whole claim this port makes.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contract import Contract  # noqa: E402  (needs the sys.path line above)

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

LOOP_YML = """\
version: 1

roles:
  code_implementer:
    write_allow: ["app/**"]
    write_deny:  ["tests/**"]
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
    """A directory that satisfies the contract, with no doer declared.

    No doer is the point. The enhancer's doer scope has to come from
    `roleplan.FALLBACK_SCOPE`, the way every real target repo leaves it.
    """
    (tmp_path / "Taskfile.yml").write_text(TASKFILE, encoding="utf-8")
    (tmp_path / ".loop.yml").write_text(LOOP_YML, encoding="utf-8")
    (tmp_path / "tickets").mkdir()
    return tmp_path


@pytest.fixture
def contract(target_repo: Path):
    return Contract(target_repo)


@pytest.fixture
def fake_langchain(monkeypatch: pytest.MonkeyPatch):
    """A stand-in for `langchain.tools`, so the write tool runs uninstalled.

    The real `@tool` wraps the function in a `BaseTool`. The scope check runs
    before any of that, so returning the function unchanged is enough to test
    the only part this folder owns.
    """

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
