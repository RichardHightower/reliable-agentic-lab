"""One filtered research boundary, with provider fallbacks.

    perplexity   Search API through the MCP server or vendor REST endpoint
    anthropic    one domain-filtered web-search request
    openai       one domain-filtered web-search request
    fixture      a recorded answer, when no live provider is available

The attendee decides. The loop does not know which one it holds, which is the
same tool-contract idea as MCP and as the repo contract: name the boundary,
keep the caller ignorant of what is behind it. The only exception is the
explicit `WebSearchBackend`, retained for the Saturday-style classroom demo
when the caller asks for `--backend websearch`; paper auto mode never chooses
it.

Every call goes through a budget with a hard cap, ported from
`v3/article_pipeline/util/cost.py`. An agent that can search without a ceiling
is an agent that can spend without a ceiling.
"""

from __future__ import annotations

import json
import os
import re
from base64 import urlsafe_b64decode
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from threading import Lock
from typing import Callable
from urllib.parse import parse_qs, urlencode, urljoin, urlparse
from urllib.request import Request, urlopen

import source_policy


HERE = Path(__file__).resolve().parent
ENV_LINE = re.compile(r"(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)")


def dotenv_paths(anchor: Path = HERE) -> tuple[Path, ...]:
    """The four explicit, portable locations this standalone lab honors.

    A workshop attendee may run from the solution folder, a `solutions/`
    directory, or a checkout nested in a larger workspace.  Checking these
    paths means a live run sees its own key without reading an editor profile,
    a home-directory credential store, or an unrelated parent directory.
    """
    root = Path(anchor).resolve()
    return tuple(root.parents[level] / ".env" if level else root / ".env" for level in range(4))


def load_dotenv(paths: tuple[Path, ...] | None = None) -> None:
    """Load non-empty `.env` values, nearest file first, without clobbering env.

    Shell-exported values remain authoritative.  Among files, the nearest
    non-empty value wins, so a solution-specific key can intentionally differ
    from one at the repository or workshop root.  This deliberately small
    reader supports the conventional `KEY=value` and `export KEY=value` forms
    required by this lab; it is not a general shell parser.
    """
    for path in paths or dotenv_paths():
        if not path.is_file():
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            match = ENV_LINE.fullmatch(raw.strip())
            if match is None:
                continue
            key, value = match.groups()
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                value = value[1:-1]
            if value and not os.environ.get(key):
                os.environ[key] = value


# `task` loads dotenv files too, but direct `python loop.py` is a supported
# workshop entry point.  Load before checking availability so both paths choose
# the same Perplexity backend.
load_dotenv()


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
    on_charge: Callable[[float], None] | None = field(default=None, repr=False, compare=False)
    _request_limit: int | None = field(default=None, init=False, repr=False, compare=False)
    _request_calls: int = field(default=0, init=False, repr=False, compare=False)
    _tool_limit: int | None = field(default=None, init=False, repr=False, compare=False)
    _tool_calls: int = field(default=0, init=False, repr=False, compare=False)
    _lock: Lock = field(default_factory=Lock, init=False, repr=False, compare=False)

    def begin_request(
        self, max_calls: int | None = None, *, max_provider_calls: int | None = None
    ) -> None:
        """Start one agent request with tool and provider-call ceilings.

        The research role gets one tool invocation. That one invocation may make
        Scout, Retrieve, and the narrow Ask repair, so provider charges have a
        separate cap and cannot be mistaken for extra model-issued searches.
        """
        with self._lock:
            self._request_limit = max_provider_calls if max_provider_calls is not None else max_calls
            self._request_calls = 0
            self._tool_limit = max_calls
            self._tool_calls = 0

    def end_request(self) -> None:
        with self._lock:
            self._request_limit = None
            self._request_calls = 0
            self._tool_limit = None
            self._tool_calls = 0

    def reserve_tool(self) -> None:
        """Spend one role-visible tool invocation before it reaches a backend."""
        with self._lock:
            if self._tool_limit is not None and self._tool_calls + 1 > self._tool_limit:
                raise BudgetExceeded(f"request search budget spent: {self._tool_limit} tool call")
            self._tool_calls += 1

    def charge(self, usd: float) -> None:
        """Reserve a provider call before issuing it.

        The callback persists the reservation before a live tool call begins.
        A crash can therefore over-count a call, but can never spend an
        unrecorded call and resume past the cap.
        """
        with self._lock:
            if self._request_limit is not None and self._request_calls + 1 > self._request_limit:
                raise BudgetExceeded(f"request search budget spent: {self._request_limit} call")
            if self.calls + 1 > self.max_calls:
                raise BudgetExceeded(f"call budget spent: {self.max_calls} calls")
            if self.spent_usd + usd > self.max_usd:
                raise BudgetExceeded(
                    f"money budget spent: ${self.spent_usd:.2f} + ${usd:.2f} > ${self.max_usd:.2f}"
                )
            self.calls += 1
            self._request_calls += 1
            self.spent_usd += usd
            if self.on_charge is not None:
                self.on_charge(usd)

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
    provider_unavailable: bool = False

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


