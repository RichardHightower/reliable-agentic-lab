"""Which reply sources came out of the cabinet, and which URL may stand for one.

A researcher that reads `corpus_search` reports the hit as a source, and the
only reference it has for it is the corpus key: `corpus:knowledge:claim.x`, a
bare ULID, or `not-found`. Every one of those is a reference a reader cannot
open. The cabinet knows what it read; it does not know where the public copy
lives.

This module is the Python half of finding that copy. It picks the reply sources
that came from the cabinet, builds the one question the locator turn is asked,
and admits the answer. The model proposes a URL and never gets to install it: a
`supports: false`, a scheme that is not http(s), or a string with whitespace in
it is dropped here, without argument.

The admission guard is the same bar `corpus.attach_url` applies before it
writes `url:` onto a SourceDocument. It is four lines and it is copied on
purpose, so this module has no reason to import the write path. Keep the two in
lockstep.

    python3 locate.py --demo
"""

from __future__ import annotations

import sys
from urllib.parse import urlsplit

# How much of the claim the locator sees. Enough to recognize the document,
# short enough that it cannot start researching the claim instead.
CLAIM_HEAD_WORDS = 20


def is_cabinet_url(url: str) -> bool:
    """True when this reply source names the corpus rather than the live web.

    The reference itself is the evidence. Anything that is not an http(s) URL
    is a cabinet key, a file path, or `not-found`. An empty string counts as a
    cabinet reference too: a researcher that read the brain and left `url`
    blank has still cited something a reader cannot open.
    """
    return not str(url or "").strip().lower().startswith(("http://", "https://"))


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


def query_for(title: str, vendor: str, claim: str) -> str:
    """The three things the locator turn is given, and nothing else.

    The claim is cut to its head. A locator that sees the whole claim starts
    answering it, and this turn is a cross-reference, not research.
    """
    head = " ".join(str(claim or "").split()[:CLAIM_HEAD_WORDS])
    return (
        "Find the public page that carries this source. This is a "
        "cross-reference, not research.\n"
        f"Title: {title or '(none)'}\n"
        f"Vendor: {vendor or '(none)'}\n"
        f"The claim begins: {head}\n"
        "Call locate once. It is not domain filtered, so any host is "
        "admissible. Never invent a URL: a page you did not open is a miss.\n"
        'Return ONLY {"url": "...", "supports": true, "excerpt": "..."} '
        'or {"url": "", "supports": false, "excerpt": ""}.'
    )


def admit(reply: dict) -> str:
    """The URL a reader can open, or an empty string.

    A `supports: false` is a miss the locator reported honestly, and a miss must
    not become a citation. Everything after that is the `corpus.attach_url`
    bar: a raw `"` or `\\` is refused because `corpus.parse_front_matter` does
    not unescape one, so such a URL comes back corrupted.
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


def demo() -> int:
    ok = {"url": "https://arxiv.org/abs/2503.13657", "supports": True, "excerpt": "x"}
    assert admit(ok) == "https://arxiv.org/abs/2503.13657"
    assert admit({**ok, "supports": False}) == ""
    assert admit({"url": "corpus:knowledge:claim.x", "supports": True}) == ""
    assert admit({"url": "not-found", "supports": True}) == ""
    assert admit({"url": "https://a.invalid/a b", "supports": True}) == ""

    assert is_cabinet_url("corpus:knowledge:claim.x")
    assert is_cabinet_url("")
    assert is_cabinet_url("  NOT-FOUND ")
    assert not is_cabinet_url("https://a.invalid/x")
    assert not is_cabinet_url("  HTTPS://a.invalid/x ")

    assert normalize_key("corpus://knowledge:claim.x") == "knowledge:claim.x"
    assert normalize_key("corpus:knowledge:claim.x") == "knowledge:claim.x"
    assert normalize_key("brain:claim.x") == "brain:claim.x"

    long_claim = " ".join(f"w{n}" for n in range(40))
    prompt = query_for("T", "V", long_claim)
    assert "Title: T" in prompt and "Vendor: V" in prompt
    head = prompt.split("The claim begins: ")[1].split("\n")[0]
    assert len(head.split()) == CLAIM_HEAD_WORDS, head
    print("locate: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(demo() if "--demo" in sys.argv else 0)
