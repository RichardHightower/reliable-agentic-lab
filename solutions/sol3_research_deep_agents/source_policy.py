"""The source-admission wall for this standalone Deep Agents research port.

Provider filters are useful but advisory: an API can change, a redirect can
escape a domain, and a model can name a URL it did not retrieve. This module
therefore owns both the domains sent to Perplexity and the post-filter applied
to every finding before it can become a claim or a reference.

It intentionally lives in this folder. The workshop's ports are copyable
artifacts, not callers of a shared research package. Copied from the Agent SDK
port for #304, not imported.
"""

from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import urlparse, urlsplit

# Perplexity accepts at most twenty allowlist entries. These are vendor docs
# and this workshop's repository. Keep the list concrete: asking a model to
# decide what is reputable is how blogs re-enter the paper. The librarian
# proposes a topic's twenty; `admit` decides; this seed is the fallback.
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
MAX_PERPLEXITY_DOMAINS = MAX_ALLOWLIST

# The only organization types a proposed host may claim. The librarian picks
# from this list and cannot invent a value, which is what keeps `blog`,
# `cable_news`, and `encyclopedia` out. The order is the admission priority.
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

# Never admitted, whatever type is claimed. Aggregators, social sites,
# encyclopedias, and cable news. Wikipedia is a fine way to design a publisher
# map and a bad thing for a paper to cite.
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
# arxiv.org and acm.org are `.org`, and so are content mills. Name those hosts.
ALLOWED_TLDS = frozenset({".gov", ".edu", ".int"})

# Below this many admitted hosts the run keeps the seed instead.
MIN_ADMITTED = 3

_GITHUB_ORGS = frozenset(
    entry.rsplit("/", 1)[1].lower() for entry in SEED_ALLOWLIST if entry.startswith("github.com/")
)
_OFFICIAL_PREFIXES = ("docs.", "reference.", "learn.")


def host(url: str) -> str:
    """Return a normalized hostname, or an empty string for a non-URL."""
    parsed = urlparse(url)
    value = (parsed.hostname or "").lower().rstrip(".")
    return value.removeprefix("www.")


def _path_parts(url: str) -> list[str]:
    return [part for part in urlparse(url).path.split("/") if part]


def _denied(value: str) -> bool:
    return value in DENYLIST or any(value.endswith(f".{denied}") for denied in DENYLIST)


def is_scout_candidate(url: str) -> bool:
    """Whether a discovered URL may extend the working domain filter.

    Scout does not make a URL valid by itself. It only admits official-looking
    documentation hosts, one of the vendor GitHub organizations already named
    in the seed list, or this repository. It cannot promote CNN.
    """
    value = host(url)
    if not value or _denied(value):
        return False
    if value == "github.com":
        parts = _path_parts(url)
        return bool(parts) and parts[0].lower() in _GITHUB_ORGS
    return value.startswith(_OFFICIAL_PREFIXES)


def merge_allowlist(
    urls: list[str] | tuple[str, ...],
    *,
    seed: Iterable[str] = SEED_ALLOWLIST,
) -> tuple[str, ...]:
    """Append qualified scout hosts onto this run's seed, capped at 20."""
    merged = list(dict.fromkeys(str(item).strip() for item in seed if str(item).strip()))
    known = {entry.lower() for entry in merged}
    for url in urls:
        if len(merged) >= MAX_ALLOWLIST:
            break
        value = host(url)
        if not value or not is_scout_candidate(url):
            continue
        entry = value if value != "github.com" else f"github.com/{_path_parts(url)[0]}"
        if entry.lower() in known:
            continue
        merged.append(entry)
        known.add(entry.lower())
    return tuple(merged[:MAX_ALLOWLIST])


def url_allowed(url: str, allowlist: tuple[str, ...] = SEED_ALLOWLIST) -> bool:
    """Apply the real source wall to one HTTP(S) URL.

    The wall is the list this run admitted, not the leftover vendor seed. A
    host on the run list is in; a host only on the seed is out once the
    librarian has replaced it.
    """
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    value = host(url)
    if not value or _denied(value):
        return False
    for entry in allowlist:
        item = str(entry).strip().lower()
        if not item:
            continue
        if item.startswith("github.com/"):
            if value == "github.com":
                parts = _path_parts(url)
                if parts and f"github.com/{parts[0].lower()}" == item:
                    return True
            continue
        if item.startswith("."):
            if value.endswith(item) or value == item[1:]:
                return True
            continue
        if value == item or value.endswith(f".{item}"):
            return True
    return False


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


def _normalize_host(raw: str) -> str:
    """A bare host, or a TLD, or "" when the entry cannot be one."""
    entry = str(raw or "").strip().lower()
    if not entry:
        return ""
    if "//" in entry:
        entry = urlsplit(entry).netloc or entry.split("//", 1)[1]
    entry = entry.split("/", 1)[0].split("@")[-1].split(":", 1)[0]
    entry = entry.removeprefix("*.").removeprefix("www.").strip(".")
    if not entry:
        return ""
    if "." not in entry:
        return f".{entry}"
    if any(character.isspace() for character in entry):
        return ""
    return entry


def admit(proposed: Iterable[dict], *, cap: int = MAX_PERPLEXITY_DOMAINS) -> dict:
    """Decide which proposed hosts a run may search. Python decides, not a model.

    The librarian proposes and this admits. A model that could widen its own
    allowlist would be deciding what counts as reputable, and that is how blogs
    re-enter the paper.
    """
    admitted: list[tuple[int, str]] = []
    dropped: list[dict] = []
    seen: set[str] = set()
    proposals = [item for item in (proposed or []) if isinstance(item, dict)]

    for item in proposals:
        hostname = _normalize_host(item.get("host", ""))
        org_type = str(item.get("org_type") or "").strip().lower()

        def drop(reason: str, current: dict = item) -> None:
            dropped.append({"host": current.get("host"), "org_type": current.get("org_type"), "why": reason})

        if not hostname:
            drop("not a host")
            continue
        if org_type not in ORG_TYPES:
            drop(f"org_type {org_type!r} is not one of {', '.join(ORG_TYPES)}")
            continue
        if hostname in DENYLIST:
            drop("on the denylist")
            continue
        if hostname.startswith("."):
            if hostname not in ALLOWED_TLDS:
                drop(f"{hostname} is not an admitted top level domain")
                continue
        elif hostname.count(".") == 0:
            drop("not a host")
            continue
        if hostname in seen:
            drop("duplicate")
            continue
        seen.add(hostname)
        admitted.append((ORG_TYPES.index(org_type), hostname))

    admitted.sort()
    kept = tuple(host for _priority, host in admitted[: max(0, int(cap))])
    for _priority, extra in admitted[max(0, int(cap)) :]:
        dropped.append({"host": extra, "why": f"over the cap of {cap}"})

    return {
        "proposed": [
            {"host": item.get("host"), "org_type": item.get("org_type"), "why": item.get("why")}
            for item in proposals
        ],
        "dropped": dropped,
        "admitted": list(kept),
    }


def run_allowlist(admitted: Iterable[str]) -> tuple[str, ...]:
    """The domains this run may search, or the seed when the librarian gave too few."""
    hosts = tuple(dict.fromkeys(str(item).strip() for item in (admitted or []) if str(item).strip()))
    if len(hosts) < MIN_ADMITTED:
        return SEED_ALLOWLIST
    return hosts[:MAX_PERPLEXITY_DOMAINS]
