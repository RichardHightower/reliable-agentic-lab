#!/usr/bin/env python3
"""Confirm the judge and the doer cannot write, spawn, or run a shell.

Antigravity isolation is a per-agent tools allowlist. The orchestrator skill
runs in the parent agent, which holds write and `invoke_subagent`.
The two custom agents must not. A tools line that includes
`replace_file_content`, `run_command`, or `invoke_subagent` removes the
reason the loop can be trusted.

Also checks the plugin tree: plugin.json name, skill directory name, and
that the three workspace registration paths resolve.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
PLUGIN = HERE / ".agents" / "plugins" / "ticket-enhancer"
FORBIDDEN = {
    "replace_file_content",
    "run_command",
    "invoke_subagent",
    "write_to_file",
    "edit",
}
REQUIRED = {"view_file", "grep_search"}
AGENTS = (
    PLUGIN / "agents" / "enhancer-doer.md",
    PLUGIN / "agents" / "enhancer-judge.md",
)


def _frontmatter(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise SystemExit(f"{path}: missing YAML frontmatter")
    end = text.find("\n---", 3)
    if end < 0:
        raise SystemExit(f"{path}: unclosed YAML frontmatter")
    return text[3:end]


def _tools(front: str) -> list[str]:
    inline = re.search(r"^tools:\s*\[([^\]]*)\]", front, re.M)
    if inline:
        raw = inline.group(1)
        return [item.strip().strip("'\"") for item in raw.split(",") if item.strip()]
    block = re.search(r"^tools:\s*\n((?:[ \t]*-[ \t]*.+\n)+)", front, re.M)
    if not block:
        raise SystemExit("tools: list missing from agent frontmatter")
    items = []
    for line in block.group(1).splitlines():
        item = line.strip().lstrip("-").strip().strip("'\"")
        if item:
            items.append(item)
    return items


def main() -> int:
    errors: list[str] = []

    plugin = json.loads((PLUGIN / "plugin.json").read_text(encoding="utf-8"))
    if plugin.get("name") != "ticket-enhancer":
        errors.append(f"plugin.json name is {plugin.get('name')!r}, want ticket-enhancer")

    skill = PLUGIN / "skills" / "enhancer-loop" / "SKILL.md"
    skill_front = _frontmatter(skill)
    name_match = re.search(r"^name:\s*(\S+)", skill_front, re.M)
    if not name_match or name_match.group(1) != "enhancer-loop":
        errors.append("SKILL.md name must be enhancer-loop and match its directory")
    if "/" in (name_match.group(1) if name_match else ""):
        errors.append("skill name must not carry a namespace prefix")

    for path in AGENTS:
        front = _frontmatter(path)
        tools = _tools(front)
        lowered = [t.lower() for t in tools]
        hits = [t for t in tools if t.lower() in FORBIDDEN]
        if hits:
            errors.append(f"{path.name} tools include {hits}; judge and doer must be read-only")
        for need in REQUIRED:
            if need not in lowered:
                errors.append(f"{path.name} is missing {need}")
        if not re.search(r"^subagent:\s*true\s*$", front, re.M):
            errors.append(f"{path.name} must set subagent: true")
        if not re.search(r"^mainAgent:\s*false\s*$", front, re.M):
            errors.append(f"{path.name} must set mainAgent: false")
        if not re.search(r"^commandExecutionPolicy:\s*off\s*$", front, re.M):
            errors.append(f"{path.name} must set commandExecutionPolicy: off")

    links = {
        HERE / ".agents" / "skills" / "enhancer-loop" / "SKILL.md": skill,
        HERE / ".agents" / "agents" / "enhancer-doer.md": AGENTS[0],
        HERE / ".agents" / "agents" / "enhancer-judge.md": AGENTS[1],
    }
    for link, target in links.items():
        if not link.exists():
            errors.append(f"missing workspace registration {link.relative_to(HERE)}")
            continue
        resolved = link.resolve()
        if resolved != target.resolve():
            errors.append(
                f"{link.relative_to(HERE)} resolves to {resolved}, want {target}"
            )

    if errors:
        print("fence_check: FAIL")
        for item in errors:
            print(f"  {item}")
        return 1
    print("fence_check: the judge and the doer are read-only")
    print("fence_check: plugin, skill name, and three registration paths match")
    return 0


if __name__ == "__main__":
    sys.exit(main())
