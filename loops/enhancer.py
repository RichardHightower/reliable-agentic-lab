#!/usr/bin/env python3
"""The Ticket Enhancer. Module 1, the smallest loop that Module 2 can score.

A vague ticket in, a ready contract out. It is the simplest of the three loops
and it carries the same three parts as the others:

    orchestrator   owns the budget and the exits
    doer           edits the ticket body, and nothing else
    judge          scores the ticket against criteria for its kind

The exits are the lesson. It stops when the ticket is ready, when the budget is
spent, or when two rounds in a row find exactly the same gaps, which means the
human has not acted and another round will not help.

When the ticket names an error it cannot explain, the enhancer asks the research
boundary once, inside the budget, and folds the answer into its comment.

    task loop:enhancer -- --repo work/northwind-field-crm --ticket T001
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

from loops import criteria, doers, gates, research, roles
from loops import ticket as tickets
from loops.contract import Contract

ERROR_LINE = re.compile(r"^(?:.*?)\b([A-Z][A-Za-z]*(?:Error|Exception))\b.*$", re.M)


def _find_error(body: str) -> str | None:
    match = ERROR_LINE.search(body)
    return match.group(0).strip() if match else None


def run(  # noqa: PLR0913, PLR0912, PLR0915
    *,
    repo: str | Path,
    ticket_id: str = "T001",
    budget: int | None = None,
    incorporate: bool = False,
    doer: str | doers.Backend | None = None,
    research_backend: research.Backend | None = None,
    write_trace: bool = True,
) -> dict:
    """Groom one ticket until it is ready, the budget is spent, or it stalls.

    One function on purpose. The rounds, the judge, the research call, and the
    three exits read in the order they happen.
    """
    contract = Contract(repo)
    contract.validate()
    target = contract.repo
    folder = contract.tickets.get("path", "tickets")

    cast = roles.build(contract)
    boss: roles.Orchestrator = cast["orchestrator"]
    if budget:
        boss.budget_iterations = budget

    scholar = None
    if research_backend is not None:
        scholar = research.Researcher(
            backend=research_backend, budget=research.Budget(max_calls=2, max_usd=0.05)
        )

    trace: dict = {"ticket": ticket_id, "repo": str(target), "rounds": []}
    previous: tuple[str, ...] | None = None
    decision = gates.Decision(gates.RETRY, "not started")

    while True:
        iteration = boss.start_iteration()
        the_ticket = tickets.load(target, ticket_id, folder, prefer_ready=False)
        verdict = criteria.judge(the_ticket)

        comment = criteria.suggestion(the_ticket, verdict)
        evidence = None
        if not verdict.ready and scholar is not None:
            error = _find_error(the_ticket.body)
            if error:
                try:
                    finding = scholar.ask(error)
                    if finding.answer:
                        evidence = finding.to_dict()
                        comment += f"\n\nLooked up `{error}`:\n\n{finding.answer}\n"
                        comment += "".join(f"\n- {c}" for c in finding.citations)
                except research.BudgetExceeded as exc:
                    comment += f"\n\n(Research budget spent: {exc})"

        decision = gates.decide(
            passed=verdict.ready,
            iteration=iteration,
            budget=boss.budget_iterations,
            signature=verdict.signature(),
            previous_signature=previous,
            usd_left=boss.usd_left,
        )

        round_record = {
            "iteration": iteration,
            "kind": verdict.kind,
            "ready": verdict.ready,
            "missing": verdict.missing,
            "gate": decision.gate,
            "reason": decision.reason,
            "comment": comment,
        }
        if evidence:
            round_record["research"] = evidence
        trace["rounds"].append(round_record)

        if verdict.ready:
            _mark_ready(target, the_ticket, folder)
            break
        if decision.stop:
            break
        if doer is not None:
            # A real backend edits the ticket, the same way implementer.run and
            # fixer.run already hand work to one. Supersedes --incorporate's
            # canned fixture copy when a doer is actually given.
            _doer_edit(target, the_ticket, doer, comment)
        elif incorporate:
            # Stands in for a human accepting the suggestion between rounds.
            _incorporate(target, the_ticket, folder)
        previous = verdict.signature()

    trace["gate"] = decision.gate
    trace["reason"] = decision.reason
    trace["ready"] = decision.gate == gates.PASS
    if scholar:
        trace["research_budget"] = scholar.budget.line()
    if write_trace:
        out = target / ".harness"
        out.mkdir(parents=True, exist_ok=True)
        trace["written_at"] = time.time()
        (out / "last-enhancer.json").write_text(json.dumps(trace, indent=2), encoding="utf-8")
    return trace


def _mark_ready(repo: Path, the_ticket: tickets.Ticket, folder: str) -> None:
    if the_ticket.path is None:
        return
    text = the_ticket.path.read_text(encoding="utf-8")
    if "state: ready" not in text:
        text = re.sub(r"^state:\s*\w+$", "state: ready", text, count=1, flags=re.M)
        the_ticket.path.write_text(text, encoding="utf-8")


def _incorporate(repo: Path, the_ticket: tickets.Ticket, folder: str) -> None:
    """Copy the ready version over the draft, the way a human would after editing."""
    ready = sorted((repo / folder).glob(f"{the_ticket.id}*.ready.md"))
    if not ready or the_ticket.path is None:
        return
    the_ticket.path.write_text(ready[0].read_text(encoding="utf-8"), encoding="utf-8")


def _doer_edit(repo: Path, the_ticket: tickets.Ticket, doer: str | doers.Backend, comment: str) -> None:
    """Have a real doer backend edit the ticket, scoped to tickets/** (the
    doer role's write scope, `solutions/roleplan.py`'s `FALLBACK_SCOPE["doer"]`).

    Unlike `_incorporate`'s canned fixture copy, this calls a real backend:
    a CLI tool, the reference answer, or a runtime port's own Backend, the
    same way implementer.run and fixer.run already hand work to one.
    """
    if the_ticket.path is None:
        return
    backend = doers.build(doer)
    prompt = (
        f"Edit {the_ticket.path.relative_to(repo)} to address this feedback, "
        f"and nothing else:\n\n{comment}"
    )
    backend.run(repo=repo, prompt=prompt, allow=["tickets/**"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ticket Enhancer")
    parser.add_argument("--repo", default="work/northwind-field-crm")
    parser.add_argument("--ticket", default="T001")
    parser.add_argument("--budget", type=int, default=None)
    parser.add_argument(
        "--incorporate",
        action="store_true",
        help="Stand in for a human accepting the suggestion between rounds.",
    )
    parser.add_argument(
        "--doer",
        default=None,
        help="A real backend edits the ticket instead: none, reference, "
        "reference:<ref>, or a CLI tool name. Supersedes --incorporate.",
    )
    parser.add_argument(
        "--research",
        default="fixture",
        choices=["off", "fixture", "auto"],
        help="Look up an error the ticket cannot explain.",
    )
    args = parser.parse_args(argv)

    backend = None
    if args.research == "fixture":
        backend = research.FixtureBackend(Path(__file__).parent / "fixtures" / "research.json")
    elif args.research == "auto":
        backend = research.choose(fixture=Path(__file__).parent / "fixtures" / "research.json")

    trace = run(
        repo=args.repo,
        ticket_id=args.ticket,
        budget=args.budget,
        incorporate=args.incorporate,
        doer=args.doer,
        research_backend=backend,
    )
    for record in trace["rounds"]:
        state = "ready" if record["ready"] else "not ready"
        print(f"round {record['iteration']}: {record['kind']}, {state}")
        for item in record["missing"]:
            print(f"  missing: {item}")
    print()
    print(f"gate: {trace['gate']}")
    print(f"reason: {trace['reason']}")
    return 0 if trace["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