EXIT_DOCTRINE_QUESTION = "What three exits does this repo's paper loop check, and in what order?"
REPOSITORY_PAPER_URL = (
    "https://github.com/RichardHightower/reliable-agentic-lab/blob/main/"
    "solutions/sol3_research_deep_agents/paper.py"
)


def repository_doctrine_finding(question: str) -> Finding | None:
    """Return the local first-party source for the one repository question.

    Perplexity Search does not index this repository's ``paper.py``. Broadening
    the query only returned generic vendor loop docs, which cannot establish
    what *this* implementation checks. The commissioning plan permits this
    repository as a primary source, so read the exact checked-in function and
    expose it through the same one-call research boundary.

    This is deliberately exact-question-only. It must never turn into a local
    corpus search that bypasses the provider allowlist for ordinary questions.
    """
    normalized = " ".join(question.lower().split())
    doctrine_markers = ("three exits", "repo", "paper loop", "order")
    if question.strip() != EXIT_DOCTRINE_QUESTION and not all(
        marker in normalized for marker in doctrine_markers
    ):
        return None
    source = (HERE / "paper.py").read_text(encoding="utf-8")
    start = source.find("def check_stop(")
    end = source.find("\n\n@dataclass", start)
    if start < 0 or end < 0:
        return Finding(
            question,
            "",
            backend="repository",
            note="paper.py does not contain the check_stop implementation",
        )
    function = source[start:end]
    markers = ("if done:", "if spent_usd >= max_usd:", "if exhausted:")
    positions = tuple(function.find(marker) for marker in markers)
    if any(position < 0 for position in positions) or positions != tuple(sorted(positions)):
        return Finding(
            question,
            "",
            backend="repository",
            note="paper.py does not check done, cost, and max turns in the required order",
        )
    excerpt = "\n".join(
        line.strip()
        for line in function.splitlines()
        if line.strip().startswith(("if done:", "if spent_usd", "if exhausted:"))
        or '"reason":' in line
    )
    return Finding(
        question=question,
        answer=(
            "The repository's check_stop function tests completion first, then the "
            "cost ceiling, then exhausted turns. Exact source excerpt:\n" + excerpt
        ),
        citations=[REPOSITORY_PAPER_URL],
        backend="repository",
        note="local first-party repository source",
    )


def repository_doctrine_report(question: str) -> dict | None:
    """Structured evidence for the live paper's deterministic local question.

    The open-ended researcher still owns every web question. This report keeps
    the exact local implementation check out of model query rewriting: Python
    verifies the function order, supplies the fixed repository URL, and emits
    the same shape the evidence ledger accepts from the researcher.
    """
    finding = repository_doctrine_finding(question)
    if finding is None or finding.empty or not finding.citations:
        return None
    excerpt = finding.answer.partition("Exact source excerpt:\n")[2].strip()
    url = finding.citations[0]
    return {
        "answer": finding.answer,
        "sources": [
            {
                "title": "Sol3 Deep Agents paper-loop implementation",
                "url": url,
                "vendor": "reliable-agentic-lab",
                "quote": excerpt,
            }
        ],
        "claims": [
            {
                "text": "The paper loop checks done first, cost second, and max turns third.",
                "confidence": 1.0,
                "source_urls": [url],
            }
        ],
    }


class Backend:
    name = "backend"
    cost_per_call = 0.0

    @property
    def active_name(self) -> str:
        """The provider that satisfied the latest search request."""
        return self.name

    @property
    def active_transport(self) -> str:
        """The concrete MCP or REST path, when the provider exposes one."""
        return str(getattr(self, "transport", "") or "")

    def available(self) -> bool:
        return True

    def search(self, question: str, reserve: Callable[[float], None] | None = None) -> Finding:
        raise NotImplementedError


class FixtureBackend(Backend):
    """Recorded answers. Runs offline, in a room with no network."""

    name = "fixture"

    def __init__(self, path: Path | str):
        self.path = Path(path)

    def available(self) -> bool:
        return self.path.exists()

    def search(self, question: str, reserve: Callable[[float], None] | None = None) -> Finding:
        if reserve is not None:
            reserve(self.cost_per_call)
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


