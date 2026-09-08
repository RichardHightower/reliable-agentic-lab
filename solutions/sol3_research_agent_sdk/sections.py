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
import os
import re
from pathlib import Path

import checks
import citations
import corpus
import gates
import locate
import metadata
import outline as outlines
import rkc
import source_policy
from turns import Escalate, TurnFailed

LIVE_SEARCHES_PER_QUESTION = 2
LIVE_SEARCHES_PER_SECTION = 8
# One locator answer per source, for the whole run. Two sections citing the
# same paper pay for one turn.
LOCATED_FILE = "knowledge/located.json"
# Per section, beside findings.json: what the locator could not place, and why.
UNRESOLVED_FILE = "unresolved.json"
# The attempts one section gets, covering the first draft, every deterministic
# repair, and every judge repair from one budget. Three was silently the whole
# story: `--max-iterations` drives the whole-paper cycle in `paper.py`, not
# this loop, so a run that raised it changed nothing here.
#
# A live section spent attempt one on the draft, attempt two on the Python
# rows, and had one left when the judge finally named `evidence_matches` and
# `voice`. The outline gate gets fourteen rounds by comparison and converges.
# The default stays 3, so a run changes nothing unless it opts in.
def _attempts(raw: str) -> int:
    """The attempt budget, refused rather than silently useless.

    `range(1, 0 + 1)` is empty, so a zero or negative budget skipped the write
    loop entirely. `last_verdict` then stayed at its optimistic default, the
    ledger step still ran, and a section nobody wrote or checked was stamped
    as finished work. A resume with a retained draft made that permanent.
    """
    try:
        value = int(raw)
    except ValueError:
        raise ValueError(
            f"SOL3_SECTION_ATTEMPTS must be a positive integer, not {raw!r}"
        ) from None
    if value < 1:
        raise ValueError(
            f"SOL3_SECTION_ATTEMPTS must be at least 1, not {value}. A budget of "
            "zero writes no section and stamps it anyway."
        )
    return value


SECTION_ATTEMPTS = _attempts(os.environ.get("SOL3_SECTION_ATTEMPTS", "3"))

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
                # #475. `{}` for a bare-string question, an older outline, or
                # one this test built directly: the run pass below treats an
                # empty block as nothing required, the same as `checks
                # .evidence_requirements_met` does.
                "evidence_requirements": outlines.question_evidence_requirements(raw),
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
        # Population, design, and sample size, when the model reported one.
        # Unused until #478's study table; carried here only so it survives
        # to `claims.json`. #471
        "study": claim.get("study") or {},
    }


def enrich_source_metadata(findings: list[dict], run) -> None:
    """Replace each web finding's title with the record's, in place. #470

    One call, over every finding a section produced, whichever research path
    built it: the per-question `research()` loop through
    `findings_from_research`, the base `Turns.research_section` default (which
    calls that same function), or the live `SdkTurns.research_section`, which
    hands back the identical `_SOURCE_SCHEMA` shape straight from the model.
    A single choke point here, after every path has converged on one finding
    shape, beats fetching inside each path separately and disagreeing about
    which title is "the model's" once a run enriches the same finding twice.

    `run` is `None` in every test and call site that predates this ticket,
    which is a no-op: the model's title stands exactly as before. The same
    holds for a `run.turns` that declares no `backend` at all, which is every
    hand-built test double in this suite that is not modelling the research
    backend. Treating "no backend concept" as "live, go fetch" would send a
    real DNS query for every `https://example.invalid/...` those tests
    construct.

    Only a `turns` that actually holds a `backend` attribute, fixture or
    live, is enriched. The fetch is cached per work directory
    (`metadata.cached_fetch`), so a source two sections cite, or a resumed
    run reloading a stamped section, pays for it once.
    """
    if run is None or not hasattr(getattr(run, "turns", None), "backend"):
        return
    backend = run.turns.backend
    for finding in findings:
        source = finding.get("source") or {}
        url = str(source.get("url_or_path") or "")
        # Not `kind == "web"`: `locate_cabinet_findings` relabels a matched
        # cabinet source `kind = "corpus"` even once it carries a real public
        # URL, and that source is just as fetchable as one the researcher
        # found directly. The scheme is the actual gate: a corpus key or a
        # `brain:` reference is never `http(s)://`, and `metadata.fetch_record`
        # refuses anything else anyway, this check only saves the call.
        if not url.lower().startswith(("http://", "https://")):
            continue
        fetched = metadata.cached_fetch(
            run.work_dir, url, backend, model_title=source.get("title") or ""
        )
        source["title"] = fetched.get("title") or source.get("title") or ""
        source["authors"] = fetched.get("authors") or []
        source["year"] = fetched.get("year") or ""
        source["venue"] = fetched.get("venue") or ""
        source["note"] = fetched.get("note") or ""
        # The abstract or page text the fetch carried. #471's `attributed()`
        # reads this, never the researcher's own quote.
        source["text"] = fetched.get("text") or ""
        # A dict lookup on the record's own publication type, never the
        # model's opinion. Named `evidence_tier`, not `tier`: this schema
        # already carries a numeric `tier` (a corpus-vs-web citation weight,
        # `_finding_from_claim` above), and the two are unrelated. #473
        source["evidence_tier"] = source_policy.tier_for(fetched)
        finding["source"] = source


