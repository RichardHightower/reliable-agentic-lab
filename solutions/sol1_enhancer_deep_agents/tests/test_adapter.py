"""The backend. `git diff` is mocked at `_changed_files`, its only shell seam."""

from __future__ import annotations

import adapter
import contextlib
import signal
import time
import pytest

# -- shapes a LangChain run actually returns -------------------------------


class Block:
    """A content block that is an object, not a dict."""

    def __init__(self, text):
        self.text = text


class Message:
    """A message that is an object, the shape LangChain returns."""

    def __init__(self, type_, content, usage=None):
        self.type = type_
        self.content = content
        self.usage_metadata = usage


class State:
    """An invoke result that is an object rather than a state dict."""

    def __init__(self, messages):
        self.messages = messages


def state(*messages):
    return {"messages": list(messages)}


def ai(content, usage=None):
    entry = {"role": "assistant", "content": content}
    if usage is not None:
        entry["usage_metadata"] = usage
    return entry


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


def test_a_timeout_returns_a_distinct_fail_closed_result(tmp_path, monkeypatch):
    _diffs(monkeypatch, before=set(), after=set())

    @contextlib.contextmanager
    def expires(_seconds):
        raise adapter.QueryTimedOut("Deep Agents query exceeded 180 seconds")
        yield  # pragma: no cover - keeps this a context manager for the adapter

    monkeypatch.setattr(adapter, "_wall_clock_timeout", expires)
    result = adapter.DeepAgentsBackend(FakeAgent()).run(
        repo=tmp_path, prompt="Use the judge subagent. Read tickets/T001.md", allow=[]
    )

    assert result.ok is False
    assert result.timed_out is True
    assert "exceeded 180 seconds" in result.output


@pytest.mark.skipif(not hasattr(signal, "SIGALRM"), reason="SIGALRM is unavailable on Windows")
def test_the_wall_clock_guard_interrupts_a_blocked_sync_invoke(tmp_path, monkeypatch):
    _diffs(monkeypatch, before=set(), after=set())

    class SlowAgent:
        def invoke(self, _payload):
            time.sleep(1)

    started = time.monotonic()
    result = adapter.DeepAgentsBackend(SlowAgent(), timeout_s=0.05).run(
        repo=tmp_path, prompt="Use the judge subagent. Read tickets/T001.md", allow=[]
    )

    assert result.timed_out is True
    assert time.monotonic() - started < 0.5


def test_a_completed_call_persists_its_prompt_and_returned_text(tmp_path, monkeypatch):
    _diffs(monkeypatch, before=set(), after=set())
    adapter.DeepAgentsBackend(FakeAgent(answer='{"kind": "feature"}')).run(
        repo=tmp_path, prompt="Use the judge subagent. Read tickets/T001.md", allow=[]
    )

    trace = (tmp_path / ".harness" / "last-deep-agents-judge-T001.md").read_text()
    assert "Use the judge subagent" in trace
    assert '{"kind": "feature"}' in trace


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


# -- which message is the answer -------------------------------------------
#
# Two failure shapes, and this repo has shipped both. These four cases are the
# contract. They were written before the fix.


def tool_call(name="read_file"):
    """A tool-calling assistant message. Content is empty, which is the trap."""
    return {"role": "assistant", "content": "", "tool_calls": [{"name": name}]}


def tool_result(text):
    return {"role": "tool", "content": text}


def test_case_1_a_plain_reply_comes_back():
    """The simple shape. Nothing tricky, and it still has to work."""
    assert adapter.last_ai_text(state(ai("the answer"))) == "the answer"


def test_case_2_a_reply_after_the_tool_wins_over_an_earlier_one():
    """The model spoke again after the tool ran. That is the answer.

    Writing these tests first caught a flaw in an earlier draft of this file.
    It asserted that a trailing tool message is never the answer, which
    contradicts case 4. A ToolMessage only exists because an assistant message
    asked for it, so "the model has not answered since the tool ran" and "the
    tool holds the answer" are the same state.
    """
    result = state(
        {"role": "user", "content": "grade this"},
        ai('{"verdict": "stale"}'),
        tool_call(),
        tool_result("some file contents"),
        ai('{"verdict": "final"}'),
    )
    assert adapter.last_ai_text(result) == '{"verdict": "final"}'


def test_case_3_a_reply_after_a_tool_call_is_not_stale():
    """The regression #176 shipped.

    The walk backward for the last non-empty AI message steps over the empty
    tool-calling message and lands on turn 1. A stale verdict that parses is
    worse than no verdict, because nothing reports it.
    """
    result = state(
        {"role": "user", "content": "grade this"},
        ai('{"verdict": "stale"}'),
        tool_call(),
        tool_result("some file contents"),
        ai('{"verdict": "current"}'),
    )
    assert adapter.last_ai_text(result) == '{"verdict": "current"}'


def test_case_4_a_run_ending_on_a_tool_call_returns_the_tool_content():
    """When the model has not spoken since the tool ran, the tool holds the
    answer. A subagent with a `response_format` puts its structured result
    exactly there, JSON-serialized.

    Returning the earlier assistant turn here is the #176 bug. Returning "" is
    worse: it reads as a successful empty run.
    """
    result = state(
        {"role": "user", "content": "grade this"},
        ai('{"verdict": "stale"}'),
        tool_call(),
        tool_result('{"verdict": "current"}'),
    )
    assert adapter.last_ai_text(result) == '{"verdict": "current"}'


def test_an_empty_tool_calling_message_is_never_the_answer():
    """Its content is empty by construction. Skipping it is right. Landing on
    the turn before it is the #176 bug."""
    result = state(ai("the answer"), tool_call())
    assert adapter.last_ai_text(result) == "the answer"


def test_the_rule_in_one_line():
    """Walk backward. The first non-empty content from an assistant or a tool
    message is the answer. Everything above is that rule under four shapes."""
    assert adapter.last_ai_text(state(ai("a"), tool_call(), tool_result("b"))) == "b"
    assert adapter.last_ai_text(state(ai("a"), tool_call(), tool_result("b"), ai("c"))) == "c"


def test_object_messages_take_the_same_path():
    """LangChain returns objects, not dicts, on the real path."""
    result = State(
        [
            Message("ai", '{"verdict": "stale"}'),
            Message("ai", ""),
            Message("tool", '{"verdict": "current"}'),
        ]
    )
    assert adapter.last_ai_text(result) == '{"verdict": "current"}'


def test_write_refuses_a_path_outside_the_repo(fake_langchain, tmp_path):
    """`WriteScope` refuses `..` by glob, which holds only while every caller
    spells the escape the same way. Resolving the target means the check does
    not depend on the spelling."""
    import roleplan  # noqa: PLC0415  (sys.path is set by conftest first)
    import roles  # noqa: PLC0415

    repo = tmp_path / "repo"
    repo.mkdir()
    writer = next(r for r in roleplan.plan(None, "enhancer").values() if r.can_write)
    out = roles.scoped_write_tool(repo, writer)("../escaped.txt", "SECRET")

    assert out.startswith("REFUSED")
    assert not (tmp_path / "escaped.txt").exists()
