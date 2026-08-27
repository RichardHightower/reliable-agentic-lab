"""Deterministic checks on a written brief.

Both of these come from articles v3, and both are checks a model does not get a
vote on. The lesson is the same one Module 2 teaches about code: check what you
can check without asking, and save the model for what needs judgement.

    grounding   every claim traces to a source that was actually retrieved
    style       an em dash is replaced, not argued about
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

CITATION = re.compile(r"\[(\d+)\]")
EM_DASH = re.compile(r"\s*—\s*")
EN_DASH = re.compile(r"(?<=\w)\u2013(?=\w)")
CODE_SPAN = re.compile(r"`[^`]*`|```.*?```", re.S)
LIST_ITEM = re.compile(r"^\d+[.)]\s")


@dataclass
class BriefCheck:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class BriefScore:
    checks: list[BriefCheck] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(check.passed for check in self.checks)

    def signature(self) -> tuple[str, ...]:
        return tuple(sorted(c.name for c in self.checks if not c.passed))

    def report(self) -> str:
        return "\n".join(
            f"{'PASS' if c.passed else 'FAIL'}  {c.name:<14} {c.detail}" for c in self.checks
        )


def strip_em_dashes(text: str) -> str:
    """Replace em dashes deterministically. Code spans are left alone.

    A comma-heavy sentence takes a colon, a light one takes a semicolon. The
    rule matters less than the fact that it is a rule and not a negotiation.
    """
    spans: list[str] = []

    def stash(match: re.Match) -> str:
        spans.append(match.group(0))
        return f"\x00{len(spans) - 1}\x00"

    masked = CODE_SPAN.sub(stash, text)

    out_lines = []
    for raw_line in masked.split("\n"):
        line = raw_line
        while EM_DASH.search(line):
            replacement = ": " if line.count(",") >= 2 else "; "
            line = EM_DASH.sub(replacement, line, count=1)
        out_lines.append(line)
    masked = "\n".join(out_lines)
    masked = EN_DASH.sub("-", masked)

    for index, span in enumerate(spans):
        masked = masked.replace(f"\x00{index}\x00", span)
    return masked


def ungrounded_citations(body: str, sources: list[str]) -> list[str]:
    """Citation markers that point at a source which was never retrieved."""
    available = set(range(1, len(sources) + 1))
    used = {int(marker) for marker in CITATION.findall(body)}
    return [f"[{n}]" for n in sorted(used - available)]


def uncited_claims(body: str) -> list[str]:
    """Body paragraphs that assert something and cite nothing.

    Crude on purpose: a paragraph with no citation marker is a claim with no
    source. The check is cheap, it never argues, and it catches the failure that
    matters, which is a confident sentence nobody can trace.
    """
    loose = []
    for block in body.split("\n\n"):
        text = block.strip()
        if not text or text.startswith(("#", "-", "*", ">", "|", "```")):
            continue
        # A numbered list is the source list itself, or a set of steps. Neither
        # is a claim, and demanding a citation on the bibliography is silly.
        if LIST_ITEM.match(text):
            continue
        if not CITATION.search(text):
            loose.append(text.splitlines()[0][:80])
    return loose


def check(body: str, sources: list[str]) -> BriefScore:
    """Score a brief. No model call."""
    checks: list[BriefCheck] = []

    checks.append(BriefCheck("has_sources", bool(sources), f"{len(sources)} sources retrieved"))

    ungrounded = ungrounded_citations(body, sources)
    checks.append(
        BriefCheck(
            "grounded",
            not ungrounded,
            "every citation resolves" if not ungrounded else f"dangling: {ungrounded}",
        )
    )

    loose = uncited_claims(body)
    checks.append(
        BriefCheck(
            "cited",
            not loose,
            "every paragraph cites a source" if not loose else f"uncited: {loose[:2]}",
        )
    )

    dashes = len(EM_DASH.findall(CODE_SPAN.sub("", body)))
    checks.append(BriefCheck("style", dashes == 0, f"{dashes} em dashes"))

    return BriefScore(checks=checks)