# #471: the claim's own quote, or all of its numbers, must appear in the text
# `enrich_source_metadata` just fetched for the source it names. Lives here,
# not in `paper.py`: `run_section` is the path a real run executes, and
# `paper.verify` is dead code no `LINEAR` or `CYCLE` stage calls.
_NUMBER = re.compile(r"\d[\d,.]*\d|\d")


def _numbers(text: str) -> set[str]:
    return {token.replace(",", "") for token in _NUMBER.findall(text or "")}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def attributed(finding: dict, source_text: str) -> bool:
    """Does the text fetched for a finding's own cited source back it?

    The finding's own `quote` (the researcher's excerpt) must appear in
    `source_text`, or every one of the claim's numbers must -- one shared
    number out of several is not enough: a source that only says "a 12 week
    study" does not back "creatine adds 1.2 kg over 12 weeks" merely because
    12 appears in both. Neither a quote nor a number is not a failure: a
    purely qualitative claim carries nothing this cheap, model-free check
    can contradict, and dropping it here would invent a mismatch that was
    never checked. #471
    """
    quote = str(finding.get("quote") or "").strip()
    numbers = _numbers(finding.get("claim") or "")
    if not quote and not numbers:
        return True
    normalized_source = _normalize(source_text)
    if quote and _normalize(quote) in normalized_source:
        return True
    return bool(numbers) and numbers <= _numbers(source_text)


def _flatten_for_grading(findings: list[dict]) -> list[dict]:
    """Raw findings, reduced to the `{tier, year, text}` shape
    `checks.evidence_requirements_met` grades. #475"""
    flattened = []
    for finding in findings:
        source = finding.get("source") or {}
        flattened.append(
            {
                "tier": source.get("evidence_tier") or "",
                "year": source.get("year") or "",
                "text": f"{finding.get('claim') or ''} {finding.get('quote') or ''}",
            }
        )
    return flattened


def attribute_findings(run, findings: list[dict], sid: str) -> list[dict]:
    """Drop a finding whose own cited source does not back it. #471

    Python only, no model call, so it runs over every finding here,
    unconditionally, before `run.max_claims` caps the model verify turn
    below. Gated the same way `enrich_source_metadata` is: a `run.turns`
    with no `backend` attribute at all (every pre-#471 test double) is
    untouched, so old behaviour is unchanged byte for byte.
    """
    if not hasattr(getattr(run, "turns", None), "backend"):
        return findings
    kept: list[dict] = []
    dropped: list[str] = []
    for finding in findings:
        source = finding.get("source") or {}
        source_text = str(source.get("text") or "")
        if source_text and not attributed(finding, source_text):
            dropped.append(finding.get("claim") or finding.get("id") or "")
            continue
        if not source_text:
            note = "unattributed: attribution not checked"
            source["note"] = f"{source['note']}; {note}" if source.get("note") else note
            finding["source"] = source
        kept.append(finding)
    if dropped:
        run.log(f"    {sid} attribution: dropped {len(dropped)} claim(s) the cited source does not say: {dropped}")
    return kept


# #473. A preprint's number is the least trustworthy citation in the paper; a
# systematic review's is closest to a primary trial's own. Lower sorts first,
# so a run past `--max-follow` spends its turns on the shakiest claims.
_FOLLOW_ORDER = {
    "preprint_or_compilation": 0,
    "narrative_review": 1,
    "meta_analysis_or_systematic_review": 2,
}


def _follow_candidates(findings: list[dict]) -> list[dict]:
    """Numeric findings bound only to a review, a preprint, or a compilation."""
    candidates = [
        finding
        for finding in findings
        if _numbers(finding.get("claim") or "")
        and (finding.get("source") or {}).get("evidence_tier") in source_policy.SECONDARY_TIERS
    ]
    candidates.sort(
        key=lambda f: (
            _FOLLOW_ORDER.get((f.get("source") or {}).get("evidence_tier"), 9),
            float(f.get("evidence_strength") or 0.5),
        )
    )
    return candidates


def _apply_follow_result(run, finding: dict, result: dict) -> bool:
    """Rebind a finding to the primary a follow turn found, or mark it secondary.

    A hit only counts when the found source's own tier is not itself
    secondary: the same review answering twice, or a different review, must
    not clear the caveat (#473 item 2). A hit whose fetched text contradicts
    the claim is treated the same as a miss: a primary study's own URL is
    not a licence to skip the check #471 already runs on every other
    binding.

    The original review survives under `finding["via"]`, not discarded
    (item 5): the paper can still say the number arrived through it. The
    new source's own `note` is computed fresh, including the same
    `unattributed: attribution not checked` marker `attribute_findings`
    writes, so a rebind to a record with no fetched text is never carried
    as if it had been attributed (item 4).
    """
    url = str(result.get("url") or "").strip()
    if result.get("found") and url.lower().startswith(("http://", "https://")):
        backend = run.turns.backend
        model_title = result.get("title") or url
        fetched = metadata.cached_fetch(run.work_dir, url, backend, model_title=model_title)
        tier = source_policy.tier_for(fetched)
        if tier not in source_policy.SECONDARY_TIERS:
            quote = str(result.get("quote") or "")
            fetched_text = fetched.get("text") or ""
            probe = {"quote": quote, "claim": finding.get("claim") or ""}
            if not fetched_text or attributed(probe, fetched_text):
                note = fetched.get("note") or ""
                if not fetched_text:
                    marker = "unattributed: attribution not checked"
                    note = f"{note}; {marker}" if note else marker
                finding["via"] = finding.get("source") or {}
                finding["source"] = {
                    "kind": "web",
                    "ref": url,
                    "title": fetched.get("title") or model_title,
                    "url_or_path": url,
                    "vendor": "",
                    "tier": 1,
                    "evidence_tier": tier,
                    "authors": fetched.get("authors") or [],
                    "year": fetched.get("year") or "",
                    "venue": fetched.get("venue") or "",
                    "note": note,
                    "text": fetched_text,
                }
                if quote:
                    finding["quote"] = quote
                finding["secondary"] = False
                return True
    finding["secondary"] = True
    return False


