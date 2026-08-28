"""The handoff is a subprocess into solutions/sol1_enhancer. No import of that folder."""

from __future__ import annotations

from pathlib import Path

from solutions.extra_credit.s_ext_1_webhook import call_sol1


def test_default_backend_is_the_claude_plugin():
    folder = call_sol1.sol1_dir(backend="claude")
    assert folder.name == "sol1_enhancer"
    assert folder.parent.name == "solutions"


def test_command_is_task_run_ticket():
    assert call_sol1.command_for("T001") == ["task", "run", "--", "--ticket", "T001"]


def test_runner_override_never_spawns(tmp_path: Path):
    seen: dict = {}

    def runner(*, ticket_id, backend, cwd):
        seen["ticket_id"] = ticket_id
        seen["backend"] = backend
        seen["cwd"] = cwd
        return {"returncode": 0, "stdout": "ok", "stderr": ""}

    result = call_sol1.run_sol1("T900", backend="claude", runner=runner)
    assert result["returncode"] == 0
    assert seen["ticket_id"] == "T900"
    assert seen["cwd"].name == "sol1_enhancer"


def test_ticket_id_from_title():
    from solutions.extra_credit.s_ext_1_webhook.webhook import ticket_id_from_issue

    assert ticket_id_from_issue({"title": "[T001] Add due dates"}) == "T001"
    assert ticket_id_from_issue({"title": "nope", "body": "id: T042\n\nHi"}) == "T042"
    assert ticket_id_from_issue({"title": "nothing"}) is None
