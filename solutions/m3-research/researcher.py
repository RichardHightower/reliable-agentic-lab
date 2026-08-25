from __future__ import annotations

import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "fixtures" / "research.json"


def research(topic: str, work_dir: Path) -> dict:
    """Research sub-agent. Orchestrator gets a summary, not the dump.

    Uses Perplexity if PERPLEXITY_API_KEY is set. Otherwise the local fixture.
    """
    key = os.environ.get("PERPLEXITY_API_KEY")
    notes = json.loads(FIXTURE.read_text(encoding="utf-8"))
    notes["topic"] = topic
    notes["backend"] = "perplexity" if key else "fixture"
    if key:
        notes["summary"] = (
            notes.get("summary", "")
            + " Perplexity key present. Fixture still grounds the lab so Saturday does not depend on signup."
        )
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "research_notes.json").write_text(json.dumps(notes, indent=2), encoding="utf-8")
    (work_dir / "research_summary.md").write_text(
        f"# Research summary\n\n{notes.get('summary', '')}\n",
        encoding="utf-8",
    )
    return {
        "summary": notes.get("summary", ""),
        "backend": notes["backend"],
        "source_count": len(notes.get("sources", [])),
        "path": str(work_dir / "research_notes.json"),
    }
