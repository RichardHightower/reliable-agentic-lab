"""The adapter's two extractions: what the model said, and what it cost.

Both used to be missing here. `run()` returned `str(result)`, the repr of the
whole graph state, and never set `usd` at all.
"""

from __future__ import annotations

import adapter


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


def ai(content, usage=None, name=None):
    entry = {"role": "assistant", "content": content}
    if usage is not None:
        entry["usage_metadata"] = usage
    if name is not None:
        entry["name"] = name
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


def test_a_trailing_tool_message_is_the_answer_when_nothing_followed_it():
    """This test asserted the opposite when #176 shipped it, and the assertion
    was wrong.

    A ToolMessage exists only because an assistant message asked for it, and
    that asking message carries empty content. So "the model has not spoken
    since the tool ran" and "the tool holds the answer" are the same state.
    Skipping the tool message here is what made the loop read a stale verdict
    from an earlier turn.
    """
    result = state(ai("an older turn"), {"role": "tool", "content": "exit status 0"})
    assert adapter.last_ai_text(result) == "exit status 0"


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


def test_a_delegated_reply_ignores_the_parent_tool_receipt():
    result = state(
        ai("[1] cited writer body", name="writer"),
        {"role": "tool", "content": "permission denied: /paper"},
        ai("delegation finished", name="orchestrator"),
    )
    assert adapter.last_agent_ai_text(result, "writer") == "[1] cited writer body"


def test_a_delegated_reply_falls_back_for_old_graph_shapes():
    assert adapter.last_agent_ai_text(state(ai("plain answer")), "writer") == "plain answer"


def test_agent_name_identifies_a_subgraph_state_without_its_namespace():
    child = state(ai("[1] writer prose", name="writer"))
    assert adapter.has_agent_ai_message(child, "writer") is True
    assert adapter.has_agent_ai_message(child, "researcher") is False


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
    writer = next(r for r in roleplan.plan(None, "paper").values() if r.can_write)
    out = roles.scoped_write_tool(repo, writer)("../escaped.txt", "SECRET")

    assert out.startswith("REFUSED")
    assert not (tmp_path / "escaped.txt").exists()
