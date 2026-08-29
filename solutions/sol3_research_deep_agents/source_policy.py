"""The source policy for this standalone Deep Agents white-paper port.

The model never decides which companies are reputable.  Search providers receive
the allowlist as a first filter, but this module is the hard wall: anything that
does not pass here is absent from the evidence ledger and cannot reach a paper.
"""

from __future__ import annotations

from urllib.parse import urlparse


# Keep this list literal and small. Perplexity accepts at most 20 domain
# filters, and an explicit list is reviewable in the workshop room.
SEED_ALLOWLIST = (
    "docs.langchain.com",
    "reference.langchain.com",
    "docs.claude.com",
    "platform.claude.com",
    "docs.anthropic.com",
    "docs.openai.com",
    "github.com/langchain-ai",
    "github.com/anthropics",
    "github.com/openai",
    "github.com/RichardHightower",
    "learn.microsoft.com",
    "docs.stripe.com",
)
MAX_ALLOWLIST = 20
DENYLIST = (
    "medium.com",
    "reddit.com",
    "twitter.com",
    "x.com",
    "pinterest.com",
    "quora.com",
    "deepwiki.com",
    "substack.com",
)

_GITHUB_ORGS = frozenset({"langchain-ai", "anthropics", "openai", "richardhightower"})
_OFFICIAL_PREFIXES = ("docs.", "reference.", "learn.")


def host(url: str) -> str:
    """Return a normalized hostname, or an empty string for a non-URL."""
    parsed = urlparse(url)
    value = (parsed.hostname or "").lower().rstrip(".")
    return value.removeprefix("www.")


def _path_parts(url: str) -> list[str]:
    return [part for part in urlparse(url).path.split("/") if part]


def is_scout_candidate(url: str) -> bool:
    """Whether a discovered URL may extend the working domain filter.

    Scout does not make a URL valid by itself. It only admits official-looking
    documentation hosts, one of the vendor GitHub organizations already named
    in the seed list, or this repository.
    """
    value = host(url)
    if not value or value in DENYLIST:
        return False
    if value == "github.com":
        parts = _path_parts(url)
        return bool(parts) and parts[0].lower() in _GITHUB_ORGS
    return value.startswith(_OFFICIAL_PREFIXES)


def merge_allowlist(urls: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    """Append qualified scout hosts, preserving the fixed seed and 20-item cap."""
    merged = list(SEED_ALLOWLIST)
    known = {entry.lower() for entry in merged}
    for url in urls:
        value = host(url)
        if not value or not is_scout_candidate(url):
            continue
        # GitHub is filtered by organization in `url_allowed`; the provider
        # receives the org path rule from the seed list rather than a bare host.
        entry = value if value != "github.com" else f"github.com/{_path_parts(url)[0]}"
        if entry.lower() in known:
            continue
        merged.append(entry)
        known.add(entry.lower())
        if len(merged) == MAX_ALLOWLIST:
            break
    return tuple(merged)


def url_allowed(url: str, allowlist: tuple[str, ...] = SEED_ALLOWLIST) -> bool:
    """Apply the real source wall to one HTTP(S) URL."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    value = host(url)
    if not value or value in DENYLIST:
        return False
    entries = {entry.lower() for entry in allowlist}
    if value == "github.com":
        parts = _path_parts(url)
        return bool(parts) and f"github.com/{parts[0].lower()}" in entries
    return value in entries and (value in {entry.lower() for entry in SEED_ALLOWLIST} or is_scout_candidate(url))


def filter_urls(urls: list[str] | tuple[str, ...], allowlist: tuple[str, ...]) -> list[str]:
    """Keep allowed URLs once, in provider order."""
    kept: list[str] = []
    for url in urls:
        clean = str(url).strip().rstrip(".,;)")
        if clean not in kept and url_allowed(clean, allowlist):
            kept.append(clean)
    return kept


def unallowed_urls(urls: list[str] | tuple[str, ...], allowlist: tuple[str, ...] = SEED_ALLOWLIST) -> list[str]:
    """Return invalid citation URLs for a deterministic paper-gate report."""
    return [str(url) for url in urls if not url_allowed(str(url), allowlist)]


def provider_domains(allowlist: tuple[str, ...]) -> tuple[str, ...]:
    """Host-only form for providers whose filters do not accept URL paths."""
    domains: list[str] = []
    for entry in allowlist:
        value = entry.split("/", 1)[0].lower()
        if value not in domains:
            domains.append(value)
    return tuple(domains)
