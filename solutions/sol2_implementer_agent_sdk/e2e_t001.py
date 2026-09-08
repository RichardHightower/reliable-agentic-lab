#!/usr/bin/env python3
"""Run the Agent SDK port through the Lab 2 T001 harness.

This folder owns the loop. `implementer.run` lives here. This file is the
live operator path: one Agent SDK backend per phase, a hook audit, and a
credential preflight. Copy this folder somewhere else and it still runs.
"""

from __future__ import annotations

import argparse
import inspect
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import adapter
import contract
import doers
import implementer
import roleplan
from load_agents import DEFAULT_MAX_TURNS

FOLDER = Path(__file__).resolve().parent
MAX_TOTAL_USD = 2.0
E2E_MAX_TURNS = DEFAULT_MAX_TURNS
CONTROLLED_STOPS = frozenset({"max turns", "cost budget spent"})


def _load_operator_env() -> None:
    """Load only SDK auth variables for the direct, non-Task invocation.

    The documented E2E command executes Python directly, so Task's ``dotenv``
    support is not present. Keep this tiny loader deliberately narrow: it
    accepts the two supported auth keys, does not replace an exported value,
    and never prints a secret.
    """
    for path in (FOLDER / ".env", FOLDER.parent / ".env", FOLDER.parent.parent / ".env"):
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            name, separator, value = line.partition("=")
            if separator and name in {"ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN"}:
                os.environ.setdefault(name, value.strip().strip("\"'"))


def _has_sdk_credential() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"))


def _phase(allow: list[str]) -> tuple[str, str]:
    if any(pattern.startswith("tests/") for pattern in allow):
        return "test", "implementer-test-implementer"
    if any(pattern.startswith(("app/", "src/")) for pattern in allow):
        return "code", "implementer-code-implementer"
    return "unknown", ""


@dataclass
class Call:
    phase: str
    agent: str
    wrote: list[str]
    usd: float | None
    ok: bool
    stop_reason: str | None
    # #539. The proof, not just the verdict. Dropped here on the old code
    # path, so a failed live run left nothing for `_write_extras` to write.
    raw_output: str = ""


class AgentSdkE2EBackend(doers.Backend):
    """Wrap the phase backend with spend tracking and a hook-friendly name."""

    name = "agent_sdk"

    def __init__(self, backend: Any, *, max_total_usd: float = MAX_TOTAL_USD):
        self.backend = backend
        self.max_total_usd = max_total_usd
        self.calls: list[Call] = []
        self.spent_usd = 0.0

    @property
    def query_failed(self) -> bool:
        return any(not call.ok and call.stop_reason not in CONTROLLED_STOPS for call in self.calls)

    def _bookkeep(self, *, phase: str, agent: str, result: Any) -> float | None:
        """Record the call and return the usd this turn reported.

        #539. `None` means the backend never answered; coercing it to 0.0
        with `or` is the exact silent-zero bug this ticket exists to kill.
        The budget still moves (an unknown turn spends 0.0 against it), but
        the number this method returns, and the trace that reads it, keeps
        the `None`.
        """
        raw_usd = getattr(result, "usd", None)
        usd = None if raw_usd is None else float(raw_usd)
        self.spent_usd += usd if usd is not None else 0.0
        self.calls.append(
            Call(
                phase=phase,
                agent=agent,
                wrote=list(getattr(result, "wrote", ()) or ()),
                usd=usd,
                ok=bool(getattr(result, "ok", False)),
                stop_reason=getattr(result, "stop_reason", None),
                raw_output=str(getattr(result, "raw_output", "") or ""),
            )
        )
        return usd

    def run(self, *, repo: Path, prompt: str, allow: list[str]):
        phase, agent = _phase(allow)
        if self.spent_usd >= self.max_total_usd:
            result = doers.DoerResult(
                ok=False,
                usd=None,
                output=f"Agent SDK E2E budget exhausted at ${self.spent_usd:.2f}",
            )
            self.calls.append(Call(phase, agent, [], None, False, "cost budget spent"))
            return result

        instruction = f"Delegate only to {agent}. {prompt}" if agent else prompt
        result = self.backend.run(repo=repo, prompt=instruction, allow=allow)
        usd = self._bookkeep(phase=phase, agent=agent, result=result)
        return doers.DoerResult(
            wrote=list(getattr(result, "wrote", ()) or ()),
            output=str(getattr(result, "output", "")),
            usd=usd,
            ok=bool(getattr(result, "ok", False)),
            structured=getattr(result, "structured", None),
            stop_reason=getattr(result, "stop_reason", None),
            raw_output=str(getattr(result, "raw_output", "") or ""),
        )

    def judge(self, *, repo: Path, prompt: str):
        result = self.backend.judge(repo=repo, prompt=prompt)
        self._bookkeep(phase="judge", agent="implementer-judge", result=result)
        return result


def _path_from_hook(input_data: dict) -> str | None:
    tool_input = input_data.get("tool_input") or {}
    for key in ("file_path", "path", "notebook_path"):
        if key in tool_input:
            return str(tool_input[key])
    return None


def _instrument_hooks(options, audit: list[dict[str, str | None]]) -> None:
    """Record redacted tool metadata while preserving the port's deny hook."""
    matchers = options.hooks.get("PreToolUse", [])
    for index, matcher in enumerate(matchers):
        wrapped = []
        for original in matcher.hooks:

            async def audit_hook(input_data, tool_use_id, context, *, original=original):
                audit.append(
                    {
                        "tool": input_data.get("tool_name"),
                        "path": _path_from_hook(input_data),
                        "agent_type": input_data.get("agent_type"),
                    }
                )
                answer = original(input_data, tool_use_id, context)
                return await answer if inspect.isawaitable(answer) else answer

            wrapped.append(audit_hook)
        try:
            matcher.hooks = wrapped
        except (AttributeError, TypeError):
            replacement = None
            if hasattr(matcher, "model_copy"):
                replacement = matcher.model_copy(update={"hooks": wrapped})
            if replacement is None:
                raise RuntimeError(
                    "Agent SDK HookMatcher does not permit hook instrumentation"
                ) from None
            matchers[index] = replacement


