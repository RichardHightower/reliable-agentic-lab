"""Shared fixtures. Nothing here imports deepagents or langchain for real.

The whole suite must run with no SDK, no API key, no network, no clone, and no
diagram renderer. That last one was missing, and it cost a real bug: thirteen
tests shelled out to mermaid-cli and plantuml, so the suite could not run on a
clean runner, and one cost-cap test was a false green. With no renderer the run
died at the diagram stage and still returned the exit code the test asserted.

`test_diagrams.py` is the one place that exercises the renderers, and it stubs
the calls that shell out.
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
DIAGRAM_SUFFIXES = (".mmd", ".mermaid", ".puml", ".plantuml")


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


# -- the diagram renderers -------------------------------------------------


def stub_figure(name: str, out_dir: Path):
    """A rendered figure, without mermaid-cli, plantuml, java, or a network."""
    import diagrams  # noqa: PLC0415  (sys.path is set above)

    out_dir.mkdir(parents=True, exist_ok=True)
    svg = out_dir / f"{name}.svg"
    svg.write_text("<svg/>", encoding="utf-8")
    return diagrams.Figure(
        name=name,
        source=Path(f"{name}.mmd"),
        svg=svg,
        alt=f"A diagram of {name}",
        hash="stub",
    )


def _render_stub(src_dir, out_dir, topic, **kwargs):
    src_dir = Path(src_dir)
    names = (
        [path.stem for path in sorted(src_dir.iterdir()) if path.suffix.lower() in DIAGRAM_SUFFIXES]
        if src_dir.is_dir()
        else []
    )
    return [stub_figure(name, Path(out_dir)) for name in names], []


@pytest.fixture
def stub_renderer(monkeypatch: pytest.MonkeyPatch):
    """Render every diagram source to a placeholder SVG, in process."""
    import stages  # noqa: PLC0415  (sys.path is set above)

    monkeypatch.setattr(stages, "render_figures", _render_stub)
    return _render_stub


@pytest.fixture
def no_renderer(monkeypatch: pytest.MonkeyPatch):
    """No mermaid-cli, no plantuml, no java. What a clean CI runner looks like."""
    import stages  # noqa: PLC0415  (sys.path is set above)

    def missing(src_dir, out_dir, topic, **kwargs):
        raise stages.RendererMissing("no diagram source could be rendered on this machine.")

    monkeypatch.setattr(stages, "render_figures", missing)
    return missing


# -- whole runs ------------------------------------------------------------


@pytest.fixture
def run_dir(tmp_path: Path) -> Path:
    return tmp_path / "run"


def build_run(work_dir: Path, **kwargs):
    import paper  # noqa: PLC0415  (sys.path is set above)
    import research  # noqa: PLC0415

    return paper.Paper(
        topic="Exit conditions in production agent loops",
        runner=kwargs.pop("runner", None) or paper.FixtureRunner(FIXTURES / "replies.json"),
        backend=research.FixtureBackend(FIXTURES / "research.json"),
        work_dir=work_dir,
        polish=False,
        quiet=True,
        **kwargs,
    )


@pytest.fixture
def offline(run_dir: Path, stub_renderer):
    """A whole pipeline, wired to recorded replies and a stubbed renderer."""
    return build_run(run_dir)


@pytest.fixture(scope="session")
def finished_paper(tmp_path_factory) -> Path:
    """One completed run, shared by every read-only check.

    Session scoped so the pipeline runs once rather than once per test. The
    renderer is stubbed here as everywhere else, so this passes on a runner with
    nothing installed.
    """
    import stages  # noqa: PLC0415  (sys.path is set above)

    work = tmp_path_factory.mktemp("finished")
    real, stages.render_figures = stages.render_figures, _render_stub
    try:
        run = build_run(work)
        assert run.run() == 0
    finally:
        stages.render_figures = real
    return work


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
