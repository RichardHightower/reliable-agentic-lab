"""Outline validation, hashing, and the plan-shaped view later phases read.

Python owns this. A model returns an Outline; this module decides whether it
is usable, writes the human-readable copy, and stamps the approved file.
Nothing downstream re-derives sections, questions, or figures from anything
but `outline.approved.json`.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import re
from datetime import datetime, timezone

import source_policy

# Prompt-side checklist, not a hard validator rule. The outliner is told this.
ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]{1,40}$")

# P4, the last prose section is a next step, not a restated conclusion. "Next"
# is in the list because the house style's own recommended heading for this
# section is literally "Next step". `require_next_step` gates the rule below,
# so the dozens of existing outline fixtures that end on an arbitrary heading
# keep validating with no changes.
NEXT_STEP_VERBS = ("Next", "Evaluate", "Run", "Compare", "Try", "Measure", "Adopt", "Pilot")


def is_bare_conclusion(heading: str) -> bool:
    """A last section headed exactly `Conclusion`, which only restates the
    abstract and is banned as the paper's closing prose section."""
    return str(heading or "").strip().lower() == "conclusion"


def starts_with_next_step_verb(heading: str) -> bool:
    """The heading's first word is a next-step verb, case insensitive."""
    first = re.match(r"[A-Za-z]+", str(heading or "").strip())
    return bool(first) and first.group(0).lower() in {verb.lower() for verb in NEXT_STEP_VERBS}


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


