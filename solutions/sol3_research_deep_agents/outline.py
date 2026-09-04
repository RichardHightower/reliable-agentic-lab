"""Outline validation, hashing, and the plan-shaped view later phases read.

Python owns this. A model returns an Outline; this module decides whether it
is usable, writes the human-readable copy, and stamps the approved file.
Nothing downstream re-derives sections, questions, or figures from anything
but `outline.approved.json`.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone

# Prompt-side checklist, not a hard validator rule. The outliner is told this.
ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]{1,40}$")


def canonical(outline: dict) -> str:
    """Stable JSON for hashing and for the resume diff."""
    return json.dumps(outline, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(outline: dict) -> str:
    return hashlib.sha256(canonical(outline).encode("utf-8")).hexdigest()


def stamp(outline: dict, *, approved_by: str, approved_at: str | None = None) -> dict:
    """The file every later phase reads. The outline is nested so the hash
    covers the document and not the stamp."""
    return {
        "outline": outline,
        "approved_by": approved_by,
        "approved_at": approved_at
        or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sha256": digest(outline),
    }


def load_approved(payload: dict) -> dict:
    """Accept the stamped file, and a bare outline for tests that skip the stamp."""
    if "outline" in payload and isinstance(payload["outline"], dict):
        return payload["outline"]
    return payload


def _as_int(value) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    return None


def _cycle(ids: list[str], edges: dict[str, list[str]]) -> str | None:
    """Return one cycle if the depends_on graph has one."""
    visiting: set[str] = set()
    seen: set[str] = set()
    stack: list[str] = []

    def walk(node: str) -> str | None:
        if node in visiting:
            start = stack.index(node)
            return " -> ".join(stack[start:] + [node])
        if node in seen:
            return None
        visiting.add(node)
        stack.append(node)
        for nxt in edges.get(node, []):
            found = walk(nxt)
            if found:
                return found
        stack.pop()
        visiting.remove(node)
        seen.add(node)
        return None

    for sid in ids:
        found = walk(sid)
        if found:
            return found
    return None


def validate(outline: dict, *, word_target_total: int | None = None, corpus_keys: list[str] | None = None) -> list[str]:
    """Return human-readable errors. Empty means the outline is usable.

    The exact strings are the retry instruction handed back to the outliner.
    """
    errors: list[str] = []
    if not isinstance(outline, dict):
        return ["the outline must be an object, not a string or array"]

    sections = outline.get("sections")
    if not isinstance(sections, list) or not sections:
        return ["sections must be a non-empty array of objects, not strings"]

    for index, section in enumerate(sections):
        if not isinstance(section, dict):
            errors.append(
                f"sections[{index}] must be an object, not a string. "
                "SECTIONS MUST BE OBJECTS, NOT STRINGS."
            )
    if errors:
        return errors

    ids = [section.get("id") for section in sections]
    if any(not sid for sid in ids):
        errors.append("every section needs a non-empty id")
    seen: dict[str, int] = {}
    for index, sid in enumerate(ids):
        if not sid:
            continue
        if sid in seen:
            errors.append(f"section id {sid!r} is duplicated (sections {seen[sid]} and {index})")
        else:
            seen[sid] = index

    id_to_index = {sid: index for index, sid in enumerate(ids) if sid}
    edges: dict[str, list[str]] = {sid: [] for sid in id_to_index}
    for index, section in enumerate(sections):
        sid = section.get("id")
        deps = section.get("depends_on") or []
        if deps and not isinstance(deps, list):
            errors.append(f"section {sid!r} depends_on must be an array of earlier section ids")
            continue
        for dep in deps:
            if dep not in id_to_index:
                errors.append(f"section {sid!r} depends_on unknown id {dep!r}")
                continue
            if id_to_index[dep] >= index:
                errors.append(
                    f"section {sid!r} depends_on {dep!r} which is not an earlier section. "
                    "depends_on may only reference sections above this one."
                )
                continue
            edges[sid].append(dep)

    cycle = _cycle([sid for sid in ids if sid], edges)
    if cycle:
        errors.append(f"depends_on has a cycle: {cycle}")

    expected_total = _as_int(outline.get("word_target_total"))
    if word_target_total is not None:
        expected_total = word_target_total if expected_total is None else expected_total
    summed = 0
    for section in sections:
        target = _as_int(section.get("word_target"))
        if target is None:
            errors.append(f"section {section.get('id')!r} is missing a numeric word_target")
            continue
        summed += target

    if expected_total is None or expected_total <= 0:
        errors.append("word_target_total must be a positive integer")
    else:
        slack = 0.10 * expected_total
        if abs(summed - expected_total) > slack:
            errors.append(
                f"section word_targets sum to {summed}, which is more than ten percent "
                f"away from word_target_total {expected_total}. Rebalance the section "
                "word_targets so they sum to the paper total within 10%."
            )

    for section in sections:
        sid = section.get("id")
        heading = str(section.get("heading") or "").strip()
        objective = str(section.get("objective") or "").strip()
        abstract = str(section.get("abstract") or "").strip()
        if not objective:
            errors.append(
                f"section {sid!r} has no objective. Say what a reader knows after "
                "this section that they did not know before it."
            )
        elif _echoes(objective, heading):
            errors.append(
                f"section {sid!r} has an objective that restates its heading: "
                f"{objective!r}. Name the point the section makes, not its title."
            )
        if not abstract:
            errors.append(
                f"section {sid!r} has no abstract. Two or three sentences saying "
                "what this section argues."
            )
        questions = section.get("key_questions") or []
        if not isinstance(questions, list):
            errors.append(f"section {sid!r} key_questions must be an array of strings")
            questions = []
        questions = [q for q in questions if question_text(q)]
        if len(questions) < 2:
            errors.append(
                f"section {sid!r} has {len(questions)} key_questions; every section "
                "needs at least two."
            )
        figures = section.get("figures") or []
        if figures and not isinstance(figures, list):
            errors.append(f"section {sid!r} figures must be an array of objects")
            continue
        for figure in figures:
            if not isinstance(figure, dict):
                errors.append(f"section {sid!r} has a figure that is not an object")
                continue
            if figure.get("kind") == "chart" and not str(figure.get("data_needed") or "").strip():
                errors.append(
                    f"chart figure {figure.get('name')!r} in section {sid!r} has empty "
                    "data_needed. Name the table or series the chart will plot."
                )
        refs = section.get("corpus_refs") or []
        if refs and not isinstance(refs, list):
            errors.append(f"section {sid!r} corpus_refs must be an array of corpus keys")
            refs = []
        if corpus_keys is not None:
            allowed = set(corpus_keys)
            for ref in refs:
                if not isinstance(ref, str) or ref not in allowed:
                    errors.append(
                        f"section {sid!r} corpus_refs names unknown key {ref!r}. "
                        "Use keys from corpus/brain-pack.json."
                    )

    return errors


JUDGE_PROMPT_CHARS = 24000


def for_judge(drafted: dict, limit: int | None = None) -> str:
    """The outline as the judge should see it: parseable, and honest about cuts.

    A raw `json.dumps(...)[:8000]` cut a 9,114 character outline mid-key. The
    judge received malformed JSON ending in `"depends_on": [], "c`, saw 6 of 7
    sections, and reported the outline as truncated and incomplete. It was
    right, and the harness had done it. Two live runs escalated that way (#323).

    Drop whole sections from the end when a ceiling is unavoidable, and say how
    many went, so the judge knows what it did not see instead of inferring a
    gap that is not in the document.
    """
    # Read the module constant here, not as a default argument. A default is
    # bound once at definition, so a test that lowers the ceiling would change
    # nothing and pass for the wrong reason.
    limit = JUDGE_PROMPT_CHARS if limit is None else limit
    body = json.dumps(drafted, indent=2)
    if len(body) <= limit:
        return body

    sections = list(drafted.get("sections") or [])
    kept = list(sections)
    while len(kept) > 1:
        kept.pop()
        trial = dict(drafted, sections=kept)
        body = json.dumps(trial, indent=2)
        if len(body) <= limit:
            break
    withheld = len(sections) - len(kept)
    return (
        f"This outline has {len(sections)} sections. The last {withheld} are "
        f"withheld for length and are NOT missing from the paper. Grade the "
        f"{len(kept)} below, and do not fail completeness for the withheld "
        f"sections.\n{body}"
    )


def retry_note(errors: list[str]) -> str:
    return "The outline failed validation. Fix every item:\n" + "\n".join(
        f"- {item}" for item in errors
    )


def question_text(question) -> str:
    """A key question is a string or `{text, kind}`."""
    if isinstance(question, dict):
        return str(question.get("text") or "").strip()
    return str(question or "").strip()


def question_kind(question) -> str:
    if isinstance(question, dict):
        kind = str(question.get("kind") or "fact").strip().lower()
        return kind if kind in {"fact", "mechanism", "comparison", "data"} else "fact"
    return "fact"


def questions(outline: dict) -> list[dict]:
    """Flatten key_questions in outline order. The research phase iterates this."""
    out = []
    for section in outline.get("sections") or []:
        for index, question in enumerate(section.get("key_questions") or []):
            text = question_text(question)
            if not text:
                continue
            out.append(
                {
                    "id": f"{section['id']}-q{index + 1}",
                    "text": text,
                    "kind": question_kind(question),
                    "section": section["id"],
                }
            )
    return out


def diagrams(outline: dict) -> list[dict]:
    """kind: diagram only. Charts are a separate phase."""
    out = []
    for section in outline.get("sections") or []:
        for figure in section.get("figures") or []:
            if not isinstance(figure, dict):
                continue
            if figure.get("kind") != "diagram":
                continue
            out.append(
                {
                    "name": figure.get("name", ""),
                    "concept": figure.get("shows") or figure.get("concept") or "",
                    "section": section["id"],
                    "kind": "diagram",
                }
            )
    return out


def charts(outline: dict) -> list[dict]:
    out = []
    for section in outline.get("sections") or []:
        for figure in section.get("figures") or []:
            if isinstance(figure, dict) and figure.get("kind") == "chart":
                out.append({**figure, "section": section.get("id") or ""})
    return out


def plan_view(outline: dict) -> dict:
    """The shape `rkc.write_bundle` already understands.

    Built from the approved outline, never from a second planner pass.
    `goal` is the section objective under the older name.
    """
    return {
        "title": outline.get("title", ""),
        "abstract": outline.get("thesis", ""),
        "audience": outline.get("audience", ""),
        "thesis": outline.get("thesis", ""),
        "word_target_total": outline.get("word_target_total"),
        "sections": [
            {
                "id": section["id"],
                "heading": section.get("heading", ""),
                "goal": section.get("objective") or section.get("goal", ""),
                "objective": section.get("objective") or section.get("goal", ""),
                "abstract": section.get("abstract", ""),
                "claims_to_support": section.get("claims_to_support") or [],
                "word_target": section.get("word_target"),
                "key_questions": section.get("key_questions") or [],
            }
            for section in outline.get("sections") or []
        ],
        "questions": questions(outline),
        "diagrams": diagrams(outline),
    }


def to_markdown(outline: dict) -> str:
    """Readable copy for `--approve`. The JSON remains the source of truth."""
    lines = [
        f"# {outline.get('title') or 'Untitled outline'}",
        "",
        f"**Audience.** {outline.get('audience') or ''}".rstrip(),
        "",
        f"**Thesis.** {outline.get('thesis') or ''}".rstrip(),
        "",
        f"**Word target.** {outline.get('word_target_total') or ''}",
        "",
    ]
    for section in outline.get("sections") or []:
        lines += [
            f"## {section.get('id')}: {section.get('heading')}",
            "",
            f"**Objective.** {section.get('objective') or ''}",
            "",
            section.get("abstract") or "",
            "",
            f"**Word target.** {section.get('word_target') or ''}",
            "",
            "**Key questions**",
            "",
        ]
        for index, question in enumerate(section.get("key_questions") or [], start=1):
            lines.append(f"{index}. {question}")
        lines += ["", "**Claims to support**", ""]
        for claim in section.get("claims_to_support") or []:
            lines.append(f"- {claim}")
        lines += ["", "**Required evidence**", ""]
        for item in section.get("required_evidence") or []:
            lines.append(f"- {item}")
        figures = section.get("figures") or []
        lines += ["", "**Figures**", ""]
        if not figures:
            lines.append("None.")
        for figure in figures:
            extra = ""
            if figure.get("kind") == "chart" and figure.get("data_needed"):
                extra = f" Data needed: {figure['data_needed']}."
            lines.append(
                f"- `{figure.get('name')}` ({figure.get('kind')}): "
                f"{figure.get('shows') or ''}{extra}"
            )
        deps = section.get("depends_on") or []
        lines += ["", f"**Depends on.** {', '.join(deps) if deps else 'none'}", ""]
    lines += [
        "---",
        "",
        "This file is for reading. Edit `outline.json` to change the outline, "
        "then re-run with `--resume`. Python stamps `outline.approved.json` "
        "from the JSON, never from this markdown.",
        "",
    ]
    return "\n".join(lines)


SKIP_HEADINGS = {"abstract", "references", "summary", "bibliography"}


def _question_text(question) -> str:
    if isinstance(question, dict):
        return str(question.get("question") or question.get("text") or "").strip()
    return str(question or "").strip()


def _as_entry(item) -> dict:
    """One plan section, with the four fields this lift reads."""
    if not isinstance(item, dict):
        return {"heading": str(item or "").strip(), "objective": "", "abstract": "",
                "key_questions": []}
    return {
        "heading": str(item.get("heading") or "").strip(),
        "objective": str(item.get("objective") or "").strip(),
        "abstract": str(item.get("abstract") or "").strip(),
        "key_questions": list(item.get("key_questions") or []),
    }


def _echoes(objective: str, heading: str) -> bool:
    """True when the objective says nothing the heading did not already say.

    `Explain <heading>.` was what the old lift wrote for every section, and the
    plan judge called the result systematically mismatched. Stripping the filler
    words catches the same sentence however it is punctuated.
    """
    if not heading:
        return False
    words = re.sub(r"[^a-z0-9 ]+", " ", objective.lower())
    stripped = re.sub(
        r"^(this section |explain |describe |cover |discuss |introduce )+", "", words
    ).strip()
    return stripped == re.sub(r"[^a-z0-9 ]+", " ", heading.lower()).strip()


def outline_from_plan(plan: dict, *, word_target_total: int = 2000) -> dict:
    """Lift a Deep Agents plan.json into the outline schema.

    The planner writes each section's objective, abstract, and key questions,
    so this carries them through. It used to fill them from the heading, which
    produced `Explain <heading>.` for every section and assigned questions to
    headings by round robin. The live plan judge scored 0.35 three times with
    "Section headings and their key_questions/claims are systematically
    mismatched." The round robin was that complaint.

    A section that arrives as a plain string still parses, with empty fields.
    `validate` then names the missing field, which beats a crash on an old plan.
    """
    entries = [_as_entry(item) for item in (plan.get("sections") or [])]
    body = [entry for entry in entries if entry["heading"].lower() not in SKIP_HEADINGS]
    if not body:
        body = [{"heading": "The approach", "objective": "", "abstract": "", "key_questions": []}]
    figures = list(plan.get("diagrams") or [])
    questions = list(plan.get("questions") or [])
    per = max(80, int(word_target_total) // max(len(body), 1))
    leftover_figures = list(figures)
    checks = [
        item.get("check")
        for item in questions
        if isinstance(item, dict) and item.get("check")
    ]
    sections = []
    for index, entry in enumerate(body):
        heading = entry["heading"]
        sid = re.sub(r"[^a-z0-9]+", "-", heading.lower()).strip("-") or f"s{index + 1}"
        qs = [text for text in map(_question_text, entry["key_questions"]) if text]
        figs = []
        if leftover_figures:
            figure = leftover_figures.pop(0)
            figs.append(
                {
                    "name": figure.get("name") or sid,
                    "kind": "diagram",
                    "shows": figure.get("shows") or figure.get("concept") or "",
                }
            )
        sections.append(
            {
                "id": sid,
                "heading": heading,
                "objective": entry["objective"],
                "abstract": entry["abstract"],
                "key_questions": qs[:4],
                "claims_to_support": (checks[index : index + 1] or ["A structural claim holds."]),
                "required_evidence": ["a primary specification"],
                "word_target": per,
                "figures": figs,
                "depends_on": [],
                "corpus_refs": [],
            }
        )
    notes = plan.get("notes") or []
    thesis = notes[0] if notes and isinstance(notes[0], str) else (plan.get("title") or "A thesis.")
    return {
        "title": plan.get("title") or "Untitled",
        "audience": plan.get("audience") or "engineers",
        "thesis": thesis,
        "word_target_total": word_target_total,
        "sections": sections,
    }


def judge_signature(verdict: dict) -> tuple[str, ...]:
    """What failed, not how it was worded. Stall detection keys on this."""
    issues = verdict.get("blocking_issues") or []
    rules = sorted(
        {
            str(issue.get("rule") or "outline").strip()
            for issue in issues
            if isinstance(issue, dict)
        }
    )
    return tuple(rules) if rules else ("outline",)
