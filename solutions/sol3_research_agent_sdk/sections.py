"""Per-section research, verify, write, check, judge, ledger.

Python holds the loop. One approved section at a time, forward only. A
finished section's files are the skip key: `--resume` does not pay for it
again.

    run_section(run, section)  -> meta dict
    assemble_context(...)      -> (prompt, cuts)

The writer is the only role that writes. Findings, evidence packs, verdicts,
and the ledger are Python-written files.
"""

from __future__ import annotations

import json
from pathlib import Path

import checks
import citations
import gates
import outline as outlines
from turns import Escalate, TurnFailed

LIVE_SEARCHES_PER_QUESTION = 2
LIVE_SEARCHES_PER_SECTION = 8
SECTION_ATTEMPTS = 3

# Named slots, in priority order. Cut from the tail of a slot, never from a
# higher-priority slot, and log what went.
SLOT_BUDGETS = (
    ("register", 2500),
    ("outline", 8000),
    ("ledger", 4000),
    ("previous", 4000),
    ("findings", 8000),
    ("retry", 1500),
)

REGISTER = """Write like a specification, not like a blog post.
Lead with the finding. Mechanism, alternative and its cost, then the limit
of the evidence. Three to eight paragraphs per key question.
No second person. No metaphor. No em dash. Cite by number.
Do not invent a specific. Do not define a term the ledger already defines.
A claim's status changes how you word it and is never something to mention.
verified: state it. disputed: name the disagreement. unverified: qualitative
or drop. contradicted: not in your input.
"""


def question_list(section: dict) -> list[dict]:
    out = []
    for index, raw in enumerate(section.get("key_questions") or [], start=1):
        text = outlines.question_text(raw)
        if not text:
            continue
        out.append(
            {
                "id": f"{section['id']}-q{index}",
                "text": text,
                "kind": outlines.question_kind(raw),
            }
        )
    return out


def _cut(text: str, budget: int) -> tuple[str, int]:
    if len(text) <= budget:
        return text, 0
    return text[:budget].rsplit("\n", 1)[0] or text[:budget], len(text) - budget


def assemble_context(
    *,
    outline: dict,
    ledger: list,
    previous: str,
    findings: list,
    retry: str = "",
) -> tuple[dict[str, str], list[str]]:
    """Named slots with per-slot character budgets. Returns slots and cut log."""
    raw = {
        "register": REGISTER,
        "outline": json.dumps(outline, indent=2),
        "ledger": json.dumps(ledger, indent=2) if ledger else "(empty)",
        "previous": previous or "(none)",
        "findings": json.dumps(findings, indent=2),
        "retry": retry or "",
    }
    slots: dict[str, str] = {}
    cuts: list[str] = []
    for name, budget in SLOT_BUDGETS:
        kept, dropped = _cut(raw.get(name, ""), budget)
        slots[name] = kept
        if dropped:
            cuts.append(f"cut {name} by {dropped} chars (budget {budget})")
    return slots, cuts


def _finding_from_claim(claim: dict, section_id: str, question: str, index: int) -> dict:
    url = claim.get("source_url") or ""
    kind = "corpus" if (claim.get("origin") == "corpus" or str(url).startswith("brain:")) else "web"
    return {
        # The harness names every finding, never the model. A researcher that
        # supplies its own id for some claims and not others put two schemes in
        # one section, `f1` beside `why-prompting-does-not-scale-f14`. The
        # writer read the short form as the house style and abbreviated the
        # rest, and every abbreviated citation then failed `grounded`.
        "id": f"{section_id}-f{index}",
        "section_id": section_id,
        "answers_question": question,
        "claim": claim.get("text") or claim.get("claim") or "",
        "quote": claim.get("quote") or "",
        "source": {
            "kind": kind,
            "ref": claim.get("corpus_key") or url,
            "title": claim.get("title") or "",
            "url_or_path": url,
            "vendor": claim.get("vendor") or "",
            "tier": int(claim.get("tier") or (3 if kind == "corpus" else 1)),
        },
        "evidence_strength": float(claim.get("evidence_strength") or 0.5),
        "counterargument_to": claim.get("counterargument_to") or "",
        "numbers": claim.get("numbers") or [],
        "origin": "corpus" if kind == "corpus" else "web",
        "epistemic": claim.get("epistemic") or "",
    }


