"""The source-admission wall for this standalone research port.

Provider filters are useful but advisory: an API can change, a redirect can
escape a domain, and a model can name a URL it did not retrieve.  This module
therefore owns both the domains sent to Perplexity and the post-filter applied
to every finding before it can become a claim or a reference.

It intentionally lives in this folder.  The workshop's ports are copyable
artifacts, not callers of a shared research package.
"""

from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import urlsplit

# Perplexity accepts at most twenty allowlist entries.  These are vendor docs,
# vendor repositories, this workshop's repository, and the two standards that
# the recorded offline corpus already cites.  Keep the list concrete: asking a
# model to decide what is reputable is how blogs re-enter the paper.
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
    "modelcontextprotocol.io",
    "sre.google",
)

MAX_PERPLEXITY_DOMAINS = 20
_GITHUB_ORGS = frozenset(
    entry.rsplit("/", 1)[1].lower() for entry in SEED_ALLOWLIST if entry.startswith("github.com/")
)
_EXACT_HOSTS = frozenset(entry.lower() for entry in SEED_ALLOWLIST if "/" not in entry)
_OFFICIAL_PREFIXES = ("docs.", "reference.", "learn.")


def host_for(url: str) -> str:
    """Return a normalized hostname, or an empty string for a malformed URL."""
    try:
        return (urlsplit(url).hostname or "").lower().rstrip(".")
    except ValueError:
        return ""


def _github_org(url: str) -> str:
    parsed = urlsplit(url)
    if (parsed.hostname or "").lower() != "github.com":
        return ""
    return next((piece.lower() for piece in parsed.path.split("/") if piece), "")


def _entry_host(entry: str) -> str:
    """The host part of either a Perplexity domain entry or a URL."""
    raw = entry.strip().lstrip("-")
    return host_for(raw if "://" in raw else f"https://{raw}")


def is_scout_candidate(url: str) -> bool:
    """Whether a scout result may extend the working allowlist.

    A scout may discover a new official documentation host, but it never gets
    to promote a course site, a personal blog, or an arbitrary GitHub account.
    """
    host = host_for(url)
    if not host:
        return False
    if host == "github.com":
        return _github_org(url) in _GITHUB_ORGS
    return host.startswith(_OFFICIAL_PREFIXES)


def merge_scout_domains(entries: Iterable[str], *, seed: Iterable[str] = SEED_ALLOWLIST) -> tuple[str, ...]:
    """Add only official scout results to the allowlist, capped for Perplexity."""
    merged = list(dict.fromkeys(str(item).strip() for item in seed if str(item).strip()))
    for url in entries:
        if len(merged) >= MAX_PERPLEXITY_DOMAINS:
            break
        if not is_scout_candidate(url):
            continue
        entry = f"github.com/{_github_org(url)}" if host_for(url) == "github.com" else host_for(url)
        if entry not in merged:
            merged.append(entry)
    return tuple(merged[:MAX_PERPLEXITY_DOMAINS])


def is_allowed_url(url: str, *, allowed_domains: Iterable[str] = SEED_ALLOWLIST) -> bool:
    """Return whether a URL clears the hard source-admission wall."""
    host = host_for(url)
    if not host:
        return False

    entries = tuple(str(entry).strip() for entry in allowed_domains if str(entry).strip())
    allowed_hosts = {_entry_host(entry) for entry in entries}
    if host == "github.com":
        org = _github_org(url)
        allowed_orgs = {
            entry.rsplit("/", 1)[1].lower()
            for entry in entries
            if entry.lower().startswith("github.com/")
        }
        return org in allowed_orgs

    return any(host == allowed or host.endswith(f".{allowed}") for allowed in allowed_hosts if allowed)


def filter_sources(
    sources: Iterable[dict], *, allowed_domains: Iterable[str] = SEED_ALLOWLIST
) -> list[dict]:
    """Keep one normalized source record for each allowed URL, in order."""
    accepted: list[dict] = []
    seen: set[str] = set()
    for raw in sources:
        if not isinstance(raw, dict):
            continue
        url = str(raw.get("url", "")).strip()
        if not is_allowed_url(url, allowed_domains=allowed_domains) or url in seen:
            continue
        accepted.append({"url": url, "title": str(raw.get("title", "")).strip()})
        seen.add(url)
    return accepted


def filter_claims(claims: Iterable[dict], *, allowed_domains: Iterable[str] = SEED_ALLOWLIST) -> list[dict]:
    """Drop a claim unless its cited source has cleared the same wall."""
    return [
        claim
        for claim in claims
        if isinstance(claim, dict)
        and is_allowed_url(str(claim.get("source_url", "")), allowed_domains=allowed_domains)
    ]