def follow_primary_sources(run, findings: list[dict], sid: str) -> None:
    """One follow turn per shaky numeric claim, capped at `run.max_follow`
    across the whole run. #473

    A claim whose only bound source is a review, a preprint, or a
    compilation is asked once for the primary study behind its number. A hit
    rebinds the finding to that primary; a miss is recorded, `secondary`, so
    the writer is told outright rather than left to infer it, and the brief
    says "as summarized by [n]" (`_claims_for_writer`).

    The cap is per run, not per section: `run.follow_used` is the running
    count across every section's call, the field `--max-follow` bounds.

    Gated the same way `attribute_findings` is: a `run.turns` with no
    `backend` attribute at all (every pre-#470 test double) is a no-op.
    """
    if not hasattr(getattr(run, "turns", None), "backend"):
        return
    candidates = _follow_candidates(findings)
    if not candidates:
        return
    remaining = max(0, run.max_follow - run.follow_used)
    followed = candidates[:remaining]
    run.log(
        f"    {sid} follow: {len(followed)} of {len(candidates)} candidate(s), "
        f"{run.follow_used + len(followed)}/{run.max_follow} used this run"
    )
    for finding in followed:
        source = finding.get("source") or {}
        try:
            result = run.turns.follow_primary(
                finding.get("claim") or "", source.get("title") or "", source.get("evidence_tier") or ""
            )
        except (TurnFailed, Escalate):
            result = {"found": False}
        _apply_follow_result(run, finding, result)
        run.follow_used += 1


# #474. A generalizing claim ruled a lever out from one datapoint (#474's own
# example: "protein alone did not prevent lean-mass loss" is true of one
# no-training protocol, not the literature). Word-bounded, so "alone" does
# not fire inside "standalone" and "never" does not fire inside
# "nevertheless": both words sit right against the boundary the regex
# tests, with no space or punctuation to trip it, and both correctly stay
# unmatched.
GENERALIZING = re.compile(r"\b(did not|does not|alone|fails to|no effect|always|never)\b", re.I)

# #474. What the writer's brief carries for a claim the counter-evidence
# pass never reached because the run cap was already spent.
CAPPED_NOTE = "counter-evidence not searched, run cap reached"


def _shares_terms(a: str, b: str) -> bool:
    """Loose overlap: at least one word of length 4+ in common."""
    left = {w for w in re.findall(r"[a-z]{4,}", (a or "").lower())}
    right = {w for w in re.findall(r"[a-z]{4,}", (b or "").lower())}
    return bool(left & right)


def generalizing_claims(findings: list[dict], section: dict) -> list[dict]:
    """Findings whose claim generalizes, or is the sole support for a
    `claims_to_support` item, shakiest first. #474

    Every qualifying finding is tagged `generalizing: True` in place, whether
    or not the run cap below ends up spending a turn on it: a candidate the
    cap left unprocessed still has to fail `checks.section_check`'s
    `counterweighed` row, naming a claim nobody checked.

    A finding that already carries a `counter` state ("hit", "miss", or
    "capped") is excluded: the pass already reached a verdict on it, and a
    resumed section reloading old findings must not spend a second turn
    asking the same claim.

    "Bindings" has no per-finding analogue in this port: a finding carries
    exactly one source, where the Deep Agents twin's `Claim` can carry
    several. The nearest signal available is how many findings back the same
    `claims_to_support` assertion; a claim not tied to any assertion is not
    thin by that measure, so it sorts after every claim that is. Port
    asymmetry, stated not hidden: the Deep Agents twin runs its
    counter-evidence pass during `stage_search`, before its outline (and its
    section-level `claims_to_support`) exists, so it selects by the regex
    alone.
    """
    to_support = section.get("claims_to_support") or []
    support_count: dict[int, int] = {}
    for target in to_support:
        supporters = [f for f in findings if _shares_terms(f.get("claim") or "", target)]
        for finding in supporters:
            support_count[id(finding)] = len(supporters)

    candidates = [
        finding
        for finding in findings
        if not finding.get("counter")
        and (GENERALIZING.search(finding.get("claim") or "") or support_count.get(id(finding)) == 1)
    ]
    for finding in candidates:
        finding["generalizing"] = True

    def sort_key(finding: dict) -> tuple:
        tier = (finding.get("source") or {}).get("evidence_tier") or ""
        bindings = support_count.get(id(finding), 99)
        return (0 if bindings == 1 else 1, 0 if tier in source_policy.SECONDARY_TIERS else 1, bindings)

    return sorted(candidates, key=sort_key)


