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

# The only organization types a proposed host may claim. The librarian picks
# from this list and cannot invent a value, which is what keeps `blog`,
# `cable_news`, and `encyclopedia` out. The order is the admission priority,
# and it follows the researcher card's primary-source order: specifications and
# official documentation first, trade press last.
ORG_TYPES = (
    "standards_body",
    "government",
    "peer_reviewed_publisher",
    "preprint",
    "professional_society",
    "university",
    "vendor_docs",
    "wire_service",
    "trade_press",
)

# Never admitted, whatever type is claimed. Aggregators, social sites, and
# encyclopedias. Wikipedia is a fine way to design a publisher map and a bad
# thing for a paper to cite.
DENYLIST = frozenset(
    {
        "medium.com",
        "reddit.com",
        "twitter.com",
        "x.com",
        "pinterest.com",
        "quora.com",
        "deepwiki.com",
        "substack.com",
        "en.wikipedia.org",
        "wikipedia.org",
        # Cable news, pinned. `cable_news` is not in the enum, so the only way
        # these enter is by claiming to be a wire service or trade press. They
        # are neither, and on a timely query they outrank the journals. The
        # news-shaped analog of a primary source is a wire service: Reuters,
        # the AP, the BBC.
        "cnn.com",
        "foxnews.com",
        "msnbc.com",
        "nbcnews.com",
        "abcnews.go.com",
        "cbsnews.com",
        "newsmax.com",
    }
)

# The only top level domains admitted as a whole. `.org` is deliberately absent:
# arxiv.org and acm.org are `.org`, and so are content mills, vendor marketing,
# and advocacy shops. Name those hosts individually instead.
ALLOWED_TLDS = frozenset({".gov", ".edu", ".int"})

# Below this many admitted hosts the run keeps the seed instead. A librarian
# that returns almost nothing is worse than no librarian.
MIN_ADMITTED = 3
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


def _normalize_host(raw: str) -> str:
    """A bare host, or a TLD, or "" when the entry cannot be one.

    Strips a scheme, a path, a port, and a leading `*.` or `www.`. A model that
    proposes `https://arxiv.org/list/cs` means `arxiv.org`, and rejecting it on
    formatting would waste the turn.
    """
    entry = str(raw or "").strip().lower()
    if not entry:
        return ""
    if "//" in entry:
        entry = urlsplit(entry).netloc or entry.split("//", 1)[1]
    entry = entry.split("/", 1)[0].split("@")[-1].split(":", 1)[0]
    entry = entry.removeprefix("*.").removeprefix("www.").strip(".")
    if not entry:
        return ""
    # A TLD arrives as `gov` or `.gov`. Keep the dot so it never reads as a host.
    if "." not in entry:
        return f".{entry}"
    if any(character.isspace() for character in entry):
        return ""
    return entry


def admit(proposed: Iterable[dict], *, cap: int = MAX_PERPLEXITY_DOMAINS) -> dict:
    """Decide which proposed hosts a run may search. Python decides, not a model.

    The librarian proposes and this admits. A model that could widen its own
    allowlist would be deciding what counts as reputable, and that is how blogs
    re-enter the paper. Every rule below is arithmetic or set membership.

    Returns the artifact written to `corpus/source_allowlist.json`: what was
    proposed, what was dropped and why, and what was admitted.
    """
    admitted: list[tuple[int, str]] = []
    dropped: list[dict] = []
    seen: set[str] = set()
    proposals = [item for item in (proposed or []) if isinstance(item, dict)]

    for item in proposals:
        host = _normalize_host(item.get("host", ""))
        org_type = str(item.get("org_type") or "").strip().lower()

        def drop(reason: str) -> None:
            dropped.append({"host": item.get("host"), "org_type": item.get("org_type"), "why": reason})

        if not host:
            drop("not a host")
            continue
        if org_type not in ORG_TYPES:
            drop(f"org_type {org_type!r} is not one of {', '.join(ORG_TYPES)}")
            continue
        if host in DENYLIST:
            drop("on the denylist")
            continue
        if host.startswith("."):
            if host not in ALLOWED_TLDS:
                drop(f"{host} is not an admitted top level domain")
                continue
        elif host.count(".") == 0:
            drop("not a host")
            continue
        if host in seen:
            drop("duplicate")
            continue
        seen.add(host)
        admitted.append((ORG_TYPES.index(org_type), host))

    # Stable: type priority, then host. The same outline admits the same list in
    # the same order, so a rerun does not reshuffle the provider filter.
    admitted.sort()
    kept = tuple(host for _priority, host in admitted[: max(0, int(cap))])
    for _priority, host in admitted[max(0, int(cap)) :]:
        dropped.append({"host": host, "why": f"over the cap of {cap}"})

    return {
        "proposed": [
            {"host": item.get("host"), "org_type": item.get("org_type"), "why": item.get("why")}
            for item in proposals
        ],
        "dropped": dropped,
        "admitted": list(kept),
    }


def run_allowlist(admitted: Iterable[str]) -> tuple[str, ...]:
    """The domains this run may search, or the seed when the librarian gave too few.

    A dead model, a timeout, or a librarian that admits two hosts must not stop
    the run or silently narrow it to nothing.
    """
    hosts = tuple(dict.fromkeys(str(host) for host in (admitted or []) if str(host).strip()))
    if len(hosts) < MIN_ADMITTED:
        return SEED_ALLOWLIST
    return hosts[:MAX_PERPLEXITY_DOMAINS]
