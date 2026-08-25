from __future__ import annotations


def check(*, grader: dict, previous_failed: list[str] | None) -> dict:
    """Checker has no write tools. It only reads the grader output."""
    failed = list(grader.get("failed_node_ids") or [])
    summary = "hidden grader passed" if grader.get("passed") else "hidden grader failed: " + ", ".join(failed)
    return {
        "summary": summary,
        "failed_node_ids": failed,
        "repeat_failure": previous_failed is not None and failed == previous_failed,
        "passed": bool(grader.get("passed")),
    }