def findings_from_research(result: dict, section_id: str, question: str, start: int = 1) -> list[dict]:
    out = []
    for offset, claim in enumerate(result.get("claims") or [], start=start):
        out.append(_finding_from_claim(claim, section_id, question, offset))
    if not out and (result.get("answer") or result.get("findings")):
        for offset, item in enumerate(result.get("findings") or [], start=start):
            if isinstance(item, dict) and item.get("claim"):
                item = dict(item)
                item.setdefault("section_id", section_id)
                item.setdefault("answers_question", question)
                item["id"] = f"{section_id}-f{offset}"
                out.append(item)
    return out


def _claims_for_writer(
    findings: list[dict],
    verdicts: dict[str, dict],
    section_id: str,
    numbers: dict[str, int] | None = None,
) -> list[dict]:
    """The claims the writer may cite, each carrying its run-wide number.

    These numbers were 1..N per section, restarting every section, while the
    bibliography was numbered globally at assembly. Section two wrote `[1]`
    meaning its own first source and the paper's `[1]` was section one's.
    `numbers` is the run's registry, so the number in the prose and the number
    in the reference list come from one pass.

    `None` means the caller has no registry, which is the offline and unit-test
    path. The old local numbering stands in there.
    """
    usable = []
    number = 1
    for finding in findings:
        status = (verdicts.get(finding["id"]) or {}).get("state") or "unverified"
        if status == "contradicted":
            continue
        url = (finding.get("source") or {}).get("url_or_path") or ""
        cite = number if numbers is None else numbers.get(url, 0)
        usable.append(
            {
                "id": finding["id"],
                "text": finding.get("claim") or "",
                "source_url": url,
                "quote": finding.get("quote") or "",
                "question_id": finding.get("answers_question") or "",
                "section": section_id,
                "status": status,
                "number": cite,
            }
        )
        number += 1
    return usable


def _load_ledger(run) -> list:
    path = run.file("paper_ledger.json")
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(payload, list):
        return payload
    return list(payload.get("entries") or [])


def _save_ledger(run, entries: list) -> None:
    run.write_json("paper_ledger.json", {"entries": entries})


def _section_done(run, section_id: str) -> bool:
    body = run.file("sections") / f"{section_id}.md"
    findings = run.file(f"knowledge/{section_id}/findings.json")
    if not body.exists() or not findings.exists():
        return False
    for entry in _load_ledger(run):
        if entry.get("section_id") == section_id:
            return True
    return False


def _evidence_blob(run, section_id: str, findings: list) -> str:
    parts = [f.get("quote") or "" for f in findings]
    parts += [f.get("claim") or "" for f in findings]
    evid_dir = run.file(f"knowledge/{section_id}/evidence")
    if evid_dir.is_dir():
        for path in sorted(evid_dir.glob("*.md")):
            try:
                parts.append(path.read_text(encoding="utf-8"))
            except OSError:
                continue
    pack = run.file("corpus/brain-pack.md")
    if pack.exists():
        try:
            parts.append(pack.read_text(encoding="utf-8"))
        except OSError:
            pass
    return "\n".join(parts)


def _previous_section_text(run, section: dict) -> str:
    depends = section.get("depends_on") or []
    if not depends:
        # Forward-only: the previous section in outline order.
        approved = None
        try:
            import paper as paper_mod  # noqa: PLC0415

            approved = paper_mod.approved_outline(run)
        except Exception:
            return ""
        ids = [item["id"] for item in approved.get("sections") or []]
        if section["id"] in ids:
            idx = ids.index(section["id"])
            if idx > 0:
                depends = [ids[idx - 1]]
    for sid in depends:
        path = run.file("sections") / f"{sid}.md"
        if path.exists():
            return path.read_text(encoding="utf-8")
    return ""