def _build_backend(repo: Path, budget: int | None) -> tuple[AgentSdkE2EBackend, list[dict]]:
    """Build one capped SDK backend for the driver without calling a model."""
    if budget is not None and budget < 1:
        raise ValueError("--budget must be at least 1")
    target = contract.Contract(repo)
    iterations = budget if budget is not None else int(target.budget.get("iterations", 3))
    per_query_usd = MAX_TOTAL_USD / (iterations + 2)
    audit: list[dict] = []
    phases = {}
    for phase, role_name in (
        ("test", "test_implementer"),
        ("code", "code_implementer"),
        ("judge", "judge"),
    ):
        options = sdk_options_with_budget(target, role_name, per_query_usd)
        _instrument_hooks(options, audit)
        phases[phase] = adapter.AgentSdkBackend(options)
    inner = adapter.AgentSdkPhaseBackend(
        test=phases["test"], code=phases["code"], judge=phases["judge"]
    )
    return AgentSdkE2EBackend(inner), audit


def sdk_options_with_budget(target, role_name: str, per_query_usd: float):
    import roles as sdk_roles  # noqa: PLC0415

    return sdk_roles.options_for(
        target,
        max_usd=per_query_usd,
        max_turns=E2E_MAX_TURNS,
        role_names=frozenset({role_name}),
    )


def _write_extras(repo: Path, trace: dict, backend: AgentSdkE2EBackend, audit: list[dict]) -> None:
    """Write operator-safe evidence next to the shared harness receipt."""
    out = Path(repo) / ".harness"
    out.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Agent SDK T001 E2E",
        "",
        f"gate: {trace.get('gate', 'missing')}",
        f"reason: {trace.get('reason', 'missing')}",
        f"spent_usd: {backend.spent_usd:.4f}",
        # #539(e). The cap this run actually applied, not a number a status
        # note has to guess or invent after the fact.
        f"cap_usd: {backend.max_total_usd:.2f}",
        f"query_failed: {backend.query_failed}",
        "",
        "## Phases",
    ]
    for index, call in enumerate(backend.calls):
        usd_text = "unknown" if call.usd is None else format(call.usd, ".4f")
        lines.extend(
            (
                f"- {call.phase} via {call.agent or 'unknown'}: ok={call.ok} "
                f"usd={usd_text} stop={call.stop_reason or 'none'}",
                f"  wrote: {', '.join(call.wrote) or 'nothing'}",
            )
        )
        # #539. The proof, kept even on a failed call. Written per call
        # rather than inlined: a raw event log can run to hundreds of lines,
        # and the earlier bug was losing this entirely, not formatting it.
        if call.raw_output:
            raw_name = f"last-sdk-e2e-raw-{index}-{call.phase}.txt"
            (out / raw_name).write_text(call.raw_output, encoding="utf-8")
            lines.append(f"  raw: .harness/{raw_name}")
    lines.extend(("", "## Hook audit"))
    for event in audit:
        lines.append(
            f"- tool={event['tool'] or 'unknown'} agent={event['agent_type'] or 'unknown'} "
            f"path={event['path'] or 'none'}"
        )
    (out / "last-sdk-e2e.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    diff = subprocess.run(
        ["git", "diff", "--stat"], cwd=repo, text=True, capture_output=True, check=False
    )
    (out / "last-sdk-e2e-diff.txt").write_text(diff.stdout, encoding="utf-8")


def _print_table() -> None:
    print(roleplan.table(roleplan.plan(None, "implementer")))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=False, default="../../work/northwind-field-crm")
    parser.add_argument("--ticket", default="T001")
    parser.add_argument("--budget", type=int)
    parser.add_argument("--table-only", action="store_true")
    args = parser.parse_args(argv)

    if args.table_only:
        _print_table()
        return 0

    _load_operator_env()
    if not _has_sdk_credential():
        print(
            "Agent SDK E2E needs ANTHROPIC_API_KEY or CLAUDE_CODE_OAUTH_TOKEN "
            "in the environment or this worktree's .env.",
            file=sys.stderr,
        )
        return 2

    repo = Path(args.repo).expanduser().resolve()
    try:
        backend, audit = _build_backend(repo, args.budget)
        trace = implementer.run(repo=repo, ticket_id=args.ticket, doer=backend, budget=args.budget)
    except Exception as exc:
        print(f"Agent SDK E2E setup failed: {exc}", file=sys.stderr)
        return 2

    # #506. `implementer.run` does all its work in `<repo>.worktrees/<ticket>`
    # (`_worktree`), never against `repo` itself, and writes `.harness/`
    # there. `trace["repo"]` is that worktree path; write the summary beside
    # the `.harness/` the run itself produced, not next to the clone.
    _write_extras(Path(trace["repo"]), trace, backend, audit)
    print(trace.get("rubric", ""))
    print()
    print(f"gate: {trace.get('gate', 'missing')}")
    print(f"reason: {trace.get('reason', 'missing')}")
    if backend.query_failed:
        # #506 follow-up (judge of PR #527, item 4). A bare relative path
        # here reads as living next to wherever this command was invoked
        # from, not the worktree `_write_extras` actually wrote to above.
        summary_path = Path(trace["repo"]) / ".harness" / "last-sdk-e2e.md"
        print(f"Agent SDK query failed; see {summary_path}", file=sys.stderr)
        return 2
    return 0 if trace.get("gate") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