def counter_evidence_pass(run, findings: list[dict], section: dict) -> None:
    """One counter-evidence turn per generalizing claim, capped at
    `run.max_counter` across the whole run. #474

    A hit appends a new finding, `counterargument_to` pointing at the claim
    it contradicts, so the two reach the writer together
    (`_claims_for_writer`). A miss is recorded on the claim itself
    (`finding["counter"] = "miss"`, never a free-text note), so
    `checks.section_check`'s `counterweighed` row can tell "never checked"
    from "checked, found nothing", and the writer's brief says "no contrary
    evidence found in this search".

    A candidate the cap does not reach this call is marked `"capped"`
    immediately, deterministically, with no model turn:
    `counterweighed` must find every generalizing claim in one of `hit`,
    `miss`, or `capped` once this pass has run over it, and a `capped`
    claim's brief tells the writer to hedge it like a single-source claim.

    Gated the same way `follow_primary_sources` is.
    """
    if not hasattr(getattr(run, "turns", None), "backend"):
        return
    sid = section.get("id") or ""
    candidates = generalizing_claims(findings, section)
    if not candidates:
        return
    remaining = max(0, run.max_counter - run.counter_used)
    selected = candidates[:remaining]
    for finding in candidates[remaining:]:
        finding["counter"] = "capped"
    run.log(
        f"    {sid} counter: {len(selected)} of {len(candidates)} candidate(s), "
        f"{run.counter_used + len(selected)}/{run.max_counter} used this run"
    )
    next_index = len(findings) + 1
    for finding in selected:
        try:
            result = run.turns.counter_search(finding.get("claim") or "")
        except (TurnFailed, Escalate):
            result = {"found": False}
        url = str(result.get("url") or "").strip()
        counter_text = str(result.get("counter_claim") or "").strip()
        hit = False
        if (
            result.get("found")
            and counter_text
            and not is_retrieval_claim(counter_text)
            and url.lower().startswith(("http://", "https://"))
        ):
            backend = run.turns.backend
            model_title = result.get("title") or url
            fetched = metadata.cached_fetch(run.work_dir, url, backend, model_title=model_title)
            quote = str(result.get("quote") or "")
            probe = {"quote": quote, "claim": counter_text}
            # A hit whose fetched text does not back the model's own contrary
            # claim is treated as a miss, the same way `_apply_follow_result`
            # treats a fetched page that contradicts the primary it named.
            if not fetched.get("text") or attributed(probe, fetched.get("text") or ""):
                findings.append(
                    {
                        "id": f"{sid}-cf{next_index}",
                        "section_id": sid,
                        "answers_question": finding.get("answers_question") or "",
                        "claim": counter_text,
                        "quote": quote,
                        "source": {
                            "kind": "web",
                            "ref": url,
                            "title": fetched.get("title") or model_title,
                            "url_or_path": url,
                            "vendor": "",
                            "tier": 1,
                            "evidence_tier": source_policy.tier_for(fetched),
                            "authors": fetched.get("authors") or [],
                            "year": fetched.get("year") or "",
                            "venue": fetched.get("venue") or "",
                            "note": fetched.get("note") or "",
                            "text": fetched.get("text") or "",
                        },
                        "evidence_strength": 0.5,
                        "counterargument_to": finding.get("id") or "",
                        "numbers": [],
                        "origin": "web",
                        "epistemic": "",
                        "study": {},
                    }
                )
                finding["counter_url"] = url
                hit = True
        finding["counter"] = "hit" if hit else "miss"
        run.counter_used += 1


# A claim describes the world. These phrases describe the search instead, and
# a claim built out of one is a narrated retrieval miss, not a finding. The
# creatine paper this ticket names put two such sentences in the body, each
# `important: true`: "No arxiv.org source was found that reports a specific
# quantitative rate/magnitude of lean mass loss...". #469
RETRIEVAL_PHRASES = (
    "source was found",
    "could not be located",
    "via the search boundary",
    "search protocol",
)


def is_retrieval_claim(text: str) -> bool:
    """Whether a claim's text is about the search rather than the topic."""
    lowered = str(text or "").lower()
    return any(phrase in lowered for phrase in RETRIEVAL_PHRASES)


