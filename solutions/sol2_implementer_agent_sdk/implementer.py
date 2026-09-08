#!/usr/bin/env python3
"""The Ticket Implementer. Module 2, the centre of the workshop.

Ready ticket in, reviewed pull request out. The order is fixed, and every step
of it is enforced by something other than a prompt:

    1. Read the ticket and its acceptance criteria.
    2. The planner writes steps.jsonl. Reject the plan unless every criterion
       maps to a step and every step carries a validation statement.
    3. The test implementer writes tests. It cannot touch app code.
    4. RED GATE. Read junit.xml. If the new tests are not failing, stop. A test
       that passes before any code exists proves nothing.
    5. The code implementer writes code until the suite is green. It cannot
       touch tests, so it cannot reach green by weakening one. A retry carries
       the failed rubric rows and the failing test ids, not the same ticket
       prompt again.
    6. The rubric judge scores ten rows. No model.
    7. The final judge subagent answers in JSON. Unparseable is done=False.
       Green rubric plus the judge saying not done is escalate.
    8. Pass, retry, or escalate.

Run it against any repo that satisfies the contract:

    task loop:implementer -- --repo work/northwind-field-crm --ticket T001
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
from pathlib import Path

import doers
import gates
import receipt
import rubric
import steps
import ticket as tickets
import write_scope as roles
from contract import Contract, ContractError


def _new_test_ids(before: set[str], after_failed: set[str]) -> set[str]:
    """Test ids that are failing now and did not exist before. The red proof."""
    return {test_id for test_id in after_failed if test_id not in before}


def plan_for(target_ticket: tickets.Ticket) -> steps.Plan:
    """A plan derived from the ticket, one test step and one code step per criterion.

    ponytail: derived, not generated. Swapping this for a planner subagent is
    lab 2's stretch goal, and the schema it must satisfy is already enforced.
    """
    made: list[steps.Step] = []
    for index, criterion in enumerate(target_ticket.criteria, 1):
        made.append(
            steps.Step(
                id=f"S{index}T",
                ticket=target_ticket.id,
                role="test_implementer",
                action=f"Write a test that fails until this holds: {criterion.text}",
                validation=f"a test covering {criterion.id} exists and fails before any code",
                criterion=criterion.id,
            )
        )
        made.append(
            steps.Step(
                id=f"S{index}C",
                ticket=target_ticket.id,
                role="code_implementer",
                action=f"Implement: {criterion.text}",
                validation=f"the test covering {criterion.id} passes",
                criterion=criterion.id,
            )
        )
    return steps.Plan(steps=made)


def _extract_json(text: str) -> dict | None:
    """The first JSON object in `text`, or None. Never raises."""
    blob = (text or "").strip()
    if not blob:
        return None
    try:
        raw = json.loads(blob)
        return raw if isinstance(raw, dict) else None
    except ValueError:
        pass
    start, end = blob.find("{"), blob.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        raw = json.loads(blob[start : end + 1])
        return raw if isinstance(raw, dict) else None
    except ValueError:
        return None


def parse_judge_verdict(text: str, structured: dict | None = None) -> tuple[bool, dict]:
    """The judge's `done` flag. Unparseable is done=False, never a pass."""
    payload = structured if isinstance(structured, dict) else _extract_json(text)
    if not isinstance(payload, dict) or "done" not in payload:
        return False, {
            "done": False,
            "why": "unparseable verdict",
            "raw": (text or "")[:400],
        }
    return bool(payload["done"]), payload


def _ask_judge(
    backend,
    *,
    repo: Path,
    ticket: tickets.Ticket,
    score: rubric.Score,
    changed: list[str],
    plan: steps.Plan,
) -> tuple[bool, dict, float]:
    """Invoke the judge once. Offline backends return valid JSON; live ones run.

    `changed` is the code phase's own files, so the judge can name what it is
    grading instead of taking the rubric's word for it. `plan` is the ticket's
    steps.jsonl, so the judge can point at the step a criterion maps to.
    """
    changed_lines = "\n".join(f"- {path}" for path in changed) or "- (no files changed)"
    plan_lines = "\n".join(f"- {step.id}: {step.validation}" for step in plan.steps)
    prompt = (
        f"{ticket.for_prompt()}\n\n"
        "The ten-row rubric is green.\n\n"
        f"{score.report()}\n\n"
        f"Files changed in the code phase:\n{changed_lines}\n\n"
        f"Plan steps:\n{plan_lines}\n\n"
        "Does this diff do what the ticket asked? Reply with JSON only: "
        '{"done": true, "why": "one sentence"}. Do not name a gate. '
        "Do not say pass, retry, or escalate."
    )
    judge = getattr(backend, "judge", None)
    if judge is None:
        done, payload = parse_judge_verdict(
            '{"done": true, "why": "offline backend; rubric is green"}'
        )
        return done, payload, 0.0
    result = judge(repo=repo, prompt=prompt)
    structured = getattr(result, "structured", None)
    if structured is not None and not isinstance(structured, dict):
        structured = None
    done, payload = parse_judge_verdict(getattr(result, "output", "") or "", structured)
    return done, payload, float(getattr(result, "usd", 0.0) or 0.0)