def _write_findings(run, section_id: str, payload: dict) -> None:
    dest = run.file(f"knowledge/{section_id}")
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / "findings.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def run_section(run, section: dict) -> dict:
    """Steps 3a to 3h for one approved section."""
    sid = section["id"]
    if _section_done(run, sid):
        run.log(f"    section {sid} already done")
        return {"section": sid, "skipped": True}

    questions = question_list(section)
    knowledge = run.file(f"knowledge/{sid}")
    knowledge.mkdir(parents=True, exist_ok=True)

    # 3b research
    findings: list[dict] = []
    queries: list[str] = []
    if hasattr(run.turns, "research_section"):
        result = run.turns.research_section(section, questions, note="")
        findings = list(result.get("findings") or [])
        queries = list(result.get("queries") or [])
        if not findings:
            for question in questions:
                raw = run.turns.research(question["text"], "")
                findings.extend(
                    findings_from_research(raw, sid, question["text"], start=len(findings) + 1)
                )
                queries.append(question["text"])
    else:
        for question in questions:
            raw = run.turns.research(question["text"], "")
            findings.extend(
                findings_from_research(raw, sid, question["text"], start=len(findings) + 1)
            )
            queries.append(question["text"])

    # 3c gap pass
    gaps = []
    answered = {f.get("answers_question") for f in findings if f.get("claim")}
    for question in questions:
        if question["text"] in answered:
            continue
        try:
            if hasattr(run.turns, "gap_research"):
                raw = run.turns.gap_research(section, question, queries, note="")
            else:
                raw = run.turns.research(question["text"], "gap: restated, previous queries listed")
        except (TurnFailed, Escalate):
            raw = {"claims": [], "findings": []}
        extra = findings_from_research(raw, sid, question["text"], start=len(findings) + 1)
        if extra:
            findings.extend(extra)
        else:
            gaps.append({"question": question["text"], "queries": list(queries)})
        queries.append(question["text"])

    payload = {
        "section_id": sid,
        "findings": findings,
        "coverage_gaps": gaps,
        "queries": queries,
    }
    _write_findings(run, sid, payload)

    # 3d verify
    verdicts: dict[str, dict] = {}
    shaky = sorted(findings, key=lambda f: float(f.get("evidence_strength") or 0.5))
    cap = run.max_claims
    checked = 0
    for finding in shaky:
        epistemic = (finding.get("epistemic") or "").lower()
        origin = finding.get("origin") or (finding.get("source") or {}).get("kind")
        if origin == "corpus" and epistemic == "corroborated":
            verdicts[finding["id"]] = {
                "finding_id": finding["id"],
                "state": "verified",
                "queries_used": [],
                "note": "cross_checked: corpus",
            }
            continue
        if checked >= cap or run.exhausted():
            verdicts[finding["id"]] = {
                "finding_id": finding["id"],
                "state": "unverified",
                "queries_used": [],
                "note": "past verification cap" if not run.exhausted() else "cost budget spent",
            }
            continue
        try:
            verdict = run.turns.verify(finding.get("claim") or "")
        except (TurnFailed, Escalate) as exc:
            verdict = {"verdict": "unclear", "source_url": "", "excerpt": f"unavailable: {exc}"}
        checked += 1
        if verdict.get("verdict") == "supports":
            state = "verified"
        elif verdict.get("verdict") == "contradicts":
            state = "disputed" if finding.get("quote") else "contradicted"
        else:
            state = "unverified"
        queries_used = verdict.get("queries_used") or []
        verdicts[finding["id"]] = {
            "finding_id": finding["id"],
            "state": state,
            "queries_used": queries_used,
            "note": verdict.get("excerpt") or "",
        }
    (knowledge / "verdicts.json").write_text(
        json.dumps({"verdicts": list(verdicts.values())}, indent=2) + "\n",
        encoding="utf-8",
    )

    # 3e–3g write, check, judge, with gates.decide on the section signature
    # Register every source this section will cite before the writer runs, so
    # the number it is told to use is the number the bibliography will give.
    numbers = citations.register(
        run.work_dir,
        [(f.get("source") or {}).get("url_or_path") or "" for f in findings],
    )
    bound = _claims_for_writer(findings, verdicts, sid, numbers)
    figures = []
    diagrams_path = run.file("diagrams.json")
    if diagrams_path.exists():
        try:
            figures = [
                fig
                for fig in json.loads(diagrams_path.read_text(encoding="utf-8")).get("figures")
                or []
                if fig.get("section") == sid and fig.get("path")
            ]
        except (OSError, json.JSONDecodeError):
            figures = []
    relative = f"sections/{sid}.md"
    out = run.file("sections")
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{sid}.md"

    previous = _previous_section_text(run, section)
    ledger = _load_ledger(run)
    approved = {"title": "", "sections": [section]}
    try:
        import paper as paper_mod  # noqa: PLC0415

        full = paper_mod.approved_outline(run)
        # The paper's header, and this section only. Handing the writer every
        # section's full spec overflowed the 8000 character slot by 24489
        # characters, so `_cut` dropped 75% of the outline mid-structure and
        # the section stage escalated three attempts running (#330). A writer
        # working on one section does not need the other four specs; it gets
        # their prose through the `previous` slot.
        approved = {
            **{key: value for key, value in full.items() if key != "sections"},
            "sections": [section],
        }
    except Exception:
        pass

    from paper import _section_instruction  # noqa: PLC0415

    previous_sig: tuple[str, ...] | None = None
    last_score = None
    last_verdict = {"passed": True, "failed_rows": [], "notes": []}
    written_from_message = 0
    for iteration in range(1, SECTION_ATTEMPTS + 1):
        spent = run.exhausted()
        if spent:
            raise Escalate(f"{sid}: {spent}")
        # What the previous attempt failed. It steers this attempt's writer and
        # editor. It must never reach the judge, which grades the body in front
        # of it, not the one before it.
        retry_note = ""
        if last_score is not None and not last_score.passed:
            retry_note = last_score.report()
        if last_verdict.get("failed_rows"):
            retry_note = (retry_note + "\n" + " ".join(last_verdict.get("notes") or [])).strip()
        slots, cuts = assemble_context(
            outline=approved,
            ledger=ledger,
            previous=previous,
            findings=bound,
            retry=retry_note,
        )
        for line in cuts:
            run.log(f"    {sid} context: {line}")
        instruction = _section_instruction(section, retry_note)
        if last_verdict.get("failed_rows"):
            instruction = (
                f"{instruction}\n\nEdit mode. Fix only these rows: "
                f"{', '.join(last_verdict['failed_rows'])}. Add no facts."
            )
        existing = ""
        if path.exists():
            existing = path.read_text(encoding="utf-8")
        # The writer holds `Write` scoped to this path and is told to use it,
        # so the old file goes before the turn runs. `existing` is the copy
        # that survives a turn which raises or answers with nothing.
        path.unlink(missing_ok=True)
        # Edit whenever a draft exists. The old condition also required the
        # judge to have named a row, so a section that failed only a Python row
        # was rewritten from nothing. A full rewrite of a 1900-word section
        # returns another 1900-word section. Rewrite is attempt one only.
        #
        # `last_score.report()` carries the deterministic rows. `length` never
        # reaches `failed_rows`, so without it the editor was told to fix
        # `objective_met` and never heard "1186 words, ceiling 1000".
        try:
            if hasattr(run.turns, "edit_section") and existing:
                body = run.turns.edit_section(
                    section,
                    existing,
                    last_verdict,
                    relative,
                    note=last_score.report() if last_score else "",
                    claims=bound,
                )
            else:
                body = run.turns.write(section, bound, figures, instruction, relative)
        except TurnFailed:
            # A turn that failed costs the attempt, never the draft.
            run.log(f"    {sid}: the writer turn failed. Keeping the last draft.")
            body = ""
        except Escalate:
            # The runtime hit its own ceiling, so the run stops here. Put the
            # draft back first: the file was unlinked before the turn, and the
            # in-memory copy dies with this frame. A resume would otherwise
            # re-research a section that was already written.
            if existing:
                path.write_text(existing, encoding="utf-8")
            raise
        if not path.exists() or not path.read_text(encoding="utf-8").strip():
            if (body or "").strip():
                path.write_text(body.rstrip() + "\n", encoding="utf-8")
                written_from_message += 1
            elif existing:
                # An attempt that produced nothing costs the attempt, never the
                # draft. The next pass edits the section that got this far.
                run.log(f"    {sid}: the edit produced nothing. Keeping the last draft.")
                path.write_text(existing, encoding="utf-8")
            else:
                # Attempt one produced nothing and there is no draft to keep.
                # Leave the file absent rather than writing a blank one, so the
                # next attempt writes instead of editing emptiness, and
                # `_section_done` does not read this as finished work.
                run.log(f"    {sid}: the writer produced nothing on the first attempt.")
        body = path.read_text(encoding="utf-8") if path.exists() else ""
        last_score = checks.section_check(
            body,
            section=section,
            findings=bound,
            evidence=_evidence_blob(run, sid, findings),
            word_target=int(section.get("word_target") or 0),
            figures_given=figures,
        )
        (knowledge / "section-check.json").write_text(
            json.dumps(last_score.to_dict(), indent=2) + "\n", encoding="utf-8"
        )
        check_failed = bool(last_score.signature()) if run.enforce_research_policy else False
        # Python first, model second, and never re-litigate a row Python
        # decided. The outline gate already holds this doctrine. Here the judge
        # ran even when the deterministic check had already failed, which spent
        # a turn grading a rejected section and then fed its rows to the editor
        # in place of the row that actually blocked the section.
        if hasattr(run.turns, "judge_section") and run.enforce_research_policy and not check_failed:
            # The current report, never `retry_note`. A section whose `length`
            # row was just repaired reached the judge beside `FAIL length`, and
            # the judge was told the artifact in front of it was broken in a
            # way it no longer was.
            judge_note = last_score.report() if last_score else ""
            try:
                last_verdict = run.turns.judge_section(section, body, findings, note=judge_note)
            except (TurnFailed, Escalate):
                last_verdict = {
                    "passed": False,
                    "failed_rows": ["judge"],
                    "notes": ["section judge failed"],
                }
        else:
            # Not run is not the same as agreed. `gates.decide` already draws
            # this line for `judge_done`. A reader of `section-verdict.json`
            # could not tell a judge that passed the section from a judge that
            # never saw it. `passed` stays true so the deterministic rows alone
            # decide the gate, and `state` says why.
            last_verdict = {
                "passed": True,
                "failed_rows": [],
                "notes": [],
                "state": "not_run",
                "reason": (
                    "the deterministic check failed, so the judge was not spent"
                    if check_failed
                    else "the research policy is off for this run"
                ),
            }
        (knowledge / "section-verdict.json").write_text(
            json.dumps(last_verdict, indent=2) + "\n", encoding="utf-8"
        )
        passed = (not check_failed) and bool(last_verdict.get("passed", True))
        signature = tuple(last_score.signature()) + tuple(last_verdict.get("failed_rows") or ())
        decision = gates.decide(
            passed=passed,
            iteration=iteration,
            budget=SECTION_ATTEMPTS,
            signature=signature,
            previous_signature=previous_sig,
            usd_left=0.0 if run.exhausted() else 1.0,
        )
        if decision.stop:
            if passed:
                break
            raise Escalate(f"{sid}: {decision.reason}")
        previous_sig = signature

    # 3h ledger
    try:
        if hasattr(run.turns, "ledger_turn"):
            entry = run.turns.ledger_turn(section, path.read_text(encoding="utf-8"))
        else:
            entry = {
                "section_id": sid,
                "heading": section.get("heading") or "",
                "claims": [{"claim": c["text"], "ref": str(c.get("number") or ""), "confidence": 0.5} for c in bound],
                "numbers": [],
                "decisions": [],
                "terms_defined": [],
                "open_questions": [g["question"] for g in gaps],
                "forward_refs": [],
            }
    except (TurnFailed, Escalate):
        entry = {
            "section_id": sid,
            "heading": section.get("heading") or "",
            "claims": [],
            "numbers": [],
            "decisions": [],
            "terms_defined": [],
            "open_questions": [g["question"] for g in gaps],
            "forward_refs": [],
        }
    entry["section_id"] = sid
    entries = [item for item in _load_ledger(run) if item.get("section_id") != sid]
    entries.append(entry)
    _save_ledger(run, entries)
    return {
        "section": sid,
        "findings": len(findings),
        "gaps": len(gaps),
        "from_message": written_from_message,
        "check": list(last_score.signature()) if last_score else [],
    }
