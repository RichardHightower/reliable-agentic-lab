"""The webhook map and the Actions workflow must name the same backends."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from solutions.extra_credit.s_ext_1_webhook.call_sol1 import BACKEND_FOLDERS  # noqa: E402

WORKFLOW = ROOT / "labs/lab1_enhancer/workflows/enhance-on-issue.yml"


def test_workflow_case_arms_cover_every_backend_key():
    text = WORKFLOW.read_text(encoding="utf-8")
    # Collect tokens in case arms of the Run one poll step.
    run_part = text.split("- name: Run one poll", 1)[1]
    arms = set(re.findall(r"^\s+([a-z0-9|-]+)\)\s*$", run_part, flags=re.M))
    named = set()
    for arm in arms:
        for part in arm.split("|"):
            named.add(part.strip())
    named.discard("*")
    missing = set(BACKEND_FOLDERS) - named
    extra = named - set(BACKEND_FOLDERS)
    assert not missing, f"workflow missing keys {sorted(missing)}"
    assert not extra, f"workflow extra keys {sorted(extra)}"


def test_unknown_backend_does_not_silently_run_claude():
    from solutions.extra_credit.s_ext_1_webhook import call_sol1

    try:
        call_sol1.folder_for("vscode-typo")
    except SystemExit:
        return
    raise AssertionError("unknown backend must fail")
