"""The backend. `git diff` is mocked at `_changed_files`, its only shell seam."""

from __future__ import annotations

import adapter
import pytest


class FakeAgent:
    """Stands in for what `roles.build_agent` returns."""

    def __init__(self, answer="done", raises=None, result=None):
        self.answer = answer
        self.raises = raises
        self.result = result
        self.calls = []

    def invoke(self, payload):
        self.calls.append(payload)
        if self.raises is not None:
            raise self.raises
        if self.result is not None:
            return self.result
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
    assert result.output == "done"


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


def test_last_ai_text_takes_the_last_message_not_the_state_repr():
    state = {
        "messages": [
            {"role": "user", "content": "grade this"},
            {"role": "assistant", "content": '{"kind": "feature", "present_fields": []}'},
        ]
    }
    assert adapter.last_ai_text(state) == '{"kind": "feature", "present_fields": []}'


def test_last_ai_text_joins_content_blocks():
    state = {
        "messages": [
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": '{"kind":'},
                    {"type": "text", "text": ' "bug"}'},
                ],
            }
        ]
    }
    assert adapter.last_ai_text(state) == '{"kind": "bug"}'


def test_run_returns_the_last_message_not_the_state_repr(tmp_path, monkeypatch):
    _diffs(monkeypatch, before=set(), after=set())
    verdict = '{"kind": "feature", "present_fields": ["problem"]}'
    agent = FakeAgent(
        result={
            "messages": [
                {"role": "user", "content": "judge"},
                {"role": "assistant", "content": verdict},
            ]
        }
    )
    result = adapter.DeepAgentsBackend(agent).run(repo=tmp_path, prompt="judge", allow=[])
    assert result.output == verdict
    assert "messages" not in result.output
    assert result.usd == 0.0


def test_last_usd_sums_usage_metadata_costs():
    state = {
        "messages": [
            {"role": "user", "content": "go"},
            {"role": "assistant", "content": "ok", "usage_metadata": {"total_cost_usd": 0.4}},
            {"role": "assistant", "content": "done", "usage_metadata": {"total_cost": 0.1}},
        ]
    }
    assert adapter.last_usd(state) == pytest.approx(0.5)


def test_run_charges_the_cost_check_stop_will_see(tmp_path, monkeypatch):
    _diffs(monkeypatch, before=set(), after=set())
    agent = FakeAgent(
        result={
            "messages": [
                {"role": "assistant", "content": "done", "usage_metadata": {"cost": 0.25}},
            ]
        }
    )
    result = adapter.DeepAgentsBackend(agent).run(repo=tmp_path, prompt="draft", allow=[])
    assert result.usd == pytest.approx(0.25)
