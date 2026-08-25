from __future__ import annotations

import json
import re
from pathlib import Path


def load_notes(path: Path) -> dict:
    if path.suffix == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    return {"raw": path.read_text(encoding="utf-8"), "claims": []}


def check_facts(report: str, notes: dict) -> dict:
    issues: list[dict] = []
    blob = report.lower()
    forbidden = [str(x).lower() for x in notes.get("forbidden", [])]
    for bad in forbidden:
        if bad and bad in blob:
            issues.append(
                {
                    "severity": "critical",
                    "id": "contradiction",
                    "description": "Claim contradicts research notes.",
                    "current_text": bad,
                }
            )
    for item in notes.get("must_include", []):
        if str(item).lower() not in blob:
            issues.append(
                {
                    "severity": "major",
                    "id": f"missing:{item}",
                    "description": f"Report is missing required fact: {item}",
                }
            )
    blocking = [i for i in issues if i["severity"] in {"critical", "major"}]
    return {
        "status": "pass" if not blocking else "fail",
        "issues": issues,
        "failed_ids": [i["id"] for i in blocking],
        "passed": not blocking,
        "claim_count": len(re.findall(r"[.!?]", report)),
    }