def validate(
    outline: dict,
    *,
    word_target_total: int | None = None,
    corpus_keys: list[str] | None = None,
    require_next_step: bool = False,
    require_evidence_requirements: bool = False,
    require_introduction: bool = False,
) -> list[str]:
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

    # #538. The plan's frozen heading order is Front matter, Abstract,
    # Introduction, Methods, Evidence summary, body sections, Conclusion,
    # Next step, Glossary, References. Abstract, Methods, Evidence summary,
    # Conclusion, Glossary, and References are Python's own, never an
    # outline section in this port; Introduction is the one structural
    # heading the outliner still has to draft, and position matters as much
    # as presence: it has to be first, the same as Deep Agents'
    # `stages.normalize_plan` puts it right after its own Abstract section.
    # Copied, not imported, per the house rule against a shared loop
    # package. Gated the same way `require_next_step` is, so the many
    # single-section outline stubs across this test suite keep validating
    # with no changes.
    if require_introduction:
        heading = str(sections[0].get("heading") or "").strip()
        if heading.lower() != "introduction":
            errors.append(
                f"the first section is headed {heading!r}, not 'Introduction'. "
                "The frozen heading order puts Introduction first, right after "
                "the Abstract. Head the first section 'Introduction'."
            )

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
        if require_evidence_requirements:
            for q_index, raw_question in enumerate(questions, start=1):
                problem = _evidence_requirements_problem(raw_question)
                if problem:
                    errors.append(
                        f"section {sid!r} question {q_index} ({question_text(raw_question)!r}) {problem}"
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
            errors.extend(_check_refs(section, sid, refs, corpus_keys))

    if require_next_step:
        heading = str(sections[-1].get("heading") or "").strip()
        if is_bare_conclusion(heading):
            errors.append(
                f"the last section is headed {heading!r}, a bare Conclusion that "
                "only restates the abstract. Head it with a next-step verb "
                "instead, for example 'Evaluate X on a live ticket' or 'Next step'."
            )
        elif not starts_with_next_step_verb(heading):
            errors.append(
                f"the last section is headed {heading!r}. The paper's last prose "
                "section must tell a colleague what to do next, headed with a "
                f"next-step verb such as {', '.join(NEXT_STEP_VERBS[1:4])}, for "
                "example 'Evaluate X on a live ticket' or 'Next step'."
            )

    return errors


def resolve_ref(ref: str, corpus_keys: list[str]) -> tuple[str | None, list[str]]:
    """One corpus reference, resolved against the pack keys.

    Returns the full key and the candidates that matched. A pack key is
    `knowledge:claim.<subject>.<ULID>` and a model writes the bare ULID, so an
    exact-match-only check rejected 21 references that were all real keys in
    suffix form. `corpus.resolve` already accepts a claim id suffix, so this
    follows a rule the port had.

    A suffix only counts on a segment boundary. Matching anywhere in the string
    would let a short id collide with the middle of an unrelated ULID.
    """
    if ref in corpus_keys:
        return ref, [ref]
    matches = [key for key in corpus_keys if key.endswith((f".{ref}", f":{ref}"))]
    if len(matches) == 1:
        return matches[0], matches
    return None, matches


def _check_refs(section: dict, sid, refs: list, corpus_keys: list[str]) -> list[str]:
    """Resolve every reference in place, and report the ones that will not."""
    errors: list[str] = []
    resolved: list = []
    for ref in refs:
        if not isinstance(ref, str):
            errors.append(
                f"section {sid!r} corpus_refs names unknown key {ref!r}. "
                "Use keys from corpus/brain-pack.json."
            )
            resolved.append(ref)
            continue
        full, candidates = resolve_ref(ref, corpus_keys)
        if full is not None:
            resolved.append(full)
            continue
        if len(candidates) > 1:
            errors.append(
                f"section {sid!r} corpus_refs names {ref!r}, which matches "
                f"{len(candidates)} keys: {', '.join(sorted(candidates))}. "
                "Use the full key."
            )
        else:
            near = difflib.get_close_matches(ref, corpus_keys, n=2, cutoff=0.5)
            hint = (
                f" The closest key in the pack is {near[0]!r}."
                if near
                else " The pack has no key like it."
            )
            errors.append(
                f"section {sid!r} corpus_refs names unknown key {ref!r}. Keys are "
                f"`knowledge:claim.<subject>.<ULID>`, from corpus/brain-pack.json."
                f"{hint}"
            )
        resolved.append(ref)
    if resolved != refs:
        section["corpus_refs"] = resolved
    return errors


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


def question_evidence_requirements(question) -> dict:
    """A key question's `evidence_requirements` block, or `{}`.

    A bare string question -- every pre-#475 fixture, and an older outline
    replayed through `--resume` -- carries none. #475
    """
    if isinstance(question, dict):
        reqs = question.get("evidence_requirements")
        return reqs if isinstance(reqs, dict) else {}
    return {}


def _evidence_requirements_problem(question) -> str | None:
    """What is wrong with a question's `evidence_requirements` block, or
    `None`. #475

    Checked only when `validate` is asked to enforce it: an older plan or
    outline that carries no block at all still parses here, it just names
    the missing field, the same as every other shape check in this module.
    """
    reqs = question_evidence_requirements(question)
    if not reqs:
        return "is missing evidence_requirements (study_types, min_count, recency_years, populations)"
    study_types = reqs.get("study_types")
    if not isinstance(study_types, list) or not study_types:
        return "evidence_requirements needs a non-empty study_types list"
    unknown = [t for t in study_types if t not in source_policy.STUDY_TYPES]
    if unknown:
        return f"evidence_requirements study_types names unknown type(s) {unknown}"
    min_count = _as_int(reqs.get("min_count"))
    if min_count is None or min_count < 1:
        return "evidence_requirements needs a positive integer min_count"
    recency_years = _as_int(reqs.get("recency_years"))
    if recency_years is None or recency_years < 0:
        return "evidence_requirements needs a non-negative integer recency_years"
    if not isinstance(reqs.get("populations"), list):
        return "evidence_requirements needs populations as an array of strings"
    return None


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
            if figure.get("kind") == "chart":
                out.append({**figure, "section": section["id"]})
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
            lines.append(f"{index}. {question_text(question)}")
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