def _test_prompt(ticket: tickets.Ticket, plan: steps.Plan) -> str:
    """The ticket, plus every step the test phase owns.

    Every plan step where `role == "test_implementer"`, with its id, action,
    and validation, so the test implementer can see what the planner asked
    for instead of guessing at coverage. `_code_prompt` stays as it was: the
    code implementer never sees a test step.
    """
    body = ticket.for_prompt()
    test_steps = plan.for_role("test_implementer")
    if not test_steps:
        return body
    lines = "\n".join(f"- {step.id}: {step.action} ({step.validation})" for step in test_steps)
    return f"{body}\n\nPlan steps for this phase:\n{lines}"


def _code_prompt(
    ticket: tickets.Ticket,
    decision: gates.Decision | None,
    failed_rows: list[str],
    failed_tests: list[str],
) -> str:
    """The ticket, plus what failed, when this is a retry.

    The first code turn gets the ticket. Every later turn gets
    `gates.retry_instruction` and the failing test ids in front of it, so the
    doer is not asked to rediscover the same failure.
    """
    body = ticket.for_prompt()
    if decision is None or decision.gate != gates.RETRY:
        return body
    extra = gates.retry_instruction(decision, failed_rows)
    if failed_tests:
        extra += f"\nFailing tests: {', '.join(failed_tests)}."
    return extra + "\n\n" + body


def _worktree(repo: Path, ticket_id: str) -> Path:
    """An isolated git worktree for one ticket. Every run mutates this tree,
    never the caller's repo.

    Path: a sibling of the resolved repo, `<repo>.worktrees/<ticket_id>`.
    Never `tempfile.gettempdir()` (a per-user, OS-reaped path on darwin, and
    `/tmp` is a symlink `git worktree list` will not match) and never
    `repo.name` alone: every fixture repo in the tests is named "repo" with
    ticket "T001", so a basename key would collide. A sibling of the
    *resolved* repo does not, because two different fixture repos resolve to
    two different parents.

    An existing, registered worktree is reused by this same deterministic
    path; that determinism is what a future `--resume` (A6) needs. A path
    that exists but is not a registered worktree is a leftover, and
    `git worktree add` never runs on top of one.

    Two things are refused before anything else runs, because either one
    would let `reset --hard` / `clean -fd` land somewhere other than this
    literal sibling path: a symlink at the worktree path (it would resolve
    into whatever registered worktree it points at -- the source repo
    itself, or another ticket's worktree, and both have been reproduced),
    and a target repo that is a plain directory nested inside some other
    git repo (`git worktree list` then exits 0 and names the outer repo).
    """
    repo = Path(repo).resolve()
    path = repo.parent / f"{repo.name}.worktrees" / ticket_id

    if path.is_symlink():
        raise ContractError(f"{path} is a symlink; refusing to use it as a worktree path")

    toplevel = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--show-toplevel"],
        text=True,
        capture_output=True,
        check=False,
    )
    if toplevel.returncode != 0 or Path(toplevel.stdout.strip()).resolve() != repo:
        raise ContractError(
            "the target repo is not a git repository; the implementer isolates "
            "every run in a worktree"
        )

    listing = subprocess.run(
        ["git", "-C", str(repo), "worktree", "list", "--porcelain"],
        text=True,
        capture_output=True,
        check=False,
    )
    registered = {
        Path(line[len("worktree ") :]).resolve()
        for line in listing.stdout.splitlines()
        if line.startswith("worktree ")
    }

    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        if path.resolve() != path or path.resolve() not in registered:
            raise ContractError(
                f"{path} exists but is not a registered git worktree of {repo}. "
                "Remove it by hand, or run a different --ticket."
            )
        # Reused. There is no --resume flag yet (A6 adds one), so every run
        # here is a fresh run: reset the worktree to HEAD before the
        # baseline, rather than carrying the last attempt's code forward.
        # -fd, not -x, so a gitignored .venv the bootstrap step symlinked in
        # is left alone.
        _git(path, "reset", "--hard", "HEAD")
        _git(path, "clean", "-fd")
        harness_dir = path / ".harness"
        if harness_dir.exists():
            shutil.rmtree(harness_dir)
    else:
        branch = f"implementer/{ticket_id}"
        added = subprocess.run(
            ["git", "-C", str(repo), "worktree", "add", "-B", branch, str(path), "HEAD"],
            text=True,
            capture_output=True,
            check=False,
        )
        if added.returncode != 0:
            raise ContractError(f"git worktree add failed for {path}: {added.stderr.strip()}")

    _bootstrap(repo, path)
    _copy_ticket(repo, path, ticket_id)
    return path


