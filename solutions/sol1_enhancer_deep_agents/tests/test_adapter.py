"""The backend. `git diff` is mocked at `_changed_files`, its only shell seam."""

from __future__ import annotations

import adapter


class FakeAgent:
    """Stands in for what `roles.build_agent` returns."""

    def __init__(self, answer="done", raises=None):
        self.answer = answer
        self.raises = raises
        self.calls = []

    def invoke(self, payload):
        self.calls.append(payload)
        if self.raises is not None:
            raise self.raises
        return {"messages": [{"role": "assistant", "content": self.answer}]}


def _diffs(monkeypatch, before, after):
    """`_changed_files` is called once before the agent runs and once after."""
    answers = iter([set(before), set(after)])
    monkeypatch.setattr(adapter, "_changed_files", lambda repo: next(answers))


def test_a_write_inside_the_scope_is_reported(tmp_path, monkeypatch):
    _diffs(monkeypatch, before=set(), after={"tickets/1.md"})
    backend = adapter.DeepAgentsBackend(FakeAgent())

    result = backend.run(repo=tmp_path, prompt="enhance", allow=["tickets/**"])

    assert result.ok is True
    assert result.wrote == ["tickets/1.md"]
    assert "done" in result.output


def test_a_write_outside_the_scope_is_dropped(tmp_path, monkeypatch):
    _diffs(monkeypatch, before=set(), after={"tickets/1.md", "app/x.py"})
    backend = adapter.DeepAgentsBackend(FakeAgent())

    result = backend.run(repo=tmp_path, prompt="enhance", allow=["tickets/**"])

    assert result.wrote == ["tickets/1.md"]


def test_a_file_already_dirty_before_the_run_is_not_claimed(tmp_path, monkeypatch):
    _diffs(monkeypatch, before={"tickets/1.md"}, after={"tickets/1.md", "tickets/2.md"})
    backend = adapter.DeepAgentsBackend(FakeAgent())

    result = backend.run(repo=tmp_path, prompt="enhance", allow=["tickets/**"])

    assert result.wrote == ["tickets/2.md"]


def test_the_prompt_reaches_the_agent(tmp_path, monkeypatch):
    _diffs(monkeypatch, before=set(), after=set())
    agent = FakeAgent()

    adapter.DeepAgentsBackend(agent).run(repo=tmp_path, prompt="enhance", allow=[])

    assert agent.calls == [{"messages": [{"role": "user", "content": "enhance"}]}]


def test_a_failing_agent_returns_not_ok(tmp_path, monkeypatch):
    _diffs(monkeypatch, before=set(), after={"tickets/1.md"})
    backend = adapter.DeepAgentsBackend(FakeAgent(raises=RuntimeError("no key")))

    result = backend.run(repo=tmp_path, prompt="enhance", allow=["tickets/**"])

    assert result.ok is False
    assert result.wrote == []
    assert "deep agents backend failed" in result.output
    assert "no key" in result.output


def test_the_backend_names_itself():
    assert adapter.DeepAgentsBackend.name == "deep_agents"
    assert issubclass(adapter.DeepAgentsBackend, adapter.Backend)
