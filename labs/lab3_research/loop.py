"""Lab 3. The research assistant.

Fill the two functions below.

Perplexity is optional. If you have no key, pass `--backend websearch` and use
your agent's own search tool, or `--backend fixture` to run offline. The loop
does not know which one it is holding.

Read `solutions/sol3_research/researcher.py` and `solutions/sol3_research/brief.py` only if you stall.
"""

from __future__ import annotations

import brief


def plan_questions(question: str) -> list[str]:
    """Break one question into the sub-questions a brief needs.

    A plan step you cannot check is a wish. Each sub-question should be one you
    can tell was answered or not.
    """
    raise NotImplementedError("fill me in")


def check_brief(body: str, sources: list[str]) -> brief.BriefScore:
    """Check the brief without asking a model.

    Two things are arithmetic, not judgement:

      grounded  every citation marker resolves to a source actually retrieved
      cited     every claim paragraph carries a citation

    A confident sentence nobody can trace is the failure that matters.
    """
    raise NotImplementedError("fill me in")