def _git(cwd: Path, *args: str) -> None:
    proc = subprocess.run(
        ["git", "-C", str(cwd), *args], text=True, capture_output=True, check=False
    )
    if proc.returncode != 0:
        raise ContractError(f"git {' '.join(args)} failed in {cwd}: {proc.stderr.strip()}")


def _bootstrap(repo: Path, path: Path) -> None:
    """A worktree checks out tracked files only, and `.venv/` is gitignored.
    Share the source repo's venv when there is one, so the worktree's own
    Taskfile-resolved interpreter exists without a reinstall. `setup` is a
    required task (`contract.py:22`), so the fallback invents no spec the
    target does not already declare.
    """
    target_venv = path / ".venv"
    if target_venv.exists():
        return
    source_venv = repo / ".venv"
    if source_venv.is_dir():
        target_venv.symlink_to(source_venv)
        return
    result = Contract(path).run("setup")
    if not result.ok:
        raise ContractError(
            f"no {target_venv}/bin/python: no {source_venv} to symlink from, and "
            f"`task setup` failed in {path} (exit {result.exit_code})"
        )


def _copy_ticket(repo: Path, path: Path, ticket_id: str) -> None:
    """The enhancer's ticket edit is often uncommitted. `git worktree add`
    checks out HEAD only, so copy the ticket bytes across by hand before a
    live doer, whose cwd is the worktree, would read a stale one.

    `.loop.yml` is copied only when the worktree has none at all: a target
    repo may never track it, and a worktree checkout would then lack it too.
    """
    tickets_path = Contract(repo).tickets.get("path", "tickets")
    source_dir = repo / tickets_path
    if source_dir.is_dir():
        target_dir = path / tickets_path
        target_dir.mkdir(parents=True, exist_ok=True)
        for match in source_dir.glob(f"{ticket_id}*.md"):
            shutil.copy2(match, target_dir / match.name)
    source_loop = repo / ".loop.yml"
    target_loop = path / ".loop.yml"
    if source_loop.is_file() and not target_loop.exists():
        shutil.copy2(source_loop, target_loop)