def findings_from_research(result: dict, section_id: str, question: str, start: int = 1) -> list[dict]:
    out = []
    for offset, claim in enumerate(result.get("claims") or [], start=start):
        text = claim.get("text") or claim.get("claim") or ""
        if is_retrieval_claim(text):
            # Refused, not carried forward as a single-source claim about
            # nothing. The gap pass below sees this question still has no
            # finding and researches it again instead. #469
            continue
        out.append(_finding_from_claim(claim, section_id, question, offset))
    if not out and (result.get("answer") or result.get("findings")):
        for offset, item in enumerate(result.get("findings") or [], start=start):
            if isinstance(item, dict) and item.get("claim") and not is_retrieval_claim(item.get("claim")):
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
    local_numbers: dict[str, int] = {}
    if numbers is None:
        # #474. A claim's own citation and its counter-evidence's citation
        # can be numbered out of order: the counter finding a hit appends
        # is reached later in this same loop than the claim it answers.
        # Pre-number every kept, non-contradicted finding once, by url, so
        # either citation can be resolved regardless of which is processed
        # first. Fixes a bug where the fallback path cited the claim's own
        # number in place of the counter finding's.
        n = 1
        for finding in findings:
            status = (verdicts.get(finding["id"]) or {}).get("state") or "unverified"
            if status == "contradicted":
                continue
            url = (finding.get("source") or {}).get("url_or_path") or ""
            local_numbers[url] = n
            n += 1

    def cite_for(url: str) -> int:
        return local_numbers.get(url, 0) if numbers is None else numbers.get(url, 0)

    usable = []
    for finding in findings:
        status = (verdicts.get(finding["id"]) or {}).get("state") or "unverified"
        if status == "contradicted":
            continue
        source = finding.get("source") or {}
        url = source.get("url_or_path") or ""
        cite = cite_for(url)
        text = finding.get("claim") or ""
        if finding.get("secondary"):
            # #473. `follow_primary_sources` left this bound to the review or
            # preprint it started with; the writer is told so outright,
            # deterministically, rather than trusted to infer it from a
            # status value it was never taught.
            text = f"{text} (as summarized by [{cite}])."
        counter = finding.get("counter") or ""
        if counter == "hit":
            # #474. `counter_evidence_pass` found contrary evidence; point the
            # writer at its own citation number, not the claim's. The writer
            # card carries the one instruction to state the condition, so it
            # is not repeated here.
            counter_cite = cite_for(finding.get("counter_url") or "")
            text = f"{text} Contrary evidence in [{counter_cite}]."
        elif counter == "miss":
            text = f"{text} (no contrary evidence found in this search)."
        elif counter == "capped":
            text = f"{text} ({CAPPED_NOTE}; hedge like a single source)."
        usable.append(
            {
                "id": finding["id"],
                "text": text,
                "source_url": url,
                "quote": finding.get("quote") or "",
                "question_id": finding.get("answers_question") or "",
                "section": section_id,
                "status": status,
                "number": cite,
                # Read by `checks.section_check`'s `guideline_cited` row, not
                # sent to the writer: `WRITER_CLAIM_FIELDS` in `turns.py`
                # still names only `id, number, text, status`. #473
                "tier": source.get("evidence_tier") or "",
                # Read by `checks.section_check`'s `evidence_requirements_met`
                # row, same reason `tier` above is. #475
                "year": source.get("year") or "",
                # Read by `checks.section_check`'s `counterweighed` row, same
                # reason. #474
                "generalizing": bool(finding.get("generalizing")),
                "counter": counter,
                "counterargument_to": finding.get("counterargument_to") or "",
            }
        )
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


def _load_findings_payload(run, section_id: str) -> dict:
    path = run.file(f"knowledge/{section_id}/findings.json")
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _research_done(run, section_id: str) -> bool:
    """Findings on disk, paid for, still good. Independent of the draft."""
    payload = _load_findings_payload(run, section_id)
    return bool(payload.get("findings"))


def _section_stamped(run, section_id: str) -> bool:
    body = run.file("sections") / f"{section_id}.md"
    if not body.exists() or not _research_done(run, section_id):
        return False
    for entry in _load_ledger(run):
        if entry.get("section_id") == section_id:
            return True
    return False


def _rows_for_editor(score, verdict: dict) -> list[str]:
    """Python rows plus judge rows, in that order, no duplicates.

    `length` never reaches the judge's `failed_rows`. On a Python-only
    failure the live editor was told 'Fix only these rows: the rows named
    below' because `failed_rows` was empty (#349).
    """
    python = []
    if score is not None:
        # `length` is advisory since #366, so it is not in `signature()`. The
        # editor still has to hear the row name; `advisories()` is that list.
        python = list(score.signature()) + list(score.advisories())
    judge = [str(row) for row in (verdict or {}).get("failed_rows") or [] if row]
    return list(dict.fromkeys([*python, *judge]))


def _section_done(run, section_id: str) -> bool:
    """Skip the whole section on resume unless we were told to rewrite.

    `--reuse-research` keeps findings and rewrites prose. `--reuse-drafts`
    keeps the stamped body even when the harness SHA changed.
    """
    if getattr(run, "reuse_drafts", False):
        return _section_stamped(run, section_id)
    if getattr(run, "reuse_research", False):
        return False
    return _section_stamped(run, section_id)


def has_unstamped_research(run) -> bool:
    """Research on disk for a section that is not yet stamped."""
    root = run.file("knowledge")
    if not root.is_dir():
        return False
    for path in root.glob("*/findings.json"):
        if _research_done(run, path.parent.name) and not _section_stamped(run, path.parent.name):
            return True
    return False


def _answered(findings: list, text: str) -> bool:
    return any(
        (item.get("answers_question") == text or item.get("question") == text) and item.get("claim")
        for item in findings
    )


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


