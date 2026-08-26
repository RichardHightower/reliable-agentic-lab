"""Reading a ticket and its acceptance criteria.

A ticket is markdown with optional front matter. The criteria are the bullets
under a `## Success criteria` or `## Acceptance criteria` heading.

Criteria get ids so a step and a rubric row can point at one. When the ticket
writes its own ids, those win.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

HEADING = re.compile(r"^##\s+(success|acceptance)\s+criteria\s*$", re.I)
BULLET = re.compile(r"^\s*[-*]\s+(.*)$")
EXPLICIT_ID = re.compile(r"^\(?(AC-\d+)\)?[:.\s]\s*(.*)$", re.I)
FRONT_MATTER = re.compile(r"^---\n(.*?)\n---\n", re.S)


@dataclass
class Criterion:
    id: str
    text: str


@dataclass
class Ticket:
    id: str
    title: str = ""
    body: str = ""
    state: str = "draft"
    criteria: list[Criterion] = field(default_factory=list)
    path: Path | None = None

    @property
    def criterion_ids(self) -> list[str]:
        return [c.id for c in self.criteria]

    @property
    def ready(self) -> bool:
        return self.state == "ready" or bool(self.criteria)

    def for_prompt(self) -> str:
        lines = [f"# {self.id}: {self.title}", "", self.body.strip()]
        if self.criteria:
            lines += ["", "## Acceptance criteria", ""]
            lines += [f"- ({c.id}) {c.text}" for c in self.criteria]
        return "\n".join(lines)


def parse(text: str, *, ticket_id: str = "") -> Ticket:
    meta: dict[str, str] = {}
    match = FRONT_MATTER.match(text)
    if match:
        for line in match.group(1).splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                meta[key.strip()] = value.strip()
        text = text[match.end() :]

    title = ""
    for line in text.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            break

    criteria: list[Criterion] = []
    collecting = False
    for line in text.splitlines():
        if line.startswith("## "):
            collecting = bool(HEADING.match(line))
            continue
        if not collecting:
            continue
        bullet = BULLET.match(line)
        if not bullet:
            continue
        raw = bullet.group(1).strip()
        explicit = EXPLICIT_ID.match(raw)
        if explicit:
            criteria.append(Criterion(explicit.group(1).upper(), explicit.group(2).strip()))
        else:
            criteria.append(Criterion(f"AC-{len(criteria) + 1}", raw))

    return Ticket(
        id=meta.get("id", ticket_id),
        title=title,
        body=text.strip(),
        state=meta.get("state", "ready" if criteria else "draft"),
        criteria=criteria,
    )


def load(repo: Path, ticket_id: str, folder: str = "tickets") -> Ticket:
    """Find a ticket by id. Prefers a `.ready.md` file when one exists."""
    root = Path(repo) / folder
    if not root.is_dir():
        raise FileNotFoundError(f"no {folder}/ directory in {repo}")
    ready = sorted(root.glob(f"{ticket_id}*.ready.md"))
    plain = sorted(p for p in root.glob(f"{ticket_id}*.md") if not p.name.endswith(".ready.md"))
    for candidate in ready + plain:
        ticket = parse(candidate.read_text(encoding="utf-8"), ticket_id=ticket_id)
        ticket.path = candidate
        return ticket
    raise FileNotFoundError(f"no ticket {ticket_id} in {root}")