class _BingResults(HTMLParser):
    """The small, deliberately lossy slice of a Bing result page."""

    def __init__(self) -> None:
        super().__init__()
        self._current: dict | None = None
        self._capture: str | None = None
        self._items: list[dict] = []
        self._in_heading = False

    def _finish_current(self) -> None:
        if not self._current:
            return
        title = " ".join(self._current["title"]).strip()
        href = self._current["href"]
        if title and href:
            self._items.append(
                {
                    "title": re.sub(r"\s+", " ", title),
                    "url": _result_url(href),
                    "snippet": re.sub(r"\s+", " ", " ".join(self._current["snippet"])).strip(),
                }
            )
        self._current = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        classes = values.get("class") or ""
        if tag == "li" and "b_algo" in classes:
            self._finish_current()
            self._current = {"title": [], "href": "", "snippet": []}
            self._in_heading = False
        elif self._current is not None and tag == "h2":
            self._in_heading = True
        elif self._current is not None and tag == "a" and self._in_heading:
            self._current["href"] = values.get("href") or ""
            self._capture = "title"
        elif self._current is not None and tag == "p":
            self._capture = "snippet"

    def handle_endtag(self, tag: str) -> None:
        if tag == "a":
            self._capture = None
        elif tag == "h2":
            self._in_heading = False
        elif tag == "p":
            self._capture = None
        elif tag == "li":
            self._finish_current()

    def handle_data(self, data: str) -> None:
        if self._current is not None and self._capture is not None:
            self._current[self._capture].append(data)

    def results(self) -> list[dict]:
        self._finish_current()
        return self._items


def _result_url(href: str) -> str:
    """Return a result's source URL, unwrapping Bing's tracked redirect."""
    expanded = urljoin("https://www.bing.com/", href)
    parsed = urlparse(expanded)
    if parsed.netloc.endswith("bing.com") and parsed.path.startswith("/ck/"):
        encoded = parse_qs(parsed.query).get("u", [""])[0]
        if encoded.startswith("a1"):
            encoded = encoded[2:]
        try:
            padding = "=" * (-len(encoded) % 4)
            target = urlsafe_b64decode(encoded + padding).decode("utf-8")
        except (UnicodeDecodeError, ValueError):
            target = ""
        if target.startswith(("http://", "https://")):
            return target
    return expanded


class WebSearchBackend(Backend):
    """A no-key web-search fallback, with an optional recorded-answer inbox.

    The inbox keeps the classroom's agent-mediated demo possible, but it is not
    the live fallback. When an answer is not recorded, this backend queries
    Bing's public HTML result page and returns result URLs and snippets to the
    research subagent. The custom search tool remains the single boundary;
    Deep Agents itself supplies no built-in web-search tool.
    """

    name = "websearch"
    cost_per_call = 0.0

    def __init__(self, inbox: Path | str | None = None, *, timeout: float = 20.0):
        self.inbox = Path(inbox) if inbox else None
        self.timeout = timeout

    def available(self) -> bool:
        return True

    def search(self, question: str, reserve: Callable[[float], None] | None = None) -> Finding:
        if reserve is not None:
            reserve(self.cost_per_call)
        answers = {}
        if self.inbox and self.inbox.exists():
            answers = json.loads(self.inbox.read_text(encoding="utf-8"))
        entry = answers.get(question)
        if entry is not None:
            return Finding(
                question=question,
                answer=entry.get("answer", ""),
                citations=list(entry.get("citations", [])),
                backend=self.name,
                note="recorded web-search answer",
            )
        try:
            query = urlencode({"q": question, "kl": "us-en"})
            request = Request(
                f"https://www.bing.com/search?{query}",
                headers={"User-Agent": "Mozilla/5.0 (compatible; reliable-agentic-lab/1.0)"},
            )
            with urlopen(request, timeout=self.timeout) as response:  # noqa: S310 (fixed provider URL)
                html = response.read().decode("utf-8", errors="replace")
        except OSError as exc:
            return Finding(
                question=question,
                answer="",
                backend=self.name,
                note=f"web search unavailable: {exc}",
            )
        parser = _BingResults()
        parser.feed(html)
        results = parser.results()[:8]
        if not results:
            return Finding(
                question=question,
                answer="",
                backend=self.name,
                note="web search returned no results",
            )
        citations = [result["url"] for result in results if result["url"].startswith(("http://", "https://"))]
        lines = [f"Web results for: {question}"]
        for index, result in enumerate(results, start=1):
            detail = f" — {result['snippet']}" if result["snippet"] else ""
            lines.append(f"{index}. {result['title']}{detail}\n   {result['url']}")
        return Finding(
            question=question,
            answer="\n".join(lines),
            citations=list(dict.fromkeys(citations)),
            backend=self.name,
            note="Bing HTML search",
        )