def _remove_worktree(repo: Path, path: Path) -> None:
    proc = subprocess.run(
        ["git", "-C", str(repo), "worktree", "remove", str(path), "--force"],
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise ContractError(f"git worktree remove failed for {path}: {proc.stderr.strip()}")


def run(  # noqa: PLR0915
    *,
    repo: str | Path,
    ticket_id: str = "T001",
    doer: str | doers.Backend = "reference",
    budget: int | None = None,
    write_trace: bool = True,
    cleanup: bool = False,
) -> dict:
    """Run one implementer loop against a target repo.

    Long on purpose. The eight steps in the module docstring appear here in
    order, so the file reads as the sequence it enforces. Hiding half of them
    behind helpers would satisfy a linter and cost the reader the loop.

    Every step in this function runs inside an isolated git worktree, never
    the caller's repo (`_worktree`). `repo` names the source; `_worktree`
    creates or reuses a worktree for it, copying the source repo's current
    ticket and `.loop.yml` in first. `target` is bound to that worktree, so
    the ticket read and everything after it -- steps.jsonl, .harness, the
    receipt -- happen there, not against the source.
    """
    contract = Contract(repo)
    contract.validate()
    source_repo = contract.repo

    worktree = _worktree(source_repo, ticket_id)
    contract = Contract(worktree)
    target = contract.repo

    the_ticket = tickets.load(target, ticket_id, contract.tickets.get("path", "tickets"))
    if not the_ticket.ready:
        raise ContractError(f"{ticket_id} is not ready. Run the enhancer first.")

    cast = roles.build(contract)
    boss: roles.Orchestrator = cast["orchestrator"]
    if budget:
        boss.budget_iterations = budget

    plan = plan_for(the_ticket)
    plan.validate(criteria=the_ticket.criterion_ids)
    plan.save(target)

    backend = doers.build(doer)
    trace: dict = {
        "ticket": the_ticket.id,
        "repo": str(target),
        "doer": backend.name,
        "criteria": the_ticket.criterion_ids,
        "plan": plan.summary(),
        "iterations": [],
    }

    baseline = contract.run("test")
    known_ids = baseline.junit.passed_ids | baseline.junit.failed_ids

    # Whatever was already dirty is not this loop's doing. The enhancer edits
    # tickets before the implementer runs, and blaming this loop for that would
    # fail write_scope for a change it never made.
    preexisting = {path for path in rubric.changed_files(target) if path != steps.STEPS_FILE}

    # Step 3. Tests first. The test implementer owns tests/ and nothing else.
    # A red-gate miss retries inside this loop's own attempt counter rather
    # than escalating on the first empty attempt. This never calls
    # `boss.start_iteration()`: that counter belongs to the code loop below,
    # and sharing it would spend the code budget on test turns.
    tester = cast["test_implementer"]
    attempt = 0
    previous_test_signature: tuple[str, ...] | None = None
    while True:
        attempt += 1
        test_result = backend.run(
            repo=target, prompt=_test_prompt(the_ticket, plan), allow=list(tester.scope.allow)
        )
        boss.spend(test_result.usd)
        after_tests = contract.run("test")
        red_ids = _new_test_ids(known_ids, after_tests.junit.failed_ids)

        # Attribute writes by phase, not by what a backend claims. Files that
        # appear during the test phase belong to the test implementer; files
        # that appear later belong to the code implementer. A backend that
        # lies about `wrote` cannot move a file out of its phase.
        after_test_phase = {
            path
            for path in rubric.changed_files(target)
            if path != steps.STEPS_FILE and path not in preexisting
        }
        scope_violations = tester.violations(sorted(after_test_phase))
        trace["test_phase"] = {
            "wrote": list(test_result.wrote),
            "files": sorted(after_test_phase),
            "violations": list(scope_violations),
            "ok": test_result.ok,
            "usd": test_result.usd,
        }

        # Step 4. The red gate. A scope violation escalates on the turn it
        # happens; the test phase never gets a second try to stay in scope.
        if scope_violations:
            trace["test_phase_scope_violations"] = sorted(scope_violations)
            trace["scope_violations"] = sorted(scope_violations)
            trace["gate"] = gates.ESCALATE
            trace["reason"] = (
                "test phase wrote outside its scope: " + ", ".join(sorted(scope_violations))
            )
            trace["red_ids"] = sorted(red_ids)
            return _finish(contract, trace, write_trace, source_repo=source_repo, cleanup=cleanup)

        if not contract.rubric.get("require_red", True) or red_ids:
            break

        # Still no red. Retry while the attempt budget allows it, and reuse
        # the code loop's own stop rule (gates.decide) rather than writing a
        # second one: two attempts that touch the same files are not
        # converging, and stop as a stable failure before the budget runs out.
        signature = tuple(sorted(after_test_phase))
        decision = gates.decide(
            passed=False,
            iteration=attempt,
            budget=boss.budget_iterations,
            signature=signature,
            previous_signature=previous_test_signature,
            usd_left=boss.usd_left,
        )
        if decision.stop:
            trace["gate"] = gates.ESCALATE
            trace["reason"] = (
                decision.reason
                if decision.repeat_failure
                else "red gate: no new test was observed failing. A test that passes before "
                "any code exists proves nothing."
            )
            trace["red_ids"] = []
            trace["scope_violations"] = list(scope_violations)
            return _finish(contract, trace, write_trace, source_repo=source_repo, cleanup=cleanup)
        previous_test_signature = signature

    trace["red_ids"] = sorted(red_ids)

    # Steps 5 to 8. Code until green, then judge.
    coder = cast["code_implementer"]
    previous_signature: tuple[str, ...] | None = None
    previous_decision: gates.Decision | None = None
    last_failed_rows: list[str] = []
    last_failed_tests: list[str] = []
    decision = gates.Decision(gates.RETRY, "not started")

    while True:
        iteration = boss.start_iteration()
        prompt = _code_prompt(the_ticket, previous_decision, last_failed_rows, last_failed_tests)
        code_result = backend.run(
            repo=target, prompt=prompt, allow=list(coder.scope.allow)
        )
        boss.spend(code_result.usd)

        test_run = contract.run("test")
        e2e_run = contract.run("e2e")
        lint_run = contract.run("lint")
        format_run = contract.run("format-check")
        changed = [
            c
            for c in rubric.changed_files(target)
            if c != steps.STEPS_FILE and c not in preexisting
        ]
        code_phase = [path for path in changed if path not in after_test_phase]
        violations = sorted(set(scope_violations) | set(coder.violations(code_phase)))

        score = rubric.score(
            contract=contract,
            plan=_mark_proven(plan, test_run.junit.passed_ids, target),
            criteria=the_ticket.criterion_ids,
            test_run=test_run,
            e2e_run=e2e_run,
            lint_run=lint_run,
            format_run=format_run,
            red_ids=red_ids,
            scope_violations=violations,
            changed=changed,
        )
        judge_done: bool | None = None
        if score.passed:
            judge_done, judge_payload, judge_usd = _ask_judge(
                backend, repo=target, ticket=the_ticket, score=score,
                changed=code_phase, plan=plan,
            )
            boss.spend(judge_usd)
            trace["judge"] = judge_payload
        decision = gates.decide(
            passed=score.passed,
            iteration=iteration,
            budget=boss.budget_iterations,
            signature=score.signature(),
            previous_signature=previous_signature,
            usd_left=boss.usd_left,
            judge_done=judge_done,
        )
        trace["iterations"].append(
            {
                "iteration": iteration,
                "wrote": code_result.wrote,
                "prompt": prompt,
                "rows": {row.name: row.passed for row in score.rows},
                "failed": list(score.signature()),
                "gate": decision.gate,
                "reason": decision.reason,
                "judge_done": judge_done,
            }
        )
        trace["rubric"] = score.report()
        if decision.stop:
            break
        previous_signature = score.signature()
        previous_decision = decision
        last_failed_rows = list(score.signature())
        last_failed_tests = sorted(test_run.junit.failed_ids)

    trace["gate"] = decision.gate
    trace["reason"] = decision.reason
    trace["plan"] = plan.summary()
    return _finish(contract, trace, write_trace, source_repo=source_repo, cleanup=cleanup)


def _mark_proven(plan: steps.Plan, passing: set[str], repo: Path) -> steps.Plan:
    """Mark a step done when a passing test names its criterion.

    Evidence comes from junit, never from the doer's own claim. The test name
    has to contain the criterion id (`AC-1`, `ac_1`, ...). A T001-shaped
    filename is not evidence for every unmatched step.
    """
    for step in plan.steps:
        if step.done or not step.criterion:
            continue
        needle = step.criterion.lower().replace("-", "_")
        hit = next(
            (
                test_id
                for test_id in passing
                if step.criterion.lower() in test_id.lower() or needle in test_id.lower()
            ),
            None,
        )
        if hit:
            step.status = steps.DONE
            step.evidence = hit
    plan.save(repo)
    return plan


def _finish(
    contract: Contract,
    trace: dict,
    write_trace: bool,
    *,
    source_repo: Path | None = None,
    cleanup: bool = False,
) -> dict:
    trace.setdefault("gate", gates.ESCALATE)
    if write_trace:
        out = contract.repo / ".harness"
        out.mkdir(parents=True, exist_ok=True)
        trace["written_at"] = time.time()
        (out / "last-implementer.json").write_text(json.dumps(trace, indent=2), encoding="utf-8")
        exit_code = 0 if trace.get("gate") == gates.PASS else 1
        receipt.write(contract.repo, exit_code, list(trace.get("red_ids") or []))
    if source_repo is not None:
        # Never removed automatically. `cleanup` is the one explicit flag
        # that does; otherwise `main` prints the path and the command to do
        # it by hand.
        trace["source_repo"] = str(source_repo)
        trace["worktree"] = str(contract.repo)
        trace["worktree_removed"] = cleanup
        if cleanup:
            _remove_worktree(source_repo, contract.repo)
    return trace


def _print_worktree_status(trace: dict) -> None:
    worktree = trace.get("worktree")
    if not worktree:
        return
    if trace.get("worktree_removed"):
        print(f"worktree removed: {worktree}")
        return
    print(f"worktree: {worktree}")
    print(f"remove it with: git -C {trace.get('source_repo', '')} worktree remove {worktree}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ticket Implementer")
    parser.add_argument("--repo", default="work/northwind-field-crm")
    parser.add_argument("--ticket", default="T001")
    parser.add_argument(
        "--doer",
        default="reference",
        help="none | reference | reference:<ref> | claude | codex | grok | opencode",
    )
    parser.add_argument("--budget", type=int, default=None)
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="remove the worktree after the run. Never automatic otherwise.",
    )
    args = parser.parse_args(argv)

    trace = run(
        repo=args.repo,
        ticket_id=args.ticket,
        doer=args.doer,
        budget=args.budget,
        cleanup=args.cleanup,
    )
    print(trace.get("rubric", ""))
    print()
    print(f"gate: {trace['gate']}")
    print(f"reason: {trace['reason']}")
    _print_worktree_status(trace)
    return 0 if trace["gate"] == gates.PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
