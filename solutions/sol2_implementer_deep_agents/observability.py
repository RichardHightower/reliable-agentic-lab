"""One trace writer. Langfuse when it is configured, a JSON file when it is not.

Local JSON is production if it is the record you actually open. Langfuse is the
same record in a pane. Neither is required to run the loop, and a missing key
must never change what the loop does.

    with trace("implementer", ticket="T001") as span:
        span.event("red_gate", failing=4)
        span.result(gate="pass", reason="the rubric is green")
"""

from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from pathlib import Path

# Pin the major version you tested. The v2 and v3 SDKs differ, and on v3 a
# score filter degrades to a no-op instead of raising, which reads as clean.
LANGFUSE_MAJOR = 3


def _client():
    """The Langfuse client, or None. A missing key is not an error."""
    if not (os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")):
        return None
    try:
        from langfuse import Langfuse  # noqa: PLC0415  (optional dependency)
    except ImportError:
        return None
    return Langfuse()


class Span:
    """One run. Collects events, then writes them once at the end."""

    def __init__(self, name: str, meta: dict):
        self.name = name
        self.meta = meta
        self.events: list[dict] = []
        self.outcome: dict = {}
        self.started = time.time()

    def event(self, label: str, **fields) -> None:
        self.events.append({"at": round(time.time() - self.started, 3), label: fields})

    def result(self, **fields) -> None:
        self.outcome = fields

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "meta": self.meta,
            "seconds": round(time.time() - self.started, 3),
            "events": self.events,
            "outcome": self.outcome,
        }


@contextmanager
def trace(name: str, out: Path | str = "work/traces", **meta):
    """Record one run. Always writes the local file, even on an exception.

    A trace that only appears when the run succeeds is the trace you cannot use,
    because the run you need to read is the one that failed.
    """
    span = Span(name, meta)
    try:
        yield span
    finally:
        folder = Path(out)
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{name}-{int(span.started)}.json"
        path.write_text(json.dumps(span.as_dict(), indent=2), encoding="utf-8")

        client = _client()
        if client is not None:
            client.create_event(name=name, metadata=span.as_dict())
            client.flush()
