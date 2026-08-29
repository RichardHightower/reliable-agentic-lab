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
import re
from base64 import urlsafe_b64decode
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from threading import Lock
from typing import Callable
from urllib.parse import parse_qs, urlencode, urljoin, urlparse
from urllib.request import Request, urlopen


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
    _lock: Lock = field(default_factory=Lock, init=False, repr=False, compare=False)

    def begin_request(self, max_calls: int | None = None) -> None:
        """Start one agent request with an optional per-request tool ceiling."""
        with self._lock:
            self._request_limit = max_calls
            self._request_calls = 0

    def end_request(self) -> None:
        with self._lock:
            self._request_limit = None
            self._request_calls = 0

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

    def search(self, question: str) -> Finding:
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
    candidates: list[Backend] = [PerplexityBackend(), WebSearchBackend(inbox)]
    if fixture:
        candidates.append(FixtureBackend(fixture))
    for backend in candidates:
        if backend.available():
            return backend
    raise RuntimeError(
        "no research backend is available. Set PERPLEXITY_API_KEY, restore "
        "network access for web search, or point at a fixture file."
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
