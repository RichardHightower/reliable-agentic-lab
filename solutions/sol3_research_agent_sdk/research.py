"""One filtered research boundary, three backends.

    perplexity   the Search API, then fast Agent API only when quotes are absent
    anthropic    the researcher subagent's WebSearch fallback
    fixture      a recorded answer, when there is no network

The caller does not know which one answered. That is the same tool-contract
idea as MCP itself: name the boundary, keep the caller ignorant of what is
behind it.

The source policy is Python-owned.  Perplexity receives the allowlist, and the
same list post-filters every backend's sources and claims.  A provider filter
is a net; post-filtering is the wall.

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

import source_policy

PERPLEXITY_SEARCH_URL = "https://api.perplexity.ai/search"
PERPLEXITY_ASK_URL = "https://api.perplexity.ai/v1/agent"
PERPLEXITY_ASK_PRESET = "fast-search"
FALLBACK_CHAIN = ("perplexity", "anthropic", "fixture")


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
    charges_provider_calls = False

    def available(self) -> bool:
        return True

    def search(self, question: str, *, charge=None) -> Finding:
        raise NotImplementedError


class FixtureBackend(Backend):
    """Recorded answers. Runs offline, in a room with no network."""

    name = "fixture"

    def __init__(self, path: Path | str):
        self.path = Path(path)

    def available(self) -> bool:
        return self.path.exists()

    def search(self, question: str, *, charge=None) -> Finding:
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
        sources = source_policy.filter_sources(best.get("sources", []))
        if not sources:
            sources = source_policy.filter_sources(
                [{"url": url, "title": ""} for url in best.get("citations", [])]
            )
        return Finding(
            question=question,
            answer=best.get("answer", ""),
            citations=[source["url"] for source in sources],
            sources=sources,
            backend=self.name,
        )


class PerplexityBackend(Backend):
    """Perplexity Search with a bounded, filtered no-quote fallback.

    The researcher subagent reaches the same provider through the official MCP
    server.  This direct lane is for the no-model runtime, so it calls the
    documented HTTP APIs without adding a second Python dependency.
    """

    name = "perplexity"
    # An estimate for the budget, not a bill.  It is charged before each
    # provider call so scout, retrieve, and the rare no-quote fallback remain
    # visible to the ceiling.
    cost_per_call = 0.006
    charges_provider_calls = True

    def __init__(self, timeout: int = 120):
        self.timeout = timeout

    def available(self) -> bool:
        return bool(os.environ.get("PERPLEXITY_API_KEY"))

    def _post(self, url: str, payload: dict, *, charge=None) -> dict | None:
        """Charge before a provider request and return JSON or a safe empty result."""
        if charge is not None:
            charge(self.cost_per_call)
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            headers={
                "Authorization": f"Bearer {os.environ['PERPLEXITY_API_KEY']}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            return None

    @staticmethod
    def search_body(question: str, domains: tuple[str, ...]) -> dict:
        return {
            "query": question,
            "max_results": 10,
            "max_tokens_per_page": 1200,
            "search_domain_filter": list(domains),
        }

    @staticmethod
    def ask_body(question: str, domains: tuple[str, ...]) -> dict:
        return {
            "preset": PERPLEXITY_ASK_PRESET,
            "input": question,
            "instructions": (
                "Answer only from the supplied official-domain allowlist. "
                "Quote the source text used for every substantive claim. "
                "Say what the sources do not establish."
            ),
            "tools": [
                {
                    "type": "web_search",
                    "filters": {"search_domain_filter": list(domains)},
                }
            ],
        }

    def _search(self, question: str, domains: tuple[str, ...], *, charge=None) -> Finding:
        payload = self._post(
            PERPLEXITY_SEARCH_URL,
            self.search_body(question, domains),
            charge=charge,
        )
        return _finding_from_search(question, payload or {}, self.name, self.cost_per_call, domains)

    def _ask(self, question: str, domains: tuple[str, ...], *, charge=None) -> Finding:
        payload = self._post(
            PERPLEXITY_ASK_URL,
            self.ask_body(question, domains),
            charge=charge,
        )
        return _finding_from_ask(question, payload or {}, self.name, self.cost_per_call, domains)

    def search(self, question: str, *, charge=None) -> Finding:
        # Pass one is a narrow scout.  It may add only an official docs host to
        # the working filter; medium.com, DeepWiki, and personal blogs cannot
        # grow the allowlist merely because a provider returned them.
        scout = self._search(
            f"Which official documentation domains cover this question? {question}",
            tuple(source_policy.SEED_ALLOWLIST),
            charge=charge,
        )
        domains = source_policy.merge_scout_domains(
            [source["url"] for source in scout.sources]
        )

        retrieved = self._search(question, domains, charge=charge)
        retrieved.usd += scout.usd
        # Search results normally carry excerpts.  Only an otherwise useful
        # result set without one earns the single fast-answer fallback.
        if retrieved.citations and not _has_usable_quote(retrieved):
            fallback = self._ask(question, domains, charge=charge)
            fallback.usd += retrieved.usd
            if fallback.citations:
                return fallback
        return retrieved


class AnthropicBackend(Backend):
    """The injected Agent SDK researcher, used after Perplexity is unavailable.

    The loop cannot call an MCP tool directly. It spawns the researcher, which
    can, and reads the JSON that comes back. `ask` is injected by the driver so
    this module never imports the SDK, and so the tests can drive the whole
    phase with a plain function.
    """

    name = "anthropic"
    cost_per_call = 0.0

    def __init__(self, ask):
        self.ask = ask

    def available(self) -> bool:
        return self.ask is not None

    def search(self, question: str, *, charge=None) -> Finding:
        finding = self.ask(question)
        finding.backend = self.name
        return _filter_finding(finding)


# The earlier name appears in workshop notes and third-party attendee tests.
# Keep it as an alias while the visible fallback name is the provider it uses.
AgentBackend = AnthropicBackend


def _has_usable_quote(finding: Finding) -> bool:
    return bool(finding.answer.strip())


def _filter_finding(finding: Finding, domains=source_policy.SEED_ALLOWLIST) -> Finding:
    """Apply the source wall after every backend, not only Perplexity."""
    sources = source_policy.filter_sources(finding.sources, allowed_domains=domains)
    finding.sources = sources
    finding.citations = [source["url"] for source in sources]
    return finding


def _finding_from_search(
    question: str,
    payload: dict,
    backend: str,
    usd: float,
    domains: tuple[str, ...] = source_policy.SEED_ALLOWLIST,
) -> Finding:
    """Turn ranked Search API hits into sources and quote-bearing research text."""
    raw_sources = []
    snippets = []
    for result in payload.get("results") or []:
        url = result.get("url")
        if not url:
            continue
        snippet = str(result.get("snippet", "")).strip()
        raw_sources.append({"url": url, "title": result.get("title", "")})
        if snippet:
            snippets.append(snippet)
    finding = Finding(
        question=question,
        answer="\n\n".join(snippets),
        sources=raw_sources,
        backend=backend,
        usd=usd,
    )
    return _filter_finding(finding, domains)


def _finding_from_ask(
    question: str,
    payload: dict,
    backend: str,
    usd: float,
    domains: tuple[str, ...] = source_policy.SEED_ALLOWLIST,
) -> Finding:
    """Read the Agent API response shape, retaining only allowed citations."""
    answer = str(payload.get("output_text", "")).strip()
    if not answer:
        choices = payload.get("choices") or []
        if choices:
            answer = str((choices[0].get("message") or {}).get("content", "")).strip()
    raw_sources = []
    for result in payload.get("search_results") or payload.get("results") or []:
        if result.get("url"):
            raw_sources.append({"url": result["url"], "title": result.get("title", "")})
    for url in payload.get("citations") or []:
        raw_sources.append({"url": url, "title": ""})
    finding = Finding(question=question, answer=answer, sources=raw_sources, backend=backend, usd=usd)
    return _filter_finding(finding, domains)


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

    return _filter_finding(Finding(
        question=question,
        answer=answer.strip(),
        citations=[source["url"] for source in sources],
        sources=sources,
        backend=backend,
        usd=usd,
    ))


def choose(*, fixture: Path | str | None = None, ask=None) -> Backend:
    """Pick the best backend available. The environment decides.

    Order matters: the filtered Perplexity Search API is first, the Agent SDK's
    Anthropic WebSearch fallback is second, and the recorded fixture is last.
    This port deliberately has no OpenAI or Bing fallback.
    """
    candidates: list[Backend] = []
    candidates.append(PerplexityBackend())
    if ask is not None:
        candidates.append(AnthropicBackend(ask))
    if fixture:
        candidates.append(FixtureBackend(fixture))
    for backend in candidates:
        if backend.available():
            return backend
    raise RuntimeError(
        "no research backend is available. Set PERPLEXITY_API_KEY, pass an "
        "Anthropic Agent SDK callable, or point at a fixture file."
    )


@dataclass
class Researcher:
    """A budgeted client over whichever backend is available."""

    backend: Backend
    budget: Budget = field(default_factory=Budget)
    findings: list[Finding] = field(default_factory=list)

    def ask(self, question: str) -> Finding:
        if self.backend.charges_provider_calls:
            finding = self.backend.search(question, charge=self.budget.charge)
        else:
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
