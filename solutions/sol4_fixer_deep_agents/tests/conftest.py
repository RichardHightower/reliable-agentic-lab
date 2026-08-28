"""Fixtures for this folder's tests.

The folder's modules are flat top-level names (`roleplan`, `contract`, ...), so
the folder root has to be on `sys.path`. pytest only prepends `tests/`.

Nothing here imports `deepagents` or `langchain` for real. The suite has to run
with neither installed, with no key, and with no clone, which is the whole
claim this port makes.
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
    """A directory that satisfies the contract, shaped like the broken PR repo."""
    (tmp_path / "Taskfile.yml").write_text(TASKFILE, encoding="utf-8")
    (tmp_path / ".loop.yml").write_text(LOOP_YML, encoding="utf-8")
    (tmp_path / "app").mkdir()
    (tmp_path / "tests").mkdir()
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


@pytest.fixture
def fake_deepagents(monkeypatch: pytest.MonkeyPatch):
    """Record what `build_agent` asks the SDK for, without the SDK.

    The harness fence is only real if `create_deep_agent` and
    `register_harness_profile` actually receive it. This captures both calls so
    a test can assert on what arrived.
    """
    seen: dict = {}

    def create_deep_agent(**kwargs):
        seen.update(kwargs)
        return "agent"

    def register_harness_profile(model, profile):
        seen["harness_model"] = model
        seen["harness_profile"] = profile

    class FilesystemPermission:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class GeneralPurposeSubagentProfile:
        def __init__(self, enabled=True):
            self.enabled = enabled

    class HarnessProfile:
        def __init__(self, excluded_tools=(), general_purpose_subagent=None):
            self.excluded_tools = excluded_tools
            self.general_purpose_subagent = general_purpose_subagent

    class FilesystemBackend:
        def __init__(self, root_dir="", virtual_mode=False):
            self.root_dir = root_dir
            self.virtual_mode = virtual_mode

    class CompositeBackend:
        def __init__(self, default=None, routes=None):
            self.default = default
            self.routes = routes or {}

    package = types.ModuleType("deepagents")
    package.create_deep_agent = create_deep_agent
    package.register_harness_profile = register_harness_profile
    package.FilesystemPermission = FilesystemPermission
    package.GeneralPurposeSubagentProfile = GeneralPurposeSubagentProfile
    package.HarnessProfile = HarnessProfile
    backends = types.ModuleType("deepagents.backends")
    backends.FilesystemBackend = FilesystemBackend
    backends.CompositeBackend = CompositeBackend
    package.backends = backends

    monkeypatch.setitem(sys.modules, "deepagents", package)
    monkeypatch.setitem(sys.modules, "deepagents.backends", backends)
    return seen
