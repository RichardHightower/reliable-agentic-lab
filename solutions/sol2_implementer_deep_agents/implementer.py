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

`--resume` re-enters a killed run from its own checkpoint (`_write_checkpoint`,
read back through `state.json`'s `phase` field): a completed, green test phase
is never replayed, and the code loop picks up with the stored `red_ids`
rather than a fresh red gate.

Run it against any repo that satisfies the contract:

    task run -- --repo work/northwind-field-crm --ticket T001
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

LOOP = "implementer"


def _new_test_ids(before: set[str], after_failed: set[str]) -> set[str]:
    """Test ids that are failing now and did not exist before. The red proof."""
    return {test_id for test_id in after_failed if test_id not in before}


HARNESS_DIR = ".harness/"
_STATE_FILE = HARNESS_DIR + "state.json"
_LAST_TRACE_FILE = HARNESS_DIR + "last-implementer.json"

# The loop's own named outputs, never a role's. Not "everything under
# .harness/": that used to admit any file a doer chose to plant there,
# including an overwrite of state.json or the receipt themselves. Judge of
# PR #500 reproduced both: a doer scoped to tests/** writing
# .harness/planted.py with no violation, and a doer overwriting
# .harness/state.json with forged red_ids and preexisting that survived
# _finish's merge and were trusted by the next --resume.
_LOOP_OUTPUTS = frozenset({steps.STEPS_FILE, _STATE_FILE, _LAST_TRACE_FILE, receipt.RECEIPT})


def _is_loop_bookkeeping(path: str) -> bool:
    """`steps.jsonl` and this loop's own three `.harness/` files are its own
    output, never a role's. Excluded everywhere `rubric.changed_files` feeds
    `preexisting`, `after_test_phase`, or the code phase's own `changed`
    list.

    A6 (#433) is what surfaces the need for this at all: `_write_checkpoint`
    writes `.harness/state.json` mid-run, before the test phase's red gate
    is even decided, so a later `rubric.changed_files` scan in the same run
    would otherwise see it as an untracked file with no role's scope
    covering it, and `write_scope` would fail every run that reaches the
    code loop. A5's own `.harness` writes never hit this, because they only
    ever ran once, at the very end, after the last scan had already
    happened.

    The set is exactly these four names, not the whole directory: anything
    else under `.harness/` -- a doer planting a file, or overwriting one of
    these four itself -- is still a write this loop did not make, and stays
    visible to `write_scope` and the checkpoint's own read-then-merge.
    """
    return path in _LOOP_OUTPUTS


def _state_tampered(path: Path, last_written: bytes | None) -> bool:
    """True when `state.json` exists and its bytes differ from what this
    run's own last write put there.

    Judge of PR #500, second finding: excluding `state.json` from
    `write_scope` (above) means an overwrite of it is otherwise invisible.
    Only `_write_checkpoint` and `_finish` have a legitimate reason to touch
    this file, so any other difference from the bytes this run itself last
    wrote is a doer's hand, not a checkpoint.

    `last_written is None` means this run has not written the file yet
    (the very first checkpoint of a fresh run, or a resume that goes
    straight to the code loop before ever calling `_write_checkpoint`), so
    whatever is already there -- a previous run's own trustworthy leftover
    state, or nothing at all -- is never mistaken for tampering. A missing
    file is likewise not tampering: `_write_checkpoint` and `_finish`
    recreate it either way.
    """
    return last_written is not None and path.is_file() and path.read_bytes() != last_written


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


# A9 (#437 #422). Backends that force `derived` regardless of the --planner
# flag: a live planner with no live doer produces a plan nothing can execute.
CLASSROOM_DOERS = frozenset({"none", "reference"})


def _plan_from_backend(backend, *, repo: Path, ticket: tickets.Ticket) -> steps.Plan:
    """A generated plan, validated by the same schema the derived one meets.

    The planner writes `steps.jsonl` inside its own scope; Python reads it
    back through `steps.Plan.load`, which already rejects a line that is not
    valid JSON or is missing `id`, `ticket`, `role`, `action`, or
    `validation`. Nothing here invents a field.
    """
    maker = getattr(backend, "plan", None)
    if maker is None:
        raise steps.PlanRejected("this backend has no planner graph")
    # The DoerResult itself is discarded: neither `.ok` nor `.wrote` is
    # checked, only the file `Plan.load` reads back next. That is only safe
    # because this path never runs on a resume -- `_worktree` resets the
    # worktree to HEAD before every non-resume run, so a planner that wrote
    # nothing (or failed) cannot be masked by a stale `steps.jsonl` left
    # over from an earlier attempt. `Plan.load` then sees only this call's
    # own output, or the file's absence.
    maker(repo=repo, prompt=ticket.for_prompt())
    return steps.Plan.load(repo)


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


def _worktree(repo: Path, ticket_id: str, *, resume: bool = False) -> Path:
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
    path, which is what `--resume` (A6) reads back. A path that exists but
    is not a registered worktree is a leftover, and `git worktree add` never
    runs on top of one.

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

    # A6 (#433). A resume with no worktree at all has nothing to read back:
    # fail here, before `path.parent.mkdir` or any git command runs, rather
    # than silently starting a fresh run under `--resume`'s name.
    if resume and not path.exists():
        raise ContractError(
            f"nothing to resume for {ticket_id}: no worktree at {path}. "
            "Run without --resume first."
        )

    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        if path.resolve() != path or path.resolve() not in registered:
            raise ContractError(
                f"{path} exists but is not a registered git worktree of {repo}. "
                "Remove it by hand, or run a different --ticket."
            )
        if resume:
            # A6 (#433). A resume never resets. The whole point is to pick up
            # the killed run's own code -- and the checkpoint in `run()`'s
            # `state.json` that describes it -- not throw both away the way
            # the branch below does for an ordinary reused worktree.
            pass
        else:
            # Reused, and this is not a resume: reset the worktree to HEAD
            # before the baseline, rather than carrying the last attempt's
            # code forward. -fd, not -x, so a gitignored .venv the bootstrap
            # step symlinked in is left alone.
            #
            # state.json is cumulative across runs of this ticket (A5's
            # `runs` counter, and the corrupt-state guard that reads it
            # before this run does anything), and survives the reset on
            # purpose. `.harness` is untracked and `git clean -fd` removes it
            # along with everything else, so its bytes are captured before
            # either git command runs, not after. Everything else in
            # .harness describes only the run that just ended.
            harness_dir = path / ".harness"
            state_path = harness_dir / "state.json"
            saved_state = state_path.read_bytes() if state_path.is_file() else None
            _git(path, "reset", "--hard", "HEAD")
            _git(path, "clean", "-fd")
            if harness_dir.exists():
                shutil.rmtree(harness_dir)
            if saved_state is not None:
                harness_dir.mkdir(parents=True, exist_ok=True)
                state_path.write_bytes(saved_state)
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
    if not resume:
        # A6 (#433) fold-in. A resume's worktree already holds the ticket the
        # killed run used. Re-copying it would pull in any enhancer edit made
        # between the kill and the resume, and that edit would then show up
        # as an untracked diff to `tickets/<id>.md` -- a path neither the
        # test nor code implementer's scope covers, so it would read as a
        # scope violation for a file this loop never asked either role to
        # touch.
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
    planner: str = "derived",
    budget: int | None = None,
    write_trace: bool = True,
    cleanup: bool = False,
    resume: bool = False,
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

    `resume=True` reads that worktree's own `state.json` instead of starting
    over: `_worktree` skips its usual reset, and this function skips the test
    phase entirely when the stored `phase` says it already went green,
    restoring `preexisting`, the test phase's own files, and `red_ids` from
    the checkpoint rather than recomputing them from a worktree `--resume`
    left dirty on purpose. `_worktree` also skips re-copying the ticket on a
    resume: the worktree already holds the ticket the killed run used, and
    an enhancer edit made between the kill and the resume would otherwise
    show up as an untracked diff to a path neither role's scope covers.

    `_write_checkpoint` and `_finish` both write `state.json` from the
    values this function computed, never by merging whatever is already on
    disk, and both refuse to trust a `state.json` that changed since this
    run's own last write of it (`_state_tampered`). Live doers are fenced
    from `.harness/` by their role's own tool restrictions, so only an
    offline scripted backend -- exactly what this file's own tests use --
    can reach `state.json` directly; a real doer with a live key cannot.

    `planner` (A9, #437 #422) chooses step 2. `derived` is `plan_for`: no
    model, and the default. Any other value reads the plan back from the
    doer's own `plan()` graph through `_plan_from_backend`, still validated
    by the same schema. `doer` `none` or `reference` forces `derived`
    regardless of this flag, because a live planner with no live doer
    produces a plan nothing can execute. A resumed run never re-plans: it
    loads the worktree's own `steps.jsonl`, whichever planner wrote it.
    """
    contract = Contract(repo)
    contract.validate()
    source_repo = contract.repo

    worktree = _worktree(source_repo, ticket_id, resume=resume)
    contract = Contract(worktree)
    target = contract.repo

    # A corrupt state.json is never a fresh start: fail closed before the
    # ticket loads, before the baseline test runs, before any backend call.
    state_path = target / ".harness" / "state.json"
    previous_state = _read_state(state_path)
    previous_runs = previous_state.get("runs", 0) if previous_state else 0
    # ponytail: the tamper check below can only compare against bytes this
    # process itself wrote or read. A forge followed by a kill before the
    # loop's next write leaves no earlier-known-good copy to fall back to,
    # and the next --resume reads the forged file as-is. Closing that needs
    # a second, append-only copy of state.json outside the doer's reach;
    # not built here.
    last_state_bytes = state_path.read_bytes() if state_path.is_file() else None

    # A6 (#433). Nothing to resume is fail-closed for the same reason, and
    # checked at the same point. `_worktree` above already refused a resume
    # with no worktree at all; these two are the cases where a worktree can
    # still exist and nothing is left to resume: no run ever checkpointed a
    # phase, or the last one already reached the terminal gate a resume
    # exists to avoid replaying.
    if resume and previous_state is None:
        raise ContractError(f"nothing to resume for {ticket_id}: no state.json in {target}")
    if resume and previous_state.get("last_gate") == gates.PASS:
        raise ContractError(f"nothing to resume for {ticket_id}: the last run already passed")

    the_ticket = tickets.load(target, ticket_id, contract.tickets.get("path", "tickets"))
    if not the_ticket.ready:
        raise ContractError(f"{ticket_id} is not ready. Run the enhancer first.")

    cast = roles.build(contract)
    boss: roles.Orchestrator = cast["orchestrator"]
    if budget:
        boss.budget_iterations = budget

    backend = doers.build(doer)

    # A9 (#437 #422). derived is plan_for; sdk/deep read the plan back from
    # the doer's own planner graph through `_plan_from_backend`. `none` and
    # `reference` force derived: a live planner with no live doer produces a
    # plan nothing can execute. A resumed run never re-plans -- it loads the
    # worktree's own steps.jsonl, or a regenerated plan would renumber the
    # steps the stored `red_ids` were proven against.
    effective_planner = "derived" if backend.name in CLASSROOM_DOERS else planner
    try:
        if resume:
            plan = steps.Plan.load(target)
        elif effective_planner == "derived":
            plan = plan_for(the_ticket)
        else:
            plan = _plan_from_backend(backend, repo=target, ticket=the_ticket)
        plan.validate(criteria=the_ticket.criterion_ids)
    except steps.PlanRejected as exc:
        # Fail closed, never a crash and never a skipped red gate. A5's
        # ContractError wrapper in main() does not catch a PlanRejected
        # (it is a ValueError, not a ContractError), so it is caught here.
        trace = {
            "ticket": the_ticket.id,
            "repo": str(target),
            "doer": backend.name,
            "gate": gates.ESCALATE,
            "reason": f"the planner produced an unusable plan: {exc}",
        }
        return _finish(
            contract, trace, write_trace,
            phase="test", red_ids=set(), preexisting=set(),
            test_phase_files=set(), test_phase_attempts=0,
            last_written=last_state_bytes,
            source_repo=source_repo, cleanup=cleanup, previous_runs=previous_runs,
        )
    plan.save(target)

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

    harness_dir = target / ".harness"

    # A6 (#433). Restore, never recompute, when resuming: `preexisting` was
    # honest the moment the checkpoint below first wrote it, before anything
    # in this run touched the tree. Recomputing it now would read a worktree
    # `--resume` deliberately left dirty (Grok suggestion 4): a live doer's
    # own test files would be folded into `preexisting`, hiding them from
    # the `changed` list `rubric.score` scores in the code loop.
    resume_into_code = resume and previous_state.get("phase") == "code"
    if resume:
        preexisting = set(previous_state.get("preexisting") or [])
    else:
        # Whatever was already dirty is not this loop's doing. The enhancer
        # edits tickets before the implementer runs, and blaming this loop
        # for that would fail write_scope for a change it never made.
        preexisting = {
            path for path in rubric.changed_files(target) if not _is_loop_bookkeeping(path)
        }

    if resume_into_code:
        # A completed, checkpointed test phase. Skip it: replaying it would
        # call the test-implementer backend again for no reason, and risks
        # rewriting a test file the red gate already proved.
        red_ids = set(previous_state.get("red_ids") or [])
        after_test_phase = set(previous_state.get("test_phase_files") or [])
        scope_violations: list[str] = []
        test_phase_attempts = previous_state.get("test_phase_attempts", 0)
        trace["red_ids"] = sorted(red_ids)
        trace["test_phase"] = {
            "attempts": test_phase_attempts,
            "files": sorted(after_test_phase),
            "violations": [],
            "resumed": True,
        }
    else:
        # Step 3. Tests first. The test implementer owns tests/ and nothing
        # else. A red-gate miss retries inside this loop's own attempt
        # counter rather than escalating on the first empty attempt. This
        # never calls `boss.start_iteration()`: that counter belongs to the
        # code loop below, and sharing it would spend the code budget on
        # test turns. A resumed replay continues the attempt count a killed
        # run's own checkpoint left behind, rather than starting back at 1.
        tester = cast["test_implementer"]
        attempt = previous_state.get("test_phase_attempts", 0) if resume else 0
        previous_test_signature: tuple[str, ...] | None = None
        while True:
            attempt += 1
            test_result = backend.run(
                repo=target, prompt=_test_prompt(the_ticket, plan), allow=list(tester.scope.allow)
            )
            boss.spend(test_result.usd)
            after_tests = contract.run("test")
            red_ids = _new_test_ids(known_ids, after_tests.junit.failed_ids)

            # Attribute writes by phase, not by what a backend claims. Files
            # that appear during the test phase belong to the test
            # implementer; files that appear later belong to the code
            # implementer. A backend that lies about `wrote` cannot move a
            # file out of its phase.
            after_test_phase = {
                path
                for path in rubric.changed_files(target)
                if not _is_loop_bookkeeping(path) and path not in preexisting
            }
            scope_violations = tester.violations(sorted(after_test_phase))
            trace["test_phase"] = {
                "attempts": attempt,
                "wrote": list(test_result.wrote),
                "files": sorted(after_test_phase),
                "violations": list(scope_violations),
                "ok": test_result.ok,
                "usd": test_result.usd,
            }
            # A6 (#433). Checkpointed before the next line can escalate, or
            # this process can be killed outright, so a resume always finds
            # a phase to read: "test" until the red gate is satisfied,
            # "code" once it flips just below the loop. Judge of PR #500,
            # second finding: this read-back happens before the write, so a
            # doer that reached `.harness/state.json` since the loop's own
            # last write of it (`last_state_bytes`) is caught here, not
            # trusted.
            last_state_bytes, tampered = _write_checkpoint(
                harness_dir,
                phase="test",
                red_ids=red_ids,
                preexisting=preexisting,
                test_phase_files=after_test_phase,
                test_phase_attempts=attempt,
                last_written=last_state_bytes,
            )
            if tampered:
                scope_violations = sorted(set(scope_violations) | {_STATE_FILE})
                trace["test_phase"]["violations"] = list(scope_violations)

            # Step 4. The red gate. A scope violation escalates on the turn
            # it happens; the test phase never gets a second try to stay in
            # scope. A tampered state.json is folded into the same
            # violations set above, so it escalates through this one path.
            if scope_violations:
                trace["test_phase_scope_violations"] = sorted(scope_violations)
                trace["scope_violations"] = sorted(scope_violations)
                trace["gate"] = gates.ESCALATE
                trace["reason"] = (
                    "test phase wrote outside its scope: " + ", ".join(sorted(scope_violations))
                )
                trace["red_ids"] = sorted(red_ids)
                return _finish(
                    contract, trace, write_trace,
                    phase="test", red_ids=red_ids, preexisting=preexisting,
                    test_phase_files=after_test_phase, test_phase_attempts=attempt,
                    last_written=last_state_bytes,
                    source_repo=source_repo, cleanup=cleanup, previous_runs=previous_runs,
                )

            if not contract.rubric.get("require_red", True) or red_ids:
                break

            # Still no red. Retry while the attempt budget allows it, and
            # reuse the code loop's own stop rule (gates.decide) rather than
            # writing a second one: two attempts that touch the same files
            # are not converging, and stop as a stable failure before the
            # budget runs out.
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
                # A stop here is either a stable failure, the money budget,
                # or the iteration budget. The first two name a real reason
                # worth keeping (the money one is a fold-in fix from A5:
                # `decide` already says "the money budget is spent", and
                # this branch used to overwrite that with the generic
                # red-gate wording below). A stable failure with an empty
                # signature gets the test phase's own wording, folded in
                # from the judge of PR #490: `gates.decide`'s generic
                # wording names the signature as "unknown", which reads as a
                # bug in the trace rather than what actually happened -- two
                # turns that wrote nothing at all. Only a plain
                # iteration-budget exhaustion falls through to the red-gate
                # wording.
                if decision.repeat_failure:
                    trace["reason"] = (
                        decision.reason
                        if signature
                        else "two test turns wrote nothing. The loop is not converging."
                    )
                elif boss.usd_left <= 0:
                    trace["reason"] = decision.reason
                else:
                    trace["reason"] = (
                        "red gate: no new test was observed failing. A test that passes before "
                        "any code exists proves nothing."
                    )
                trace["red_ids"] = []
                trace["scope_violations"] = list(scope_violations)
                return _finish(
                    contract, trace, write_trace,
                    phase="test", red_ids=red_ids, preexisting=preexisting,
                    test_phase_files=after_test_phase, test_phase_attempts=attempt,
                    last_written=last_state_bytes,
                    source_repo=source_repo, cleanup=cleanup, previous_runs=previous_runs,
                )
            previous_test_signature = signature

        trace["red_ids"] = sorted(red_ids)
        test_phase_attempts = attempt
        last_state_bytes, tampered = _write_checkpoint(
            harness_dir,
            phase="code",
            red_ids=red_ids,
            preexisting=preexisting,
            test_phase_files=after_test_phase,
            test_phase_attempts=attempt,
            last_written=last_state_bytes,
        )
        if tampered:
            trace["gate"] = gates.ESCALATE
            trace["reason"] = "test phase wrote outside its scope: " + _STATE_FILE
            trace["scope_violations"] = [_STATE_FILE]
            trace["red_ids"] = sorted(red_ids)
            return _finish(
                contract, trace, write_trace,
                phase="test", red_ids=red_ids, preexisting=preexisting,
                test_phase_files=after_test_phase, test_phase_attempts=attempt,
                last_written=last_state_bytes,
                source_repo=source_repo, cleanup=cleanup, previous_runs=previous_runs,
            )

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
            if not _is_loop_bookkeeping(c) and c not in preexisting
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
    return _finish(
        contract, trace, write_trace,
        phase="code", red_ids=red_ids, preexisting=preexisting,
        test_phase_files=after_test_phase, test_phase_attempts=test_phase_attempts,
        last_written=last_state_bytes,
        source_repo=source_repo, cleanup=cleanup, previous_runs=previous_runs,
    )


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


# A6 (#433). Expected types for the keys `_read_state` will hand back. A
# `state.json` that parses as JSON but carries the wrong shape for one of
# these is corrupt in the same sense A5 already treats a truncated file: it
# raises here, before any work starts, rather than crashing later on an
# arithmetic or membership check that assumed the shape held. Folded in from
# the judge of PR #497: a string `runs` used to reach `previous_runs + 1` and
# raise `TypeError` well after the corrupt-state guard was supposed to catch
# it.
_STATE_FIELD_TYPES: dict[str, type | tuple[type, ...]] = {
    "runs": int,
    "last_gate": str,
    "last_reason": (str, type(None)),
    "last_run_at": (int, float),
    "loop": str,
    "phase": str,
    "red_ids": list,
    "preexisting": list,
    "test_phase_files": list,
    "test_phase_attempts": int,
}


def _read_state(path: Path) -> dict | None:
    """The previous `state.json`, or None the first time this ticket runs.

    A file that exists but will not parse, or parses but holds the wrong
    type for a field this module reads, is corrupt, and a corrupt state is
    never a fresh start: raise so the caller fails closed before a single
    baseline test runs, let alone a backend call.
    """
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ContractError(f"{path} is corrupt: {exc}") from exc
    if not isinstance(payload, dict):
        raise ContractError(f"{path} is corrupt: not a JSON object")
    for key, expected in _STATE_FIELD_TYPES.items():
        if key in payload and not isinstance(payload[key], expected):
            raise ContractError(f"{path} is corrupt: {key!r} is not a {expected}")
    return payload


def _write_checkpoint(
    harness_dir: Path,
    *,
    phase: str,
    red_ids,
    preexisting,
    test_phase_files,
    test_phase_attempts: int,
    last_written: bytes | None = None,
) -> tuple[bytes, bool]:
    """A resume-only checkpoint, written before this process might be killed.

    Merged onto whatever `state.json` already holds, so a previous run's
    `runs`, `last_gate`, `last_reason`, and `last_run_at` survive; only the
    fields a `--resume` needs to re-enter mid-run are replaced. `_finish`'s
    own write, at the true end of a run, writes these same fields fresh from
    `run()`'s own values (never by merging), so the terminal `state.json`
    still names the phase and files a resume would need if that run itself
    ended in an escalate rather than a pass.

    Returns the bytes just written, and whether the file had already been
    tampered with (`_state_tampered`) before this write -- the caller is the
    one that knows which phase is running, so it decides how to escalate.
    """
    harness_dir.mkdir(parents=True, exist_ok=True)
    state_path = harness_dir / "state.json"
    tampered = _state_tampered(state_path, last_written)
    state = _read_state(state_path) or {}
    state.update(
        {
            "phase": phase,
            "red_ids": sorted(red_ids),
            "preexisting": sorted(preexisting),
            "test_phase_files": sorted(test_phase_files),
            "test_phase_attempts": test_phase_attempts,
        }
    )
    payload = json.dumps(state, indent=2).encode("utf-8")
    state_path.write_bytes(payload)
    return payload, tampered


def _finish(
    contract: Contract,
    trace: dict,
    write_trace: bool,
    *,
    phase: str,
    red_ids,
    preexisting,
    test_phase_files,
    test_phase_attempts: int,
    last_written: bytes | None = None,
    source_repo: Path | None = None,
    cleanup: bool = False,
    previous_runs: int = 0,
) -> dict:
    trace.setdefault("gate", gates.ESCALATE)
    if write_trace:
        out = contract.repo / ".harness"
        out.mkdir(parents=True, exist_ok=True)
        state_path = out / "state.json"
        if _state_tampered(state_path, last_written):
            # Judge of PR #500, second finding. A doer that forges
            # state.json on a code turn is never checkpointed mid-loop (the
            # code loop has none), so this terminal read-back is the first
            # chance to catch it. Escalate through the same wording the
            # test phase already uses, whichever phase this call names.
            trace["gate"] = gates.ESCALATE
            trace["reason"] = f"{phase} phase wrote outside its scope: {_STATE_FILE}"
            trace["scope_violations"] = sorted(
                set(trace.get("scope_violations") or []) | {_STATE_FILE}
            )
        trace["written_at"] = time.time()
        (out / "last-implementer.json").write_text(json.dumps(trace, indent=2), encoding="utf-8")
        exit_code = 0 if trace.get("gate") == gates.PASS else 1
        receipt.write(contract.repo, exit_code, list(trace.get("red_ids") or []))
        # Every key, written fresh from what `run()` itself computed this
        # call -- never merged from whatever is on disk. A merge is exactly
        # what let a doer's forged `red_ids` and `preexisting` survive into
        # the next `--resume` (judge of PR #500): only `runs` needs the old
        # file at all, and that value came from `previous_runs`, captured at
        # the head of `run()`, not from this read.
        state = {
            "runs": previous_runs + 1,
            "last_gate": trace.get("gate"),
            "last_reason": trace.get("reason"),
            "last_run_at": trace["written_at"],
            "loop": LOOP,
            "phase": phase,
            "red_ids": sorted(red_ids),
            "preexisting": sorted(preexisting),
            "test_phase_files": sorted(test_phase_files),
            "test_phase_attempts": test_phase_attempts,
        }
        state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
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
        help="none | reference | reference:<ref> | judge-no",
    )
    parser.add_argument(
        "--planner",
        default="derived",
        help=(
            "derived | sdk | deep. derived is plan_for and calls no model. "
            "--doer none or reference forces derived regardless of this flag."
        ),
    )
    parser.add_argument("--budget", type=int, default=None)
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="remove the worktree after the run. Never automatic otherwise.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="re-enter the last killed run from its own state.json, instead of starting over.",
    )
    args = parser.parse_args(argv)

    try:
        trace = run(
            repo=args.repo,
            ticket_id=args.ticket,
            doer=args.doer,
            planner=args.planner,
            budget=args.budget,
            cleanup=args.cleanup,
            resume=args.resume,
        )
    except ContractError as exc:
        print(f"error: {exc}")
        return 1

    print(trace.get("rubric", ""))
    print()
    print(f"gate: {trace['gate']}")
    print(f"reason: {trace['reason']}")
    _print_worktree_status(trace)
    return 0 if trace["gate"] == gates.PASS else 2


if __name__ == "__main__":
    raise SystemExit(main())
