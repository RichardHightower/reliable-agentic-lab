"""The adapter's two extractions: what the model said, and what it cost.

Both used to be missing here. `run()` returned `str(result)`, the repr of the
whole graph state, and never set `usd` at all.
"""

from __future__ import annotations

from pathlib import Path

import adapter
import gates
import loop_roles


class Block:
    """A content block that is an object, not a dict."""

    def __init__(self, text):
        self.text = text


class Message:
    """A message that is an object, the shape LangChain actually returns."""

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


# -- what the model said ---------------------------------------------------


def test_the_last_ai_message_comes_back_not_the_state_repr():
    """`str(result)` carries every message, every tool call, and every id. Feed
    that to a JSON parser and a working loop starts failing on nothing anyone
    changed."""
    result = state(
        {"role": "user", "content": "go"},
        ai("first"),
        ai("the answer"),
    )
    assert adapter.last_ai_text(result) == "the answer"
    assert "messages" not in adapter.last_ai_text(result)


def test_a_trailing_tool_message_is_not_the_answer():
    """Taking messages[-1] outright reports the tool's output as if the model
    had said it, whenever the graph ends on a tool call."""
    result = state(ai("the answer"), {"role": "tool", "content": "exit status 0"})
    assert adapter.last_ai_text(result) == "the answer"


def test_content_blocks_join():
    assert (
        adapter.last_ai_text(
            state(ai([{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]))
        )
        == "ab"
    )


def test_a_block_with_no_type_is_kept():
    """A dropped block does not raise. It returns a shorter answer that still
    parses, and the loop acts on half a reply."""
    assert adapter.last_ai_text(state(ai([{"text": "kept"}]))) == "kept"


def test_a_block_with_another_type_that_carries_text_is_kept():
    assert adapter.last_ai_text(state(ai([{"type": "thinking", "text": "kept"}]))) == "kept"


def test_a_block_that_is_an_object_is_kept():
    assert adapter.last_ai_text(state(ai([Block("kept")]))) == "kept"


def test_an_object_message_is_read_by_attribute():
    assert adapter.last_ai_text(state(Message("ai", "from an object"))) == "from an object"


def test_a_result_that_is_not_a_dict_still_answers():
    """Requiring a dict makes every other shape look like an empty run."""
    assert adapter.last_ai_text("a plain string") == "a plain string"
    assert adapter.last_ai_text(State([Message("ai", "from an object state")])) == (
        "from an object state"
    )


def test_a_result_with_no_messages_reports_itself():
    """Returning "" here would read as a successful empty run."""
    assert adapter.last_ai_text({"error": "boom"}) == str({"error": "boom"})


def test_a_state_with_no_ai_message_falls_back_to_the_last_one():
    assert adapter.last_ai_text(state({"role": "tool", "content": "only this"})) == "only this"


# -- what it cost ----------------------------------------------------------


def test_cost_sums_across_messages():
    result = state(
        ai("first", {"total_cost": 0.25}),
        ai("second", {"cost": 0.5}),
        ai("third", {"total_cost_usd": 0.25}),
    )
    assert adapter.last_usd(result) == 1.0


def test_missing_usage_metadata_is_zero_not_a_guess():
    """A budget built on estimated costs is wrong in whichever direction is
    least convenient, and this number decides when the loop stops."""
    assert adapter.last_usd(state(ai("no metadata"))) == 0.0


def test_a_non_dict_usage_metadata_does_not_raise():
    """`key in usage` raises on an object, and a backend that raises takes the
    loop down with it."""
    assert adapter.last_usd(state(Message("ai", "x", usage=object()))) == 0.0


def test_an_unparseable_cost_is_skipped_not_crashed():
    assert adapter.last_usd(state(ai("x", {"cost": "free"}))) == 0.0


def test_a_top_level_usd_wins():
    assert adapter.last_usd({"usd": 2.5, "messages": [ai("x", {"cost": 1.0})]}) == 2.5


def test_cost_reads_an_object_result():
    assert adapter.last_usd(State([Message("ai", "x", usage={"cost": 0.75})])) == 0.75


# -- the cost stop this folder actually owns -------------------------------


class FakeAgent:
    """A Deep Agents graph that answers and reports what it charged."""

    def __init__(self, text="done", usd=0.0):
        self.text = text
        self.usd = usd

    def invoke(self, _payload):
        return state(ai(self.text, {"total_cost": self.usd}))


def test_the_backend_reports_what_the_run_cost(tmp_path):
    """The whole point. `implementer.py` calls `boss.spend(result.usd)` and
    passes `boss.usd_left` into `gates.decide`, and `gates.py` escalates on
    `usd_left <= 0`. While the adapter returned `usd=0.0` that branch was
    wired, reachable in principle, and dead in fact."""
    result = adapter.DeepAgentsBackend(FakeAgent("wrote it", usd=1.25)).run(
        repo=tmp_path, prompt="go", allow=["app/**"]
    )
    assert result.ok
    assert result.usd == 1.25
    assert result.output == "wrote it"


def test_a_spent_budget_now_escalates(tmp_path):
    """End to end through the objects the loop really uses."""
    boss = loop_roles.Orchestrator(name="orchestrator", repo=Path(tmp_path), budget_usd=2.0)
    for _ in range(2):
        outcome = adapter.DeepAgentsBackend(FakeAgent(usd=1.0)).run(
            repo=tmp_path, prompt="go", allow=["app/**"]
        )
        boss.spend(outcome.usd)

    assert boss.usd_left == 0.0
    decision = gates.decide(passed=False, iteration=1, usd_left=boss.usd_left)
    assert decision.gate == gates.ESCALATE
    assert "money budget is spent" in decision.reason


def test_a_silent_runtime_leaves_the_budget_alone(tmp_path):
    """No usage metadata means no charge, not an invented one."""
    boss = loop_roles.Orchestrator(name="orchestrator", repo=Path(tmp_path), budget_usd=2.0)
    boss.spend(
        adapter.DeepAgentsBackend(FakeAgent(usd=0.0))
        .run(repo=tmp_path, prompt="go", allow=["app/**"])
        .usd
    )
    assert boss.usd_left == 2.0
