"""One research boundary, three backends.

    agent        the researcher subagent, which holds the MCP tools
    perplexity   the Sonar HTTP API, called straight from Python
    fixture      a recorded answer, when there is no network

The caller does not know which one answered. That is the same tool-contract
idea as MCP itself: name the boundary, keep the caller ignorant of what is
behind it.

Two backends exist for one reason, and it is not redundancy. Phase 2 researches
a question through the agent, which reaches Perplexity and Context7 over MCP.
Phase 3 verifies the resulting claim through a different backend that never saw
the agent's answer. A second opinion from the same context is not a second
opinion.

Every call goes through a budget with a hard cap, ported from
`v3/article_pipeline/util/cost.py`. An agent that can search without a ceiling
is an agent that can spend without a ceiling.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"

# Keep the model named here so swapping it is one edit. `sonar-pro` searches the
# open web. `sonar-deep-research` is far slower and far more expensive, and a
# per-claim verification does not need it.
PERPLEXITY_MODEL = "sonar-pro"


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
        return (
            f"${self.spent_usd:.2f} / ${self.max_usd:.2f}{soft}, "
            f"{self.calls}/{self.max_calls} calls"
        )


@dataclass
class Finding:
    """One answer, and the sources it came from.

    `citations` is the flat URL list the grounding check counts. `sources`
    carries the title alongside the URL, which is what the RKC SourceDocument
    needs and what a reference list prints.
    """

    question: str
    answer: str
    citations: list[str] = field(default_factory=list)
    sources: list[dict] = field(default_factory=list)
    backend: str = ""
    usd: float = 0.0

    def to_dict(self) -> dict:
        return {
            "question": self.question,
            "answer": self.answer,
            "citations": self.citations,
            "sources": self.sources,
            "backend": self.backend,
            "usd": self.usd,
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
        # A key starting with an underscore is a note to the reader, not a
        # recorded answer. Skipping non-dict values keeps a comment in the
        # fixture from crashing the nearest-question fallback.
        entries = [
            value
            for key, value in data.items()
            if isinstance(value, dict) and not key.startswith("_")
        ]
        best = data.get(question)
        if not isinstance(best, dict):
            # Fall back to the closest recording by word overlap, over the
            # question and the answer together. The verify phase searches with
            # a claim, which is a sentence lifted out of an answer and shares
            # almost no words with the question that produced it.
            words = set(question.lower().split())

            def overlap(entry: dict) -> int:
                text = f"{entry.get('question', '')} {entry.get('answer', '')}".lower()
                return len(words & set(text.split()))

            best = max(entries, key=overlap, default=None)
        if best is None:
            return Finding(question, "no recorded answer", backend=self.name)
        citations = list(best.get("citations", []))
        return Finding(
            question=question,
            answer=best.get("answer", ""),
            citations=citations,
            sources=list(best.get("sources", [{"url": url, "title": ""} for url in citations])),
            backend=self.name,
        )


class PerplexityBackend(Backend):
    """Perplexity Sonar, over plain HTTP.

    The MCP server is the agent's path to Perplexity, not Python's. An MCP
    stdio server speaks framed JSON-RPC, so piping a message blob at
    `server-perplexity-ask` and reading stdout returns nothing usable. This
    calls the documented REST endpoint instead, with no client library, so the
    folder stays installable with the Agent SDK and nothing else.
    """

    name = "perplexity"
    # An estimate for the budget, not a bill. It exists so the ceiling is real
    # before the invoice is.
    cost_per_call = 0.006

    def __init__(self, model: str = PERPLEXITY_MODEL, timeout: int = 120):
        self.model = model
        self.timeout = timeout

    def available(self) -> bool:
        return bool(os.environ.get("PERPLEXITY_API_KEY"))

    def search(self, question: str) -> Finding:
        body = json.dumps(
            {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a technical research assistant. Answer from primary "
                            "sources: official documentation, specifications, papers, and "
                            "vendor repositories. State what you could not confirm. Never "
                            "invent a citation."
                        ),
                    },
                    {"role": "user", "content": question},
                ],
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            PERPLEXITY_URL,
            data=body,
            headers={
                "Authorization": f"Bearer {os.environ['PERPLEXITY_API_KEY']}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            # An empty answer with no citations. The caller's grounding check
            # fails it, which is the right outcome. Returning a confident
            # sentence with no source is the wrong one.
            return Finding(question, "", backend=self.name, usd=0.0)
        return _finding_from_sonar(question, payload, self.name, self.cost_per_call)


class AgentBackend(Backend):
    """The researcher subagent, which holds the Perplexity and Context7 MCP tools.

    The loop cannot call an MCP tool directly. It spawns the researcher, which
    can, and reads the JSON that comes back. `ask` is injected by the driver so
    this module never imports the SDK, and so the tests can drive the whole
    phase with a plain function.
    """

    name = "agent"
    cost_per_call = 0.0

    def __init__(self, ask):
        self.ask = ask

    def available(self) -> bool:
        return self.ask is not None

    def search(self, question: str) -> Finding:
        finding = self.ask(question)
        finding.backend = self.name
        return finding


def _finding_from_sonar(question: str, payload: dict, backend: str, usd: float) -> Finding:
    """Read one Sonar response.

    `citations` is a flat list of URLs. `search_results` carries the title too,
    and is the better source when it is present. Handle both, because a
    response that drops one of them should not lose every citation.
    """
    choices = payload.get("choices") or []
    answer = ""
    if choices:
        answer = (choices[0].get("message") or {}).get("content", "") or ""

    sources: list[dict] = []
    for result in payload.get("search_results") or []:
        url = result.get("url")
        if url:
            sources.append({"url": url, "title": result.get("title", "")})
    seen = {source["url"] for source in sources}
    for url in payload.get("citations") or []:
        if url not in seen:
            sources.append({"url": url, "title": ""})
            seen.add(url)

    return Finding(
        question=question,
        answer=answer.strip(),
        citations=[source["url"] for source in sources],
        sources=sources,
        backend=backend,
        usd=usd,
    )


def choose(*, fixture: Path | str | None = None, ask=None) -> Backend:
    """Pick the best backend available. The environment decides.

    Order matters: the agent reaches both MCP servers, direct Perplexity reaches
    one, and a recorded answer reaches none. Nothing is never an option, because
    a research loop that silently returns no evidence is worse than one that
    refuses.
    """
    candidates: list[Backend] = []
    if ask is not None:
        candidates.append(AgentBackend(ask))
    candidates.append(PerplexityBackend())
    if fixture:
        candidates.append(FixtureBackend(fixture))
    for backend in candidates:
        if backend.available():
            return backend
    raise RuntimeError(
        "no research backend is available. Set PERPLEXITY_API_KEY, pass an "
        "agent callable, or point at a fixture file."
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
