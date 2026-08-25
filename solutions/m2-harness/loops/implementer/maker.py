from __future__ import annotations

from pathlib import Path

from paths import CRM_ROOT, FIXTURES, REPO_ROOT

ALLOWED_RELATIVE = {
    "app/dates.py",
    "app/models.py",
    "app/main.py",
    "app/templates/task_form.html",
    "app/templates/tasks.html",
}


class ToolDenied(RuntimeError):
    pass


def assert_crm_path(path: Path, crm_root: Path = CRM_ROOT) -> Path:
    resolved = path.resolve()
    crm = crm_root.resolve()
    if crm not in resolved.parents and resolved != crm:
        raise ToolDenied(f"Maker cannot touch {path}")
    return resolved


def write_crm(relative: str, content: str, crm_root: Path = CRM_ROOT) -> str:
    if relative not in ALLOWED_RELATIVE:
        raise ToolDenied(f"Maker write is scoped to the due-date files, not {relative}")
    path = assert_crm_path(crm_root / relative, crm_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return str(path)


def apply_reference_patch(crm_root: Path = CRM_ROOT) -> dict:
    if not FIXTURES.exists():
        return {"applied": False, "reason": "no_reference_fixtures", "files": []}
    written: list[str] = []
    for src in sorted(FIXTURES.rglob("*")):
        if not src.is_file():
            continue
        relative = str(src.relative_to(FIXTURES))
        if relative not in ALLOWED_RELATIVE:
            continue
        write_crm(relative, src.read_text(encoding="utf-8"), crm_root=crm_root)
        written.append(relative)
    return {"applied": True, "reason": "reference", "files": written}


def run(mode: str, crm_root: Path | None = None) -> dict:
    crm_root = crm_root or CRM_ROOT
    if mode == "reference":
        return apply_reference_patch(crm_root=crm_root)
    if mode == "none":
        return {
            "applied": False,
            "reason": "maker_none",
            "files": [],
            "hint": "Edit solutions/crm against the ready ticket, then rerun the harness.",
        }
    return {"applied": False, "reason": f"unknown_maker_mode:{mode}", "files": []}