def _pack_hits(run) -> list[dict]:
    """The corpus pack's hits, or an empty list. A missing pack is not an error."""
    path = run.file("corpus/brain-pack.json")
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return [hit for hit in (payload.get("hits") or []) if isinstance(hit, dict)]


def _resolve_hit(run, pack: list[dict], key: str) -> tuple[dict | None, str]:
    """The cabinet record behind one reference key, and why there is none.

    The pack first, because it is already in memory and it is what the outline
    was planned against. `outlines.resolve_ref` is the rule the outline gate
    applies to a `corpus_ref`, so a key the outliner could cite is a key this
    can find: exact, or a suffix on a segment boundary.

    Two candidates end the search. `corpus.resolve` returns the first claim file
    whose name starts with the id, so falling through would settle the ambiguity
    by directory order and cite whichever paper sorted first.
    """
    if not key:
        return None, "unresolved corpus key"
    keys = [str(hit.get("key") or "") for hit in pack]
    resolved, matches = outlines.resolve_ref(key, keys)
    if resolved:
        return pack[keys.index(resolved)], ""
    if len(matches) > 1:
        return None, "ambiguous corpus key: " + ", ".join(sorted(matches))
    found = corpus.resolve(key, run.corpus_roots())
    return (found.as_dict(), "") if found is not None else (None, "unresolved corpus key")


def _unlocated(finding: dict, key: str, reason: str) -> dict:
    """One row of `unresolved.json`: what was dropped, and why."""
    return {
        "id": finding.get("id") or "",
        "key": key,
        "title": (finding.get("source") or {}).get("title") or "",
        "reason": str(reason),
    }


def _load_located(run) -> dict:
    path = run.file(LOCATED_FILE)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def locate_cabinet_findings(run, findings: list[dict]) -> tuple[list[dict], list[dict]]:
    """Give every cabinet finding a URL a reader can open, or drop it.

    Run 21 published `corpus:knowledge:claim.x` as a bibliography entry. The
    cabinet knows what it read and not where the public copy lives, so this
    asks the locator once per source and writes the answer back onto the
    SourceDocument, the pack-fed finding, and a run-level cache.

    A finding that cannot be located does not continue down the section
    pipeline. It is returned in the second list instead, which is why this runs
    before the gap pass: the question it answered becomes a gap and gets
    researched on the live web.
    """
    kept: list[dict] = []
    unlocated: list[dict] = []
    cache = _load_located(run)
    pack = _pack_hits(run)
    # The belt. `corpus_search` prints a `URL:` line, and a researcher that
    # cites that page instead of the key has cited the same cabinet source.
    # Left as a web finding it faces the research wall, and the librarian was
    # never asked about arxiv.org, so the `hosts` row fails a reference the
    # brain already held. The run must not depend on which spelling the model
    # chose. First hit wins, and the pack is ranked, so two claims out of one
    # paper tag with the better of the two keys rather than the later one.
    public_hits: dict[str, dict] = {}
    for hit in pack:
        public = str(hit.get("url") or "").strip()
        if public.lower().startswith(("http://", "https://")):
            public_hits.setdefault(public, hit)
    turns = found = missed = tagged = 0

    for finding in findings:
        source = finding.get("source") or {}
        hit = public_hits.get(str(source.get("url_or_path") or "").strip())
        if hit is not None:
            key = str(hit.get("key") or "")
            ref = str(source.get("ref") or "").strip()
            # No turn and no rewrite: the URL already is the public copy. Only
            # the paperwork changes, so the gates read it as what it is.
            if not ref or ref.lower().startswith(("http://", "https://")):
                source["ref"] = key
            if not source.get("title"):
                source["title"] = str(hit.get("source_title") or "")
            if not source.get("vendor"):
                source["vendor"] = str(hit.get("vendor") or "")
            source["kind"] = "corpus"
            source["located_from"] = key
            finding["source"] = source
            finding["origin"] = "corpus"
            kept.append(finding)
            tagged += 1
            continue
        if not locate.is_cabinet(finding):
            kept.append(finding)
            continue
        if str(source.get("url_or_path") or "").startswith(("http://", "https://")):
            kept.append(finding)
            continue

        key = locate.normalize_key(source.get("ref") or source.get("url_or_path") or "")
        hit, why = _resolve_hit(run, pack, key)
        if hit is None:
            unlocated.append(_unlocated(finding, key, why))
            missed += 1
            continue

        pack_key = str(hit.get("key") or key)
        # The claim carried the text; the cabinet carries the bibliography.
        if not source.get("title"):
            source["title"] = str(hit.get("source_title") or "")
        if not source.get("vendor"):
            source["vendor"] = str(hit.get("vendor") or "")
        source["ref"] = pack_key
        finding["source"] = source

        public = str(hit.get("url") or "")
        if public.startswith(("http://", "https://")):
            source["url_or_path"] = public
            source["located_from"] = pack_key
            kept.append(finding)
            continue

        # One source, one answer. Two claims out of the same paper are one turn.
        dedupe = str(hit.get("source_hash") or "") or pack_key
        entry = cache.get(dedupe)
        if entry is None:
            if not hit.get("source_title"):
                unlocated.append(_unlocated(finding, pack_key, "no title to locate"))
                missed += 1
                continue
            spent = run.exhausted()
            if spent:
                unlocated.append(_unlocated(finding, pack_key, spent))
                missed += 1
                continue
            reason = "not found"
            try:
                reply = run.turns.locate(**locate.query_for(finding))
            except (TurnFailed, Escalate) as exc:
                reply = {"url": "", "supports": False, "excerpt": ""}
                reason = str(exc)
            turns += 1
            url = locate.admit(reply)
            entry = {
                "url": url,
                "supports": bool(url),
                "excerpt": str(reply.get("excerpt") or ""),
                "key": pack_key,
                "reason": "" if url else reason,
            }
            cache[dedupe] = entry
            # Before the next finding, not at the end. A kill after a paid turn
            # must not make the next run pay for it again.
            run.write_json(LOCATED_FILE, cache)

        url = locate.admit(entry)
        if not url:
            unlocated.append(_unlocated(finding, pack_key, entry.get("reason") or "not found"))
            missed += 1
            continue

        source_hash = str(hit.get("source_hash") or "")
        if source_hash:
            for root in run.corpus_roots():
                if rkc.attach_url(root, source_hash, url) is not None:
                    break
        source["url_or_path"] = url
        source["kind"] = "corpus"
        source["located_from"] = pack_key
        finding["origin"] = "corpus"
        kept.append(finding)
        found += 1

    sid = next((f.get("section_id") for f in findings if f.get("section_id")), "")
    run.log(f"    {sid} locate: {turns} turns, {found} hits, {tagged} tagged, {missed} misses")
    return kept, unlocated


