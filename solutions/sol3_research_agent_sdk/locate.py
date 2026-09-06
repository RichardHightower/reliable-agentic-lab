"""Which findings came out of the cabinet, and which URL may stand for one.

Run 21 published a bibliography whose corpus entries were `corpus:knowledge:
claim.x`, a bare ULID, or `not-found`. Every one of those is a reference a
reader cannot open. The cabinet knows what it read; it does not know where the
public copy lives.

This module is the Python half of finding that copy. It picks the findings that
came from the cabinet, builds the one question the locator turn is asked, and
admits the answer. The model proposes a URL and never gets to install it: a
`supports: false`, a scheme that is not http(s), or a string with whitespace in
it is dropped here, without argument.

The admission guard is the same bar `rkc.attach_url` applies before it writes
`url:` onto a SourceDocument. It is four lines and it is copied on purpose, so
this module has no reason to import the write path. Keep the two in lockstep.
"""

from __future__ import annotations

import sys
from urllib.parse import urlsplit

# How much of the claim the locator sees. Enough to recognize the document,
# short enough that it cannot start researching the claim instead.
CLAIM_HEAD_WORDS = 20


def is_cabinet(finding: dict) -> bool:
    """True when this finding came out of the corpus rather than the live web.

    Three tells, because three writers produce findings. `sections.py` sets
    `source.kind` and `origin`; a hand-written or resumed finding may carry
    neither, and then the reference itself is the evidence: anything that is
    not an http(s) URL is a cabinet key, a file path, or `not-found`.
    """
    source = finding.get("source") or {}
    if source.get("kind") == "corpus":
        return True
    if finding.get("origin") == "corpus":
        return True
    ref = str(source.get("url_or_path") or "").strip().lower()
    return not ref.startswith(("http://", "https://"))


def normalize_key(ref: str) -> str:
    """The corpus key without its transport prefix.

    `corpus://knowledge:claim.x`, `corpus:knowledge:claim.x` and
    `knowledge:claim.x` are three spellings of one key. `brain:claim.x` is not
    prefixed and passes through unchanged.
    """
    text = str(ref or "").strip()
    for prefix in ("corpus://", "corpus:"):
        if text.startswith(prefix):
            text = text[len(prefix) :]
            break
    return text.strip()


def query_for(finding: dict) -> dict:
    """The three things the locator turn is given, and nothing else."""
    source = finding.get("source") or {}
    words = str(finding.get("claim") or "").split()
    return {
        "title": str(source.get("title") or ""),
        "vendor": str(source.get("vendor") or ""),
        "claim_head": " ".join(words[:CLAIM_HEAD_WORDS]),
    }


def admit(reply: dict) -> str:
    """The URL a reader can open, or an empty string.

    A `supports: false` is a miss the locator reported honestly, and a miss must
    not become a citation. Everything after that is the `rkc.attach_url` bar: a
    raw `"` or `\\` is refused because `corpus.parse_front_matter` does not
    unescape one, so such a URL comes back corrupted.
    """
    if (reply or {}).get("supports") is not True:
        return ""
    url = str(reply.get("url") or "")
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return ""
    if any(c.isspace() for c in url) or '"' in url or "\\" in url:
        return ""
    return url


def demo() -> None:
    ok = {"url": "https://arxiv.org/abs/2503.13657", "supports": True, "excerpt": "x"}
    assert admit(ok) == "https://arxiv.org/abs/2503.13657"
    assert admit({**ok, "supports": False}) == ""
    assert admit({"url": "corpus:knowledge:claim.x", "supports": True}) == ""
    assert admit({"url": "not-found", "supports": True}) == ""
    assert admit({"url": "https://a.invalid/a b", "supports": True}) == ""

    assert is_cabinet({"source": {"url_or_path": "corpus:knowledge:claim.x"}})
    assert is_cabinet({"source": {"url_or_path": ""}})
    assert not is_cabinet({"source": {"kind": "web", "url_or_path": "https://a.invalid/x"}})

    assert normalize_key("corpus://knowledge:claim.x") == "knowledge:claim.x"
    assert normalize_key("corpus:knowledge:claim.x") == "knowledge:claim.x"
    assert normalize_key("brain:claim.x") == "brain:claim.x"

    long_claim = " ".join(f"w{n}" for n in range(40))
    query = query_for({"claim": long_claim, "source": {"title": "T", "vendor": "V"}})
    assert len(query["claim_head"].split()) == CLAIM_HEAD_WORDS, query
    assert query["title"] == "T" and query["vendor"] == "V"
    print("locate: ok")


if __name__ == "__main__":
    raise SystemExit(demo() if "--demo" in sys.argv else 0)
