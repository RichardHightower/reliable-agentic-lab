"""Resumable pipeline state, one JSON file per paper.

A nine stage run costs real money. Losing it to a dropped connection at stage
seven is the failure this file exists to prevent. Ported from the checkpoint in
articles v3:

    articles/article-creator-plugin/v3/article_pipeline/state.py

Two things carried over unchanged, because both were learned the expensive way.

The save is atomic. It writes a temp file next to the target and calls
`os.replace`, which is atomic on POSIX. A crash between the write and the rename
leaves the previous checkpoint intact. A plain `write_text` leaves a truncated
file that no resume can read.

The resume point is the first stage that is not complete, not `current_stage + 1`.
The dispatcher reruns anything that is not `complete` or `skipped`, failed stages
included, so `current_stage + 1` quietly claims the crashed stage finished.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STATE_FILE = ".paper-state.json"
VERSION = "1"

PENDING, IN_PROGRESS, COMPLETE, SKIPPED, FAILED = (
    "pending",
    "in_progress",
    "complete",
    "skipped",
    "failed",
)
DONE_STATES = (COMPLETE, SKIPPED)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class StageStatus:
    status: str = PENDING
    timestamp: str | None = None
    cost_usd: float = 0.0
    attempts: int = 0
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "timestamp": self.timestamp,
            "cost_usd": round(self.cost_usd, 4),
            "attempts": self.attempts,
            "error": self.error,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> StageStatus:
        return cls(
            status=data.get("status", PENDING),
            timestamp=data.get("timestamp"),
            cost_usd=float(data.get("cost_usd", 0.0)),
            attempts=int(data.get("attempts", 0)),
            error=data.get("error"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class PaperState:
    """Everything a resumed run needs and nothing it does not."""

    version: str = VERSION
    slug: str = ""
    topic: str = ""
    started_at: str = ""
    current_stage: str = ""
    total_cost_usd: float = 0.0
    total_calls: int = 0
    total_retries: int = 0
    backend: str = ""
    stages: dict[str, StageStatus] = field(default_factory=dict)
    artifacts: dict[str, str] = field(default_factory=dict)

    _path: Path | None = field(default=None, repr=False, compare=False)

    # -- reading -----------------------------------------------------------

    def is_complete(self, name: str) -> bool:
        entry = self.stages.get(name)
        return entry is not None and entry.status in DONE_STATES

    def first_incomplete(self, order: list[str]) -> str | None:
        """The stage the dispatcher will actually run next.

        Returns None when every stage in `order` is already done. A failed stage
        is not done, so a resume reruns it rather than stepping over it.
        """
        for name in order:
            if not self.is_complete(name):
                return name
        return None

    def attempts(self, name: str) -> int:
        entry = self.stages.get(name)
        return entry.attempts if entry else 0

    # -- writing -----------------------------------------------------------

    def _entry(self, name: str) -> StageStatus:
        if name not in self.stages:
            self.stages[name] = StageStatus()
        return self.stages[name]

    def mark_in_progress(self, name: str) -> None:
        entry = self._entry(name)
        entry.status = IN_PROGRESS
        entry.timestamp = now()
        entry.attempts += 1
        if entry.attempts > 1:
            self.total_retries += 1
        self.current_stage = name

    def mark_complete(self, name: str, *, cost_usd: float = 0.0, **metadata: Any) -> None:
        entry = self._entry(name)
        entry.status = COMPLETE
        entry.timestamp = now()
        entry.cost_usd += cost_usd
        entry.error = None
        entry.metadata.update(metadata)
        self.current_stage = name
        self.total_cost_usd += cost_usd

    def mark_skipped(self, name: str, reason: str = "") -> None:
        entry = self._entry(name)
        entry.status = SKIPPED
        entry.timestamp = now()
        if reason:
            entry.metadata["skipped_because"] = reason

    def mark_failed(self, name: str, error: str, *, cost_usd: float = 0.0) -> None:
        entry = self._entry(name)
        entry.status = FAILED
        entry.timestamp = now()
        entry.cost_usd += cost_usd
        entry.error = error
        self.current_stage = name
        self.total_cost_usd += cost_usd

    def record(self, name: str, path: str | Path) -> None:
        """Name an artifact this run produced, so a later stage can find it."""
        self.artifacts[name] = str(path)

    def spend(self, usd: float, calls: int = 1) -> None:
        self.total_cost_usd += usd
        self.total_calls += calls

    # -- persistence -------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "slug": self.slug,
            "topic": self.topic,
            "started_at": self.started_at,
            "current_stage": self.current_stage,
            "total_cost_usd": round(self.total_cost_usd, 4),
            "total_calls": self.total_calls,
            "total_retries": self.total_retries,
            "backend": self.backend,
            "stages": {name: entry.to_dict() for name, entry in self.stages.items()},
            "artifacts": self.artifacts,
        }

    def save(self) -> None:
        """Write the checkpoint atomically. A half-written file is unreadable."""
        if self._path is None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # The temp file sits beside the target so os.replace stays on one
        # filesystem. A cross-filesystem rename is not atomic.
        tmp = self._path.with_suffix(self._path.suffix + f".tmp.{os.getpid()}")
        try:
            tmp.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
            os.replace(tmp, self._path)
        except Exception:
            tmp.unlink(missing_ok=True)
            raise

    @classmethod
    def load_or_create(cls, work_dir: Path | str, *, slug: str = "", topic: str = "") -> PaperState:
        path = Path(work_dir) / STATE_FILE
        if not path.exists():
            state = cls(slug=slug, topic=topic, started_at=now())
            state._path = path
            return state
        data = json.loads(path.read_text(encoding="utf-8"))
        state = cls(
            version=data.get("version", VERSION),
            slug=data.get("slug", slug),
            topic=data.get("topic", topic),
            started_at=data.get("started_at", now()),
            current_stage=data.get("current_stage", ""),
            total_cost_usd=float(data.get("total_cost_usd", 0.0)),
            total_calls=int(data.get("total_calls", 0)),
            total_retries=int(data.get("total_retries", 0)),
            backend=data.get("backend", ""),
            artifacts=dict(data.get("artifacts", {})),
        )
        for name, entry in data.get("stages", {}).items():
            state.stages[name] = StageStatus.from_dict(entry)
        state._path = path
        return state

    def line(self) -> str:
        done = sum(1 for entry in self.stages.values() if entry.status in DONE_STATES)
        return (
            f"{done} stages done, ${self.total_cost_usd:.2f} spent, "
            f"{self.total_calls} calls, {self.total_retries} retries"
        )
