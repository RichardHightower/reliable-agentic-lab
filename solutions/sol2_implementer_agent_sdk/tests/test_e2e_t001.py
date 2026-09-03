"""The live T001 path wraps a local Backend. No SDK. No sibling folder."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import e2e_t001


class FakeAgentSdkBackend:
    def __init__(self):
        self.prompt = ""
        self.calls = 0

    def run(self, *, repo: Path, prompt: str, allow: list[str]):
        self.prompt = prompt
        self.calls += 1
        return SimpleNamespace(
            wrote=["tests/test_due_date.py"],
            output="test created",
            usd=0.12,
            ok=True,
            stop_reason=None,
        )


def test_the_e2e_wrapper_is_a_doers_backend(tmp_path):
    """The driver must not reinterpret the SDK object as a CLI command."""
    delegate = FakeAgentSdkBackend()
    wrapper = e2e_t001.AgentSdkE2EBackend(delegate)

    assert e2e_t001.doers.build(wrapper) is wrapper

    result = wrapper.run(
        repo=tmp_path,
        prompt="Implement the ready ticket.",
        allow=["tests/**"],
    )

    assert result.wrote == ["tests/test_due_date.py"]
    assert result.usd == 0.12
    assert delegate.prompt.startswith("Delegate only to implementer-test-implementer.")
    assert wrapper.calls[0].phase == "test"


def test_the_e2e_wrapper_selects_the_backend_for_each_phase(tmp_path):
    tester = FakeAgentSdkBackend()
    coder = FakeAgentSdkBackend()
    inner = e2e_t001.adapter.AgentSdkPhaseBackend(test=tester, code=coder)
    wrapper = e2e_t001.AgentSdkE2EBackend(inner)

    wrapper.run(repo=tmp_path, prompt="test", allow=["tests/**"])
    wrapper.run(repo=tmp_path, prompt="code", allow=["app/**"])

    assert tester.calls == 1
    assert coder.calls == 1


def test_the_live_turn_ceiling_is_high_enough_for_a_green_run():
    assert e2e_t001.E2E_MAX_TURNS >= 12


def test_a_controlled_sdk_turn_ceiling_is_not_a_failed_query(tmp_path):
    delegate = FakeAgentSdkBackend()
    original_run = delegate.run

    def stopped(**kwargs):
        result = original_run(**kwargs)
        result.ok = False
        result.stop_reason = "max turns"
        return result

    delegate.run = stopped
    wrapper = e2e_t001.AgentSdkE2EBackend(delegate)

    wrapper.run(repo=tmp_path, prompt="test", allow=["tests/**"])

    assert not wrapper.query_failed


def test_the_e2e_command_refuses_before_querying_without_a_credential(tmp_path, monkeypatch, capsys):
    """A missing key is a preflight failure, not a live Agent SDK attempt."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    monkeypatch.setattr(e2e_t001, "_load_operator_env", lambda: None)

    assert e2e_t001.main(["--repo", str(tmp_path)]) == 2
    assert "needs ANTHROPIC_API_KEY" in capsys.readouterr().err


def test_the_e2e_loader_checks_local_then_parent_then_checkout_root(monkeypatch, tmp_path):
    """The direct Python command follows the documented dotenv search order."""
    folder = tmp_path / "solutions" / "sol2_implementer_agent_sdk"
    folder.mkdir(parents=True)
    (folder.parent.parent / ".env").write_text("ANTHROPIC_API_KEY=root\n", encoding="utf-8")
    (folder.parent / ".env").write_text("ANTHROPIC_API_KEY=parent\n", encoding="utf-8")
    (folder / ".env").write_text("ANTHROPIC_API_KEY=local\n", encoding="utf-8")
    monkeypatch.setattr(e2e_t001, "FOLDER", folder)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    e2e_t001._load_operator_env()

    assert e2e_t001.os.environ["ANTHROPIC_API_KEY"] == "local"