class PerplexityBackend(Backend):
    """Perplexity Scout + Retrieve, with an Ask fallback only for no quotes.

    Search receives the Python-owned filter and returns URLs/snippets. Scout may
    discover another official documentation host, then retrieve queries the
    merged list. Both calls happen inside this one tool invocation, so the
    researcher cannot spend a third model-issued search call.
    """

    name = "perplexity"
    cost_per_call = 0.006

    def __init__(self, config: dict | None = None):
        self.config = config
        self.transport = ""

    def available(self) -> bool:
        return bool(os.environ.get("PERPLEXITY_API_KEY"))

    def _call(self, operation, question, allowlist, reserve):
        if reserve is not None:
            reserve(self.cost_per_call)
        return operation(question, allowlist, self.config)

    def search(self, question: str, reserve: Callable[[float], None] | None = None) -> Finding:
        from mcp_tools import TransportUnavailable, ask_perplexity, search_perplexity  # noqa: PLC0415

        try:
            scout = self._call(search_perplexity, question, source_policy.SEED_ALLOWLIST, reserve)
            allowlist = source_policy.merge_allowlist(scout.citations)
            retrieved = self._call(search_perplexity, question, allowlist, reserve)
        except TransportUnavailable as exc:
            return Finding(
                question,
                "",
                backend=self.name,
                note=str(exc),
                provider_unavailable=True,
            )

        answer = retrieved
        calls = 2
        # Ask is deliberately not a normal second pass. It is only a repair for
        # a real result bundle that did not contain enough source text to quote.
        if retrieved.hits and not retrieved.has_usable_quotes:
            try:
                answer = self._call(ask_perplexity, question, allowlist, reserve)
                calls += 1
            except TransportUnavailable as exc:
                return Finding(question, "", backend=self.name, note=str(exc), provider_unavailable=True)

        citations = source_policy.filter_urls(answer.citations, allowlist)
        if not citations:
            return Finding(
                question,
                "",
                backend=self.name,
                usd=calls * self.cost_per_call,
                note="search returned no citations on the approved allowlist",
            )
        self.transport = answer.transport
        return Finding(
            question=question,
            answer=answer.text,
            citations=citations,
            backend=self.name,
            usd=calls * self.cost_per_call,
            note=f"{calls} filtered Perplexity requests",
        )


class AnthropicBackend(Backend):
    """One official-domain Anthropic web search when Perplexity is unavailable."""

    name = "anthropic"
    cost_per_call = 0.02

    def available(self) -> bool:
        return bool(os.environ.get("ANTHROPIC_API_KEY"))

    def search(self, question: str, reserve: Callable[[float], None] | None = None) -> Finding:
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            return Finding(question, "", backend=self.name, note="ANTHROPIC_API_KEY is not set", provider_unavailable=True)
        if reserve is not None:
            reserve(self.cost_per_call)
        try:
            import httpx  # noqa: PLC0415

            response = httpx.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": os.environ.get("ANTHROPIC_SEARCH_MODEL", "claude-haiku-4-5-20251001"),
                    "max_tokens": 900,
                    "messages": [{"role": "user", "content": question}],
                    "tools": [
                        {
                            "type": "web_search_20260209",
                            "name": "web_search",
                            "max_uses": 1,
                            "allowed_domains": list(source_policy.provider_domains(source_policy.SEED_ALLOWLIST)),
                        }
                    ],
                },
                timeout=60.0,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            return Finding(question, "", backend=self.name, note=f"anthropic web search failed: {exc}", provider_unavailable=True)
        text = "\n".join(
            str(block.get("text", ""))
            for block in payload.get("content", [])
            if isinstance(block, dict) and block.get("type") == "text"
        )
        citations = source_policy.filter_urls(_urls_in(payload), source_policy.SEED_ALLOWLIST)
        return _filtered_finding(question, text, citations, self.name, self.cost_per_call)


