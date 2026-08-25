from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from paths import TRACE_DIR


def new_trace_id() -> str:
    return "local-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def write_trace(payload: dict, path: Path | None = None) -> Path:
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    out = path or (TRACE_DIR / "last-loop.json")
    text = json.dumps(payload, indent=2)
    out.write_text(text, encoding="utf-8")
    history = TRACE_DIR / f"{payload.get('trace_id', 'loop')}.json"
    history.write_text(text, encoding="utf-8")
    return out
