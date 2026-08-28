"""The `doers.Backend` that runs the doer role through this runtime.

`run()` catches every exception on purpose, the way `CliBackend.run` does, so a
missing optional dependency reports as a failed result rather than a traceback.
The cost is that a real bug reads the same as a missing package, which is why
each failure mode gets its own check on the message it produces.

Nothing here installs `claude-agent-sdk` and nothing here calls `git`.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import adapter
import pytest
from adapter import AgentSdkBackend, Backend, DoerResult
from tests.conftest import FakeResultMessage, make_sdk_module


@pytest.fixture
def changed(monkeypatch):
    """Control what `git diff --name-only` reports, call by call.

    The backend calls it twice: once before the run and once after. The
    difference is what the doer wrote.
    """
    rounds: list[set[str]] = []

    def fake_changed(repo: Path) -> set[str]:
        return rounds.pop(0) if rounds else set()

    monkeypatch.setattr(adapter, "_changed_files", fake_changed)
    return rounds


# -- the base class --------------------------------------------------------


def test_the_base_backend_has_no_implementation(tmp_path):
    with pytest.raises(NotImplementedError):
        Backend().run(repo=tmp_path, prompt="do it", allow=[])


def test_a_result_defaults_to_ok_and_wrote_nothing():
    result = DoerResult()
    assert result.ok is True
    assert result.wrote == []
    assert result.usd == 0.0


def test_the_backend_is_named_for_its_runtime():
    assert AgentSdkBackend(options=None).name == "agent_sdk"


# -- _changed_files --------------------------------------------------------


def test_changed_files_reads_the_names_git_diff_prints(tmp_path, monkeypatch):
    class _Proc:
        def __init__(self, stdout):
            self.stdout = stdout

    def fake_run(argv, **kwargs):
        assert kwargs["cwd"] == tmp_path
        if argv[:2] == ["git", "diff"]:
            return _Proc("app/models.py\ntickets/T001.md\n")
        if argv[:2] == ["git", "ls-files"]:
            return _Proc("tickets/new.md\n")
        raise AssertionError(argv)

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert adapter._changed_files(tmp_path) == {"app/models.py", "tickets/T001.md", "tickets/new.md"}


def test_changed_files_on_a_clean_tree_is_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda argv, **kwargs: type("P", (), {"stdout": ""})())
    assert adapter._changed_files(tmp_path) == set()


# -- the success path ------------------------------------------------------


def test_run_returns_only_the_last_result_message(tmp_path, monkeypatch, changed):
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", make_sdk_module(["first", "second"]))
    changed.extend([set(), set()])
    result = AgentSdkBackend(options=None).run(repo=tmp_path, prompt="do it", allow=["tickets/**"])
    assert result.ok is True
    assert result.output == "second"


def test_run_returns_the_last_ticket_shaped_subagent_block_for_a_doer(tmp_path, monkeypatch, changed):
    class ToolOnlySubagentMessage:
        content = []
        parent_tool_use_id = "toolu_doer"

    class Text:
        text = "---\nid: T001\n---\n\n# Rewritten ticket"

    class SubagentMessage:
        content = [Text()]
        parent_tool_use_id = "toolu_doer"

    monkeypatch.setitem(
        sys.modules,
        "claude_agent_sdk",
        make_sdk_module(
            [
                ToolOnlySubagentMessage(),
                SubagentMessage(),
                FakeResultMessage(result="The doer completed the draft."),
            ]
        ),
    )
    changed.extend([set(), set()])
    result = AgentSdkBackend(options=None).run(
        repo=tmp_path, prompt="draft", allow=[], return_subagent_text=True
    )
    assert result.output == "---\nid: T001\n---\n\n# Rewritten ticket"


def test_run_prefers_a_ticket_shaped_parent_result_over_subagent_text(tmp_path, monkeypatch, changed):
    class Text:
        text = "# Older child ticket"

    class SubagentMessage:
        content = [Text()]
        parent_tool_use_id = "toolu_doer"

    monkeypatch.setitem(
        sys.modules,
        "claude_agent_sdk",
        make_sdk_module([SubagentMessage(), FakeResultMessage(result="# Parent ticket")]),
    )
    changed.extend([set(), set()])
    result = AgentSdkBackend(options=None).run(
        repo=tmp_path, prompt="draft", allow=[], return_subagent_text=True
    )
    assert result.output == "# Parent ticket"


def test_run_never_joins_intermediate_tool_output_into_a_ticket(tmp_path, monkeypatch, changed):
    class Text:
        text = "\\n30\\tintermediate Grep dump"

    class ToolMessage:
        content = [Text()]
        parent_tool_use_id = "toolu_doer"

    class TicketText:
        text = "---\nid: T001\n---\n\n# Clean candidate"

    class FinalSubagentMessage:
        content = [TicketText()]
        parent_tool_use_id = "toolu_doer"

    monkeypatch.setitem(
        sys.modules,
        "claude_agent_sdk",
        make_sdk_module(
            [
                ToolMessage(),
                FinalSubagentMessage(),
                FakeResultMessage(result="The doer completed the draft."),
            ]
        ),
    )
    changed.extend([set(), set()])
    result = AgentSdkBackend(options=None).run(
        repo=tmp_path, prompt="draft", allow=[], return_subagent_text=True
    )
    assert result.output == "---\nid: T001\n---\n\n# Clean candidate"


def test_run_reports_a_new_file_inside_the_allow_list(tmp_path, monkeypatch, changed):
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", make_sdk_module(["done"]))
    changed.extend([set(), {"tickets/T001.md"}])
    result = AgentSdkBackend(options=None).run(repo=tmp_path, prompt="do it", allow=["tickets/**"])
    assert result.wrote == ["tickets/T001.md"]


def test_run_does_not_report_a_file_outside_the_allow_list(tmp_path, monkeypatch, changed):
    """The hook is what blocks the write. This filter is the second line.

    An out-of-scope change is dropped from `wrote` rather than reported as a
    violation, so a caller reading `wrote` never sees a path the role could not
    have written.
    """
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", make_sdk_module(["done"]))
    changed.extend([set(), {"tickets/T001.md", "app/models.py"}])
    result = AgentSdkBackend(options=None).run(repo=tmp_path, prompt="do it", allow=["tickets/**"])
    assert result.wrote == ["tickets/T001.md"]
    assert "app/models.py" not in result.wrote


def test_run_ignores_a_file_that_was_already_dirty_before_it_started(
    tmp_path, monkeypatch, changed
):
    """Someone else's uncommitted edit is not this doer's work."""
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", make_sdk_module(["done"]))
    changed.extend([{"tickets/T000.md"}, {"tickets/T000.md", "tickets/T001.md"}])
    result = AgentSdkBackend(options=None).run(repo=tmp_path, prompt="do it", allow=["tickets/**"])
    assert result.wrote == ["tickets/T001.md"]


def test_run_sorts_the_paths_it_reports(tmp_path, monkeypatch, changed):
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", make_sdk_module(["done"]))
    changed.extend([set(), {"tickets/c.md", "tickets/a.md", "tickets/b.md"}])
    result = AgentSdkBackend(options=None).run(repo=tmp_path, prompt="do it", allow=["tickets/**"])
    assert result.wrote == ["tickets/a.md", "tickets/b.md", "tickets/c.md"]


def test_run_reports_nothing_when_the_doer_wrote_nothing(tmp_path, monkeypatch, changed):
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", make_sdk_module([]))
    changed.extend([set(), set()])
    result = AgentSdkBackend(options=None).run(repo=tmp_path, prompt="do it", allow=["tickets/**"])
    assert result.ok is True
    assert result.wrote == []
    assert result.output == ""


def test_run_passes_the_prompt_and_the_options_through(tmp_path, monkeypatch, changed):
    seen = {}
    module = make_sdk_module([])

    async def query(*, prompt, options):
        seen["prompt"] = prompt
        seen["options"] = options
        return
        yield  # pragma: no cover  (makes this an async generator)

    module.query = query
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", module)
    changed.extend([set(), set()])
    sentinel = object()
    AgentSdkBackend(options=sentinel).run(repo=tmp_path, prompt="groom T001", allow=[])
    assert seen == {"prompt": "groom T001", "options": sentinel}


def test_an_empty_allow_list_reports_no_writes_at_all(tmp_path, monkeypatch, changed):
    """A role with no declared scope wrote nothing this loop is willing to claim."""
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", make_sdk_module(["done"]))
    changed.extend([set(), {"tickets/T001.md"}])
    result = AgentSdkBackend(options=None).run(repo=tmp_path, prompt="do it", allow=[])
    assert result.wrote == []


# -- the failure paths -----------------------------------------------------


def test_run_fails_gracefully_when_the_sdk_is_not_installed(tmp_path, monkeypatch, changed):
    """The package is optional, so its absence is a result, not a traceback."""
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", None)
    result = AgentSdkBackend(options=None).run(repo=tmp_path, prompt="do it", allow=[])
    assert result.ok is False
    assert result.output.startswith("agent sdk backend failed:")
    assert result.wrote == []


def test_run_fails_gracefully_when_the_query_raises(tmp_path, monkeypatch, changed):
    module = make_sdk_module([])

    async def query(*, prompt, options):
        raise RuntimeError("no api key")
        yield  # pragma: no cover  (makes this an async generator)

    module.query = query
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", module)
    changed.extend([set(), set()])
    result = AgentSdkBackend(options=None).run(repo=tmp_path, prompt="do it", allow=[])
    assert result.ok is False
    assert "no api key" in result.output


def test_run_fails_gracefully_when_git_is_not_available(tmp_path, monkeypatch):
    def boom(repo):
        raise FileNotFoundError("git not found")

    monkeypatch.setitem(sys.modules, "claude_agent_sdk", make_sdk_module([]))
    monkeypatch.setattr(adapter, "_changed_files", boom)
    result = AgentSdkBackend(options=None).run(repo=tmp_path, prompt="do it", allow=[])
    assert result.ok is False
    assert "git not found" in result.output


def test_a_failed_run_never_claims_a_write(tmp_path, monkeypatch, changed):
    """Reporting a write from a failed run is how a loop fakes progress."""
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", None)
    result = AgentSdkBackend(options=None).run(repo=tmp_path, prompt="do it", allow=["**"])
    assert result.wrote == []


def test_run_reads_result_message_cost_and_structured_output(tmp_path, monkeypatch, changed):
    message = FakeResultMessage(
        result='{"kind": "bug", "present_fields": ["title"]}',
        total_cost_usd=1.25,
        structured_output={"kind": "bug", "present_fields": ["title"]},
    )
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", make_sdk_module([message]))
    changed.extend([set(), set()])
    result = AgentSdkBackend(options=None).run(repo=tmp_path, prompt="grade", allow=[])
    assert result.usd == 1.25
    assert result.structured["kind"] == "bug"
    assert result.ok is True


def test_run_maps_max_turns_subtype_to_a_stop_reason(tmp_path, monkeypatch, changed):
    message = FakeResultMessage(total_cost_usd=0.1, is_error=True, subtype="error_max_turns")
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", make_sdk_module([message]))
    changed.extend([set(), set()])
    result = AgentSdkBackend(options=None).run(repo=tmp_path, prompt="grade", allow=[])
    assert result.ok is False
    assert result.stop_reason == "max turns"


def test_run_times_out_a_hung_query(tmp_path, monkeypatch, changed):
    module = make_sdk_module([])

    async def query(*, prompt, options):
        await adapter.asyncio.sleep(1)
        yield FakeResultMessage(result="# never reached")

    module.query = query
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", module)
    monkeypatch.setattr(adapter, "QUERY_TIMEOUT_SECONDS", 0.001)
    changed.extend([set(), set()])
    result = AgentSdkBackend(options=None).run(repo=tmp_path, prompt="draft", allow=[])
    assert result.ok is False
    assert result.stop_reason == "query timeout"
    assert result.raw_output == ""