def run_section(run, section: dict) -> dict:
    """Steps 3a to 3h for one approved section."""
    sid = section["id"]
    if _section_done(run, sid):
        run.log(f"    section {sid} already done")
        return {"section": sid, "skipped": True}

    questions = question_list(section)
    knowledge = run.file(f"knowledge/{sid}")
    knowledge.mkdir(parents=True, exist_ok=True)

    # 3b research. Findings are a skip key of their own (#360).
    findings: list[dict] = []
    queries: list[str] = []
    loaded = _load_findings_payload(run, sid)
    if loaded.get("findings"):
        findings = list(loaded.get("findings") or [])
        queries = list(loaded.get("queries") or [])
        run.log(f"    section {sid} research already done")
    unanswered = [q for q in questions if not _answered(findings, q["text"])]
    if unanswered:
        if hasattr(run.turns, "research_section") and not findings:
            result = run.turns.research_section(section, questions, note="")
            findings = list(result.get("findings") or [])
            queries = list(result.get("queries") or [])
            unanswered = [q for q in questions if not _answered(findings, q["text"])]
        for question in unanswered:
            raw = run.turns.research(question["text"], "")
            findings.extend(
                findings_from_research(raw, sid, question["text"], start=len(findings) + 1)
            )
            queries.append(question["text"])

    # 3b-bis locate. Every cabinet finding gets a URL a reader can open, or it
    # leaves the pipeline here. Before the gap pass, so a question whose only
    # finding was unlocated is researched again on the live web.
    findings, unlocated = locate_cabinet_findings(run, findings)
    run.write_json(f"knowledge/{sid}/{UNRESOLVED_FILE}", {"unresolved": unlocated})

    # 3b-ter metadata, early. `evidence_requirements_met` below needs
    # `evidence_tier`, which only exists after this runs; the full pass at
    # 3c-bis below (idempotent, cache-backed) covers whatever the gap loop
    # adds. #475
    enrich_source_metadata(findings, run)

    # 3c gap pass. A question with no finding at all is researched once, the
    # existing behavior; a question with findings that still fall short of
    # its own `evidence_requirements` block is researched once more too,
    # naming the shortfall. Either way it is one extra turn per question,
    # consumed here, not retried: `do_sections` runs this section's loop
    # once, forward only, never re-entering it mid-run. #475
    gaps = [
        item
        for item in (loaded.get("coverage_gaps") or [])
        if not _answered(findings, item.get("question") or "")
    ]
    answered = {f.get("answers_question") for f in findings if f.get("claim")}
    for question in questions:
        bound = [f for f in findings if f.get("answers_question") == question["text"]]
        unanswered = question["text"] not in answered and not _answered(findings, question["text"])
        requirements = question.get("evidence_requirements") or {}
        met, reason = (
            (True, "")
            if not requirements
            else checks.evidence_requirements_met(requirements, _flatten_for_grading(bound))
        )
        if not unanswered and met:
            continue
        note = "" if unanswered else f"evidence_requirements shortfall: {reason}. Search again naming what is missing."
        try:
            if hasattr(run.turns, "gap_research"):
                raw = run.turns.gap_research(section, question, queries, note=note)
            else:
                raw = run.turns.research(
                    question["text"], note or "gap: restated, previous queries listed"
                )
        except (TurnFailed, Escalate):
            raw = {"claims": [], "findings": []}
        extra = findings_from_research(raw, sid, question["text"], start=len(findings) + 1)
        if extra:
            enrich_source_metadata(extra, run)
            findings.extend(extra)
        bound = [f for f in findings if f.get("answers_question") == question["text"]]
        met, reason = (
            (True, "")
            if not requirements
            else checks.evidence_requirements_met(requirements, _flatten_for_grading(bound))
        )
        if unanswered and not extra:
            gaps.append({"question": question["text"], "queries": list(queries)})
        elif not met:
            gaps.append({"question": question["text"], "queries": list(queries), "reason": reason})
        queries.append(question["text"])

    # 3c-bis metadata. One pass, after every research path for this section
    # has converged on the same finding shape, replaces each web source's
    # title with the record's. #470
    enrich_source_metadata(findings, run)

    # 3c-ter attribution. A finding whose own cited source does not say what
    # its claim says is dropped here, before it is written to disk, so
    # `do_sections`'s aggregation downstream never sees it. #471
    findings = attribute_findings(run, findings, sid)

    # 3c-quater follow. A numeric finding bound only to a review, a preprint,
    # or a compilation gets one turn asking for the primary study behind its
    # number, before verify spends its own turns on the same findings. #473
    follow_primary_sources(run, findings, sid)

    # 3c-quinquies counter. A generalizing claim gets one turn asking for
    # evidence it is not the case, or holds only under conditions, still
    # before verify spends its own turns on the same findings. #474
    counter_evidence_pass(run, findings, section)

    payload = {
        "section_id": sid,
        "findings": findings,
        "coverage_gaps": gaps,
        "queries": queries,
    }
    _write_findings(run, sid, payload)

    # 3d verify
    verdicts: dict[str, dict] = {}
    vpath = knowledge / "verdicts.json"
    if vpath.exists() and loaded.get("findings"):
        try:
            for item in json.loads(vpath.read_text(encoding="utf-8")).get("verdicts") or []:
                fid = item.get("finding_id") or ""
                if fid:
                    verdicts[fid] = item
        except (OSError, json.JSONDecodeError):
            verdicts = {}
    shaky = sorted(findings, key=lambda f: float(f.get("evidence_strength") or 0.5))
    cap = run.max_claims
    checked = 0
    for finding in shaky:
        if finding.get("id") in verdicts:
            continue
        epistemic = (finding.get("epistemic") or "").lower()
        origin = finding.get("origin") or (finding.get("source") or {}).get("kind")
        # A corroborated cabinet claim skips the verifier because two agents in
        # the brain already agreed. That is an argument about the claim, not
        # about the reference: a skip with no public URL stamps `verified` on a
        # row no reader can open. The locator runs before this, so a cabinet
        # finding that got here without an http URL is one it could not place,
        # and it goes to the verifier like anything else.
        located = str((finding.get("source") or {}).get("url_or_path") or "").lower()
        if (
            origin == "corpus"
            and epistemic == "corroborated"
            and located.startswith(("http://", "https://"))
        ):
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
        # Silence is not a result. A `not_found`-shaped verdict still names
        # what the verifier tried, so the record shows a search happened
        # rather than nothing at all. #471
        note = verdict.get("excerpt") or ""
        if not note and state == "unverified":
            queries = list(queries_used) or [(finding.get("claim") or "")[:80]]
            note = f"not_found: searched {queries}"
        verdicts[finding["id"]] = {
            "finding_id": finding["id"],
            "state": state,
            "queries_used": queries_used,
            "note": note,
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

    from paper import _section_instruction, _strip_policy_leak  # noqa: PLC0415

    previous_sig: tuple[str, ...] | None = None
    previous_gaps: dict[str, float] = {}
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
        # #452 #465 #412. A `cited` failure quotes the offending sentence into
        # `report()`, host and all, and a judge's own notes can repeat one
        # back too. Neither may reach the writer's next attempt.
        retry_note = _strip_policy_leak(retry_note, run.allowed_domains)
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
        edit_rows = _rows_for_editor(last_score, last_verdict)
        edit_verdict = {**last_verdict, "failed_rows": edit_rows}
        if edit_rows:
            instruction = (
                f"{instruction}\n\nEdit mode. Fix only these rows: "
                f"{', '.join(edit_rows)}. Add no facts."
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
                    edit_verdict,
                    relative,
                    note=_strip_policy_leak(last_score.report(), run.allowed_domains) if last_score else "",
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
                # The writer holds `Write` on this path, so it can have landed
                # a whitespace file before answering with nothing. Remove it:
                # the next attempt reads a whitespace file as a draft and edits
                # emptiness, and `_section_done` reads it as finished work.
                run.log(f"    {sid}: the writer produced nothing on the first attempt.")
                path.unlink(missing_ok=True)
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
                # The numbered claims, the same list the writer and the
                # deterministic check hold. Handing the judge the raw findings
                # showed it numeric citations with no map from number to
                # source, so it could not check one against the other.
                last_verdict = run.turns.judge_section(section, body, bound, note=judge_note)
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
        # A row that measures its own gap says whether the attempt moved. Row
        # names alone read 1739 words and 1600 words against a 1500 ceiling as
        # the same failure, and the loop stopped while the writer was closing
        # it. One word of movement is noise, so ask for a real step.
        distances = last_score.distances()
        progressed = any(
            name in previous_gaps and gap < previous_gaps[name] * 0.9
            for name, gap in distances.items()
        )
        decision = gates.decide(
            progressed=progressed,
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
        previous_gaps = distances

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
