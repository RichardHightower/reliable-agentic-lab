from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from paths import CRM_ROOT, GRADER, REPO_ROOT


def run_hidden_grader(cwd: Path | None = None) -> dict:
    root = cwd or REPO_ROOT
    crm = root / "solutions" / "crm" if (root / "solutions" / "crm").exists() else CRM_ROOT
    grader = root / "solutions" / "m2-harness" / "graders" / "test_due_date_contract.py"
    if not grader.exists():
        grader = GRADER
        crm = CRM_ROOT
    env = os.environ.copy()
    env["PYTHONPATH"] = str(crm) + os.pathsep + env.get("PYTHONPATH", "")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(grader), "-q"],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
    )
    output = (result.stdout or "") + (result.stderr or "")
    failed = _failed_node_ids(output)
    return {
        "exit_code": result.returncode,
        "passed": result.returncode == 0,
        "output": output,
        "failed_node_ids": failed,
    }


def _failed_node_ids(output: str) -> list[str]:
    names: list[str] = []
    for line in output.splitlines():
        if "FAILED" in line and "::" in line:
            node = line.split("FAILED", 1)[-1].strip().split()[0]
            names.append(node.split("::")[-1])
    return names
