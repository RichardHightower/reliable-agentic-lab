"""Stop conditions. Python holds the loop, not the model.

Three exits and no fourth: pass, retry, escalate.

Ported from the editor and checker loop in articles v3, which learned these the
expensive way:

    articles/article-creator-plugin/v3/article_pipeline/checker/retry_loop.py

The one most people miss is stable failure. When this attempt fails in exactly
the same way as the last one, the loop is not converging. Spending the rest of
the budget to watch it fail identically two more times buys a surprise bill,
not a fix.
"""

from __future__ import annotations

from dataclasses import dataclass

PASS, RETRY, ESCALATE = "pass", "retry", "escalate"

DEFAULT_ITERATIONS = 3


@dataclass
class Decision:
    gate: str
    reason: str
    final_attempt: bool = False
    repeat_failure: bool = False

    @property
    def stop(self) -> bool:
        return self.gate != RETRY


def decide(  # noqa: PLR0913, PLR0911
    *,
    passed: bool,
    iteration: int,
    budget: int = DEFAULT_ITERATIONS,
    signature: tuple[str, ...] = (),
    previous_signature: tuple[str, ...] | None = None,
    usd_left: float = 1.0,
    judge_done: bool | None = None,
) -> Decision:
    """Choose the next move.

    `signature` is what failed, not how it was worded. Two equal signatures mean
    the last attempt changed nothing.

    `judge_done` is the final judge's verdict. None means it did not run, which
    is not the same as agreeing.

    One return per reason to stop. The reason is what the room reads off the
    trace, so collapsing the branches would save a line and cost the lesson.
    """
    if passed and judge_done is None:
        return Decision(PASS, "the rubric is green")
    if passed and judge_done:
        return Decision(PASS, "the rubric is green and the final judge agrees")
    if passed and not judge_done:
        return Decision(
            ESCALATE,
            "the rubric is green but the final judge says the ticket is not done",
        )

    if previous_signature is not None and signature == previous_signature:
        return Decision(
            ESCALATE,
            f"the same rows failed twice: {', '.join(signature) or 'unknown'}. "
            "The loop is not converging.",
            repeat_failure=True,
        )

    if usd_left <= 0:
        return Decision(ESCALATE, "the money budget is spent")

    if iteration >= budget:
        return Decision(ESCALATE, f"the iteration budget is spent after {budget} attempts")

    return Decision(
        RETRY,
        f"attempt {iteration} of {budget} failed: {', '.join(signature) or 'unknown'}",
        final_attempt=(iteration + 1 >= budget),
    )


def retry_instruction(decision: Decision, failed_rows: list[str]) -> str:
    """What to hand the doer on a retry.

    On the last attempt, narrow the ask. A doer that spends its final turn
    polishing a minor row leaves the blocking one unfixed.
    """
    rows = ", ".join(failed_rows) or "unknown"
    if decision.final_attempt:
        return (
            f"FINAL ATTEMPT. Fix only what blocks: {rows}. "
            "Do not refactor. Do not address anything else."
        )
    return f"These rubric rows failed: {rows}. Fix them."


def demo() -> int:
    """Assert the exits against their own examples. No pytest, no network."""
    assert decide(passed=True, iteration=1).gate == PASS
    assert decide(passed=True, iteration=1, judge_done=True).gate == PASS
    assert decide(passed=True, iteration=1, judge_done=False).gate == ESCALATE

    # A stall is reported before the budget, because "it stopped converging" is
    # the actionable reason and "it ran out of turns" hides it.
    stall = decide(
        passed=False, iteration=1, budget=9, signature=("cited",), previous_signature=("cited",)
    )
    assert stall.gate == ESCALATE and stall.repeat_failure, stall

    assert decide(passed=False, iteration=1, budget=9, usd_left=0.0).gate == ESCALATE
    assert decide(passed=False, iteration=3, budget=3).gate == ESCALATE

    retry = decide(passed=False, iteration=1, budget=3, signature=("images",))
    assert retry.gate == RETRY and not retry.stop and not retry.final_attempt, retry
    assert decide(passed=False, iteration=2, budget=3).final_attempt

    assert "FINAL ATTEMPT" in retry_instruction(Decision(RETRY, "", final_attempt=True), ["cited"])
    assert "FINAL ATTEMPT" not in retry_instruction(Decision(RETRY, ""), ["cited"])

    print("gates: ok")
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(demo() if "--demo" in sys.argv else 0)
