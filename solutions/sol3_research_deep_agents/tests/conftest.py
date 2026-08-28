"""Shared fixtures. Nothing here imports deepagents or langchain for real.

The whole suite must run with no SDK, no API key, no network, and no clone.
That is the contract every solution folder in this repo meets, and it is what
lets an attendee check their translation before installing anything.
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FIXTURES = ROOT / "fixtures" / "paper"


@pytest.fixture
def fake_langchain(monkeypatch: pytest.MonkeyPatch):
    """A `@tool` decorator that is the identity function.

    `roles.py` imports `langchain.tools.tool` inside each factory. Faking the
    module lets the tests read the tool list a role is handed without the
    package being installed.
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

    The three fencing layers are only real if `create_deep_agent` actually
    receives them. This captures the call so a test can assert on it.
    """
    seen: dict = {}

    def create_deep_agent(**kwargs):
        seen.update(kwargs)
        return object()

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


@pytest.fixture
def run_dir(tmp_path: Path) -> Path:
    return tmp_path / "run"


@pytest.fixture
def offline(run_dir: Path):
    """A whole pipeline, wired to recorded replies. No network, no key, no SDK."""
    import paper  # noqa: PLC0415  (sys.path is set by conftest first)
    import research  # noqa: PLC0415  (sys.path is set by conftest first)

    return paper.Paper(
        topic="Exit conditions in production agent loops",
        runner=paper.FixtureRunner(FIXTURES / "replies.json"),
        backend=research.FixtureBackend(FIXTURES / "research.json"),
        work_dir=run_dir,
        polish=False,
        quiet=True,
    )


@pytest.fixture(scope="session")
def finished_paper(tmp_path_factory) -> Path:
    """One completed run, shared by every read-only check.

    Session scoped because the diagram stage shells out to mmdc and plantuml,
    which take seconds. Tests that mutate a run take the per-test `offline`
    fixture instead.
    """
    import paper  # noqa: PLC0415  (sys.path is set by conftest first)
    import research  # noqa: PLC0415  (sys.path is set by conftest first)

    work = tmp_path_factory.mktemp("finished")
    run = paper.Paper(
        topic="Exit conditions in production agent loops",
        runner=paper.FixtureRunner(FIXTURES / "replies.json"),
        backend=research.FixtureBackend(FIXTURES / "research.json"),
        work_dir=work,
        polish=False,
        quiet=True,
    )
    assert run.run() == 0
    return work


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