class OpenAIBackend(Backend):
    """One official-domain OpenAI web search before the recorded fixture."""

    name = "openai"
    cost_per_call = 0.02

    def available(self) -> bool:
        return bool(os.environ.get("OPENAI_API_KEY"))

    def search(self, question: str, reserve: Callable[[float], None] | None = None) -> Finding:
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            return Finding(question, "", backend=self.name, note="OPENAI_API_KEY is not set", provider_unavailable=True)
        if reserve is not None:
            reserve(self.cost_per_call)
        try:
            import httpx  # noqa: PLC0415

            response = httpx.post(
                "https://api.openai.com/v1/responses",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={
                    "model": os.environ.get("OPENAI_SEARCH_MODEL", "gpt-5.6"),
                    "input": question,
                    "tools": [
                        {
                            "type": "web_search",
                            "filters": {
                                "allowed_domains": list(
                                    source_policy.provider_domains(source_policy.SEED_ALLOWLIST)
                                )
                            },
                        }
                    ],
                    "include": ["web_search_call.action.sources"],
                },
                timeout=60.0,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            return Finding(question, "", backend=self.name, note=f"openai web search failed: {exc}", provider_unavailable=True)
        text = str(payload.get("output_text") or "")
        if not text:
            text = "\n".join(_texts_in(payload))
        citations = source_policy.filter_urls(_urls_in(payload), source_policy.SEED_ALLOWLIST)
        return _filtered_finding(question, text, citations, self.name, self.cost_per_call)


def _urls_in(value) -> list[str]:
    """Read source URLs from either provider's nested response without an SDK."""
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "url" and isinstance(item, str):
                found.append(item)
            else:
                found.extend(_urls_in(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_urls_in(item))
    return list(dict.fromkeys(found))


def _texts_in(value) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        if value.get("type") == "output_text" and isinstance(value.get("text"), str):
            found.append(value["text"])
        for item in value.values():
            found.extend(_texts_in(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_texts_in(item))
    return found


def _filtered_finding(question: str, text: str, citations: list[str], backend: str, usd: float) -> Finding:
    if not citations:
        return Finding(
            question,
            "",
            backend=backend,
            usd=usd,
            note="search returned no citations on the approved allowlist",
        )
    return Finding(question, text, citations=citations, backend=backend, usd=usd)


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

    def search(self, question: str, reserve: Callable[[float], None] | None = None) -> Finding:
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
            if reserve is not None:
                reserve(self.cost_per_call)
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


class FallbackBackend(Backend):
    """Try the paper-safe provider chain without exposing it to the role.

    An empty but non-provider-error result is a source shortfall, not permission
    to hunt more broadly. Only an unavailable provider advances to the next
    backend. That keeps a DeepWiki-only result from quietly becoming a blog hunt.
    """

    name = "fallback"
    cost_per_call = 0.0

    def __init__(self, candidates: list[Backend]):
        self.candidates = candidates
        self.last_backend: Backend | None = None

    @property
    def active_name(self) -> str:
        if self.last_backend is not None:
            return self.last_backend.name
        return next((item.name for item in self.candidates if item.available()), self.name)

    @property
    def active_transport(self) -> str:
        if self.last_backend is None:
            return ""
        return self.last_backend.active_transport

    def available(self) -> bool:
        return any(candidate.available() for candidate in self.candidates)

    def search(self, question: str, reserve: Callable[[float], None] | None = None) -> Finding:
        repository = repository_doctrine_finding(question)
        if repository is not None:
            return repository
        notes = []
        for candidate in self.candidates:
            if not candidate.available():
                continue
            finding = candidate.search(question, reserve)
            self.last_backend = candidate
            if not finding.provider_unavailable:
                return finding
            notes.append(f"{candidate.name}: {finding.note}")
        return Finding(
            question,
            "",
            backend=self.name,
            note="; ".join(notes) or "no paper-safe research backend is available",
            provider_unavailable=True,
        )


def choose(*, fixture: Path | str | None = None, inbox: Path | str | None = None) -> Backend:
    """Build the Deep Agents paper chain: Perplexity, Anthropic, OpenAI, fixture.

    `inbox` is intentionally ignored here. The legacy Bing inbox remains an
    explicit classroom-only backend in `researcher.py --backend websearch`.
    """
    del inbox
    candidates: list[Backend] = [PerplexityBackend(), AnthropicBackend(), OpenAIBackend()]
    if fixture:
        candidates.append(FixtureBackend(fixture))
    chain = FallbackBackend(candidates)
    if chain.available():
        return chain
    raise RuntimeError(
        "no paper-safe research backend is available. Set PERPLEXITY_API_KEY, "
        "ANTHROPIC_API_KEY, or OPENAI_API_KEY, or point at a fixture file."
    )


@dataclass
class Researcher:
    """A budgeted client over whichever backend is available."""

    backend: Backend
    budget: Budget = field(default_factory=Budget)
    findings: list[Finding] = field(default_factory=list)

    def ask(self, question: str) -> Finding:
        finding = self.backend.search(question, self.budget.charge)
        finding.backend = finding.backend or self.backend.name
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
