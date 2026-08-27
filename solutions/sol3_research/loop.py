"""Lab 3. The research assistant. Filled in.

This is the lab 3 answer, the same file as `solutions/sol3_research/`.

The backend does not appear anywhere in this file. That is the point of a tool
boundary: the loop calls one function and never learns whether Perplexity, the
built-in WebSearch tool, or a recorded fixture answered it.
"""

from __future__ import annotations

import brief, researcher


def plan_questions(question: str) -> list[str]:
    """Break one question into the sub-questions a brief needs.

    Each sub-question is one you can tell was answered or not. A plan step you
    cannot check is a wish.
    """
    return researcher.plan_questions(question)


def check_brief(body: str, sources: list[str]) -> brief.BriefScore:
    """Check the brief without asking a model.

    `brief.check` resolves every citation marker against the sources actually
    retrieved, and finds every claim paragraph that carries no citation. Both
    are arithmetic. A confident sentence nobody can trace is the failure that
    matters, and a model judge is the wrong tool for catching it.
    """
    return brief.check(body, sources)
