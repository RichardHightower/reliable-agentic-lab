#!/usr/bin/env python3
"""Confirm the judge and the doer cannot write, spawn, or run a shell.

VS Code isolation is a per-agent tools allowlist. The orchestrator skill
runs in the parent Copilot agent, which holds write and the `agent` tool.
The two custom agents must not. A tools line that includes `edit`,
`runCommands`, or `agent` removes the reason the loop can be trusted.

Also checks the plugin tree: plugin.json name, skill directory name, and
that the three workspace registration paths resolve.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
PLUGIN = HERE / ".github" / "plugins" / "ticket-enhancer"
FORBIDDEN = {"edit", "runcommands", "agent", "runnotebooks", "runtasks"}
AGENTS = (
    PLUGIN / "com.github.copilot" / "agents" / "enhancer-doer.agent.md",
    PLUGIN / "com.github.copilot" / "agents" / "enhancer-judge.agent.md",
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
    match = re.search(r"^tools:\s*\[([^\]]*)\]", front, re.M)
    if not match:
        raise SystemExit("tools: list missing from agent frontmatter")
    raw = match.group(1)
    return [item.strip().strip("'\"") for item in raw.split(",") if item.strip()]


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
        hits = [t for t in tools if t.lower().split("/")[0] in FORBIDDEN]
        if hits:
            errors.append(f"{path.name} tools include {hits}; judge and doer must be read-only")
        if "search/codebase" not in tools:
            errors.append(f"{path.name} is missing search/codebase")

    links = {
        HERE / ".github" / "skills" / "enhancer-loop" / "SKILL.md": skill,
        HERE / ".github" / "agents" / "enhancer-doer.agent.md": AGENTS[0],
        HERE / ".github" / "agents" / "enhancer-judge.agent.md": AGENTS[1],
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
