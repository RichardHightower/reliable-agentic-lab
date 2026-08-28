"""One research boundary, three backends.

    perplexity   the MCP server, when the attendee has a key
    websearch    the coding agent's built-in tool, when they do not
    fixture      a recorded answer, when there is no network

The attendee decides. The loop does not know which one it holds, which is the
same tool-contract idea as MCP and as the repo contract: name the boundary,
keep the caller ignorant of what is behind it.

Every call goes through a budget with a hard cap, ported from
`v3/article_pipeline/util/cost.py`. An agent that can search without a ceiling
is an agent that can spend without a ceiling.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path


class BudgetExceeded(RuntimeError):
    """The hard cap. Not a warning, not a nudge."""


@dataclass
class Budget:
    """A ceiling on spend and on calls.

    The soft target warns. The hard cap raises. A budget that only warns is a
    budget that gets ignored at three in the morning.
    """

    max_usd: float = 1.0
    max_calls: int = 8
    soft_usd: float | None = None
    spent_usd: float = 0.0
    calls: int = 0

    def charge(self, usd: float) -> None:
        if self.calls + 1 > self.max_calls:
            raise BudgetExceeded(f"call budget spent: {self.max_calls} calls")
        if self.spent_usd + usd > self.max_usd:
            raise BudgetExceeded(
                f"money budget spent: ${self.spent_usd:.2f} + ${usd:.2f} > ${self.max_usd:.2f}"
            )
        self.calls += 1
        self.spent_usd += usd

    @property
    def over_soft_target(self) -> bool:
        return self.soft_usd is not None and self.spent_usd > self.soft_usd

    def line(self) -> str:
        soft = f" (soft ${self.soft_usd:.2f})" if self.soft_usd else ""
        return f"${self.spent_usd:.2f} / ${self.max_usd:.2f}{soft}, {self.calls}/{self.max_calls} calls"


@dataclass
class Finding:
    question: str
    answer: str
    citations: list[str] = field(default_factory=list)
    backend: str = ""
    usd: float = 0.0
    note: str = ""

    @property
    def empty(self) -> bool:
        return not self.answer.strip()

    def to_dict(self) -> dict:
        return {
            "question": self.question,
            "answer": self.answer,
            "citations": self.citations,
            "backend": self.backend,
            "usd": self.usd,
            "note": self.note,
        }


class Backend:
    name = "backend"
    cost_per_call = 0.0

    def available(self) -> bool:
        return True

    def search(self, question: str) -> Finding:
        raise NotImplementedError


class FixtureBackend(Backend):
    """Recorded answers. Runs offline, in a room with no network."""

    name = "fixture"

    def __init__(self, path: Path | str):
        self.path = Path(path)

    def available(self) -> bool:
        return self.path.exists()

    def search(self, question: str) -> Finding:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        best = data.get(question)
        if best is None:
            # Fall back to the closest recorded question by word overlap.
            words = set(question.lower().split())
            best = max(
                data.values(),
                key=lambda entry: len(words & set(str(entry.get("question", "")).lower().split())),
                default=None,
            )
        if best is None:
            return Finding(question, "no recorded answer", backend=self.name)
        return Finding(
            question=question,
            answer=best.get("answer", ""),
            citations=list(best.get("citations", [])),
            backend=self.name,
        )


class WebSearchBackend(Backend):
    """The coding agent's own search tool.

    The loop cannot call the agent's tool directly, so it writes the question
    into a request file the agent answers. Crude on purpose: it keeps the
    boundary visible instead of hiding it inside a client library.
    """

    name = "websearch"
    cost_per_call = 0.0

    def __init__(self, inbox: Path | str):
        self.inbox = Path(inbox)

    def available(self) -> bool:
        return self.inbox.parent.exists()

    def search(self, question: str) -> Finding:
        answers = {}
        if self.inbox.exists():
            answers = json.loads(self.inbox.read_text(encoding="utf-8"))
        entry = answers.get(question)
        if entry is None:
            return Finding(
                question=question,
                answer="",
                backend=self.name,
            )
        return Finding(
            question=question,
            answer=entry.get("answer", ""),
            citations=list(entry.get("citations", [])),
            backend=self.name,
        )


class PerplexityBackend(Backend):
    """Perplexity, through whichever transport this laptop can reach.

    The previous version piped a JSON blob into `npx -y server-perplexity-ask`
    and read stdout. An MCP server does not work that way. It speaks JSON-RPC
    over stdio and expects an `initialize` handshake before any `tools/call`, so
    that version could only ever return an empty finding. `mcp_tools` does the
    handshake, and falls back to the vendor's REST endpoint when it cannot.
    """

    name = "perplexity"
    cost_per_call = 0.006

    def __init__(self, config: dict | None = None):
        self.config = config
        self.transport = ""

    def available(self) -> bool:
        return bool(os.environ.get("PERPLEXITY_API_KEY"))

    def search(self, question: str) -> Finding:
        from mcp_tools import TransportUnavailable, ask_perplexity  # noqa: PLC0415

        try:
            answer = ask_perplexity(question, self.config)
        except TransportUnavailable as exc:
            # An empty finding, not a raise. The loop counts empty answers and
            # escalates on no source, which is the honest outcome here.
            return Finding(question, "", backend=self.name, note=str(exc))
        self.transport = answer.transport
        return Finding(
            question=question,
            answer=answer.text,
            citations=answer.citations,
            backend=self.name,
            usd=answer.usd,
        )


class Context7Backend(Backend):
    """Library, API, and version facts, from the vendor's own documentation.

    Separate from Perplexity on purpose. Verification needs a source that is
    independent of the one that produced the claim, and a second Perplexity
    query is not independent: it is the same index, ranked slightly differently.
    Context7 reads the library's published docs.

    The question arrives as "library :: query". A question with no library is
    not something this backend can answer, and it says so rather than guessing.
    """

    name = "context7"
    cost_per_call = 0.0

    def __init__(self, config: dict | None = None):
        self.config = config
        self.transport = ""

    def available(self) -> bool:
        from mcp_tools import ctx7_available  # noqa: PLC0415

        return ctx7_available() or bool(self.config)

    def search(self, question: str) -> Finding:
        from mcp_tools import TransportUnavailable, ask_context7  # noqa: PLC0415

        library, _, query = question.partition("::")
        if not query.strip():
            return Finding(
                question,
                "",
                backend=self.name,
                note="context7 needs 'library :: question'",
            )
        try:
            answer = ask_context7(library.strip(), query.strip(), self.config)
        except TransportUnavailable as exc:
            return Finding(question, "", backend=self.name, note=str(exc))
        self.transport = answer.transport
        return Finding(
            question=question,
            answer=answer.text,
            citations=answer.citations,
            backend=self.name,
        )


def choose(*, fixture: Path | str | None = None, inbox: Path | str | None = None) -> Backend:
    """Pick the best backend available. The attendee's environment decides.

    Order matters: a real search beats a recorded one, and a recorded one beats
    nothing. Nothing is never an option, because a research loop that silently
    returns no evidence is worse than one that refuses.
    """
    candidates: list[Backend] = [PerplexityBackend()]
    if inbox:
        candidates.append(WebSearchBackend(inbox))
    if fixture:
        candidates.append(FixtureBackend(fixture))
    for backend in candidates:
        if backend.available():
            return backend
    raise RuntimeError(
        "no research backend is available. Set PERPLEXITY_API_KEY, provide a "
        "websearch inbox, or point at a fixture file."
    )


@dataclass
class Researcher:
    """A budgeted client over whichever backend is available."""

    backend: Backend
    budget: Budget = field(default_factory=Budget)
    findings: list[Finding] = field(default_factory=list)

    def ask(self, question: str) -> Finding:
        self.budget.charge(self.backend.cost_per_call)
        finding = self.backend.search(question)
        finding.backend = self.backend.name
        self.findings.append(finding)
        return finding

    def report(self) -> str:
        lines = [f"backend: {self.backend.name}", f"budget: {self.budget.line()}", ""]
        for finding in self.findings:
            lines.append(f"Q: {finding.question}")
            lines.append(f"A: {finding.answer[:300]}")
            for citation in finding.citations:
                lines.append(f"   - {citation}")
            lines.append("")
        return "\n".join(lines)
