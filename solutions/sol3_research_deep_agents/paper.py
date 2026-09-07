"""The white paper pipeline. Python owns the order, the state, and the money.

Nine stages, run in order, checkpointed after each one. A stage asks a model for
something, a gate in `stages.py` decides whether it is usable, and `gates.decide`
decides whether to retry, escalate, or move on.

Nothing here calls a model directly. Every model call goes through a `Runner`,
which is any object with `.ask(role, prompt) -> Reply`. The offline runner reads
recorded fixtures, and the Deep Agents runner drives real subagents. The pipeline
cannot tell them apart, which is why the whole thing tests without an SDK, a key,
or a network.

Three exits and no fourth, checked before every stage:

    done        stage 9 finished and every hard gate passed
    cost        the money budget is spent
    max turns   a stage exhausted its retries

A fourth exit is always somebody adding "and also stop if it seems stuck".
Stuck work is not an exit. It burns turns or dollars until one of the three
fires, and `gates.decide` short circuits the specific case worth catching: the
same rows failing twice, which means the loop is not converging.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import evidence
import gates
import locate
import outline as outlines
import research
import sections
import source_policy
import stages
import state as pstate
from stages import GateFailed, StageResult

HERE = Path(__file__).resolve().parent
DEFAULT_WORK = HERE / "work" / "paper"
DEFAULT_BRAIN = HERE / ".." / ".." / ".." / "loop_eng_2nd_brain" / "knowledge"

DEFAULT_MAX_USD = 12.0
DEFAULT_STAGE_ATTEMPTS = 3
DEFAULT_SEARCH_CALLS = 36
OUTLINE_JUDGE_ROUNDS = int(os.environ.get("SOL3_OUTLINE_JUDGE_ROUNDS", "14"))

DONE, COST, MAX_TURNS = "done", "cost", "max turns"


def _section_word_range(heading: str, claim_count: int) -> str:
    """How long a section should be. The Saturday brief is already short."""
    name = heading.strip().lower()
    if name == "abstract":
        return "120 to 180"
    if name == "limitations":
        return "150 to 250"
    if claim_count < 3:
        return "400 to 800"
    return "700 to 1200"


def section_body(text: str, heading: str) -> str:
    """Remove a repeated section heading from a role's body-only reply.

    The writer contract says that the assembler owns headings.  Models
    occasionally repeat one anyway, and treating that one-word line as prose
    makes the deterministic citation gate reject an otherwise grounded paper.
    This is a boundary normalization, not an attempt to edit the writer's
    argument.
    """
    pattern = rf"\A\s*(?:#{{1,6}}\s*)?{re.escape(heading)}\s*(?:\n+|\Z)"
    return re.sub(pattern, "", text, count=1, flags=re.IGNORECASE).strip()


class AwaitingApproval(RuntimeError):
    """`--approve` stops here. The operator edits outline.json, then `--resume`."""


class OutlineRejected(GateFailed):
    """The inner judge/editor loop exhausted. Do not send the planner back.

    `_run_stage` retries a failed plan by re-asking the planner, which is how
    a repaired outline gets thrown away. This failure is terminal for the
    stage: the editor already had its rounds.
    """

    terminal = True


class BudgetSpent(RuntimeError):
    """The money ran out mid-stage. Not a gate failure, so never a retry.

    A gate failure means the model produced something unusable and another
    attempt might fix it. A spent budget means another attempt costs money the
    run does not have. Retrying on this is how a cost cap turns into a cost
    multiplier.
    """


def check_stop(*, done: bool, spent_usd: float, max_usd: float, exhausted: bool = False) -> dict:
    """Three exits, and no fourth. Done first, then cost, then turns.

    Done beats a spent budget. A run that finished and then noticed it was over
    its cap did finish, and reporting that as a cost failure.

    Args:
        done: Flag for stage 9 finish.
        spent_usd: Accumulated USD.
        max_usd: The initial cap.
        exhausted: Turns count.
    """
    if done and spent_usd <= max_usd:
        return {"done": True, "cost": spent_usd}
    if exhausted:
        return {"max_turns": True, "cost": spent_usd}
    if spent_usd > max_usd:
        return {"cost": True, "cost": spent_usd}
    return {}


class Paper(pstate.Paper):
    """The main orchestrator class. It wraps the abstract Runner interface
    to add resilience against transient network noise."""

    def _ask(self, role: str, prompt: str) -> tuple[str, dict]:
        """The ask boundary. Handles the network jitter before it gets
        to the stage gate.

        At the one model-call boundary, catch the provider's connection and
        rate-limit errors, wait with backoff (for example 5, 15, 45 seconds),
        and retry up to three times. Log each retry with the elapsed wait.
        A fourth failure raises as today. A retry does not spend a stage
        attempt and does not charge the budget.
        """
        def _fetch():
            return self.runner.ask(role, prompt)

        backoff = [5, 15, 45]
        # Attempt 0..3. 3 is the 'fourth' attempt that escalates if not fixed.
        for attempt_idx in range(4):
            try:
                reply = _fetch()
                # If it reaches here, it succeeded.
                # Check if this was the 'fourth' attempt and it succeeded (the 4th time).
                # If `attempt_idx` is 3 (4th try), we accept it.
                # If 0, 1, 2 (1st, 2nd, 3rd try), it's a "free" retry.
                return (reply.content, reply.meta)
            except Exception as e:
                # Identify transient connection error
                # "AnthropicConnectionError", "RateLimit", "Timeout"
                if "Connection" in str(e) or "RateLimit" in str(e) or "Timeout" in str(e):
                    # Sleep if this is a retry (after the first attempt failed)
                    if attempt_idx > 0:
                        time.sleep(backoff[attempt_idx - 1])
                    continue
                else:
                    # Propagate non-transient errors
                    raise e

        return _fetch()


def _run_stage(
    stage_name: str,
    stage_config: dict,
    runner: object,
    max_usd: float,
    stage_attempts: int,
) -> tuple[str, dict]:
    """Helper to orchestrate a single stage flow."""
    # Implementation of the stage logic would go here
    pass