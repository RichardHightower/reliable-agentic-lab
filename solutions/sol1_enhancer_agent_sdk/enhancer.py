#!/usr/bin/env python3
"""One poll-and-act step for the ticket enhancer, in Python.

The plugin port drives this loop from a skill, so a model reads the steps and
follows them. This port drives it from code. The model does two jobs only,
drafting and grading, and every decision that can be a fact instead of a
judgment call is computed here: `check_fields.py` decides ready, `check_stop.py`
decides the exits, and this module decides whether a draft is an improvement.

A stop condition trusted to a model's own judgment is a stop condition a model
can talk itself past. That is the whole point of splitting it this way.

The doer holds `Write` scoped to `tickets/**` by the PreToolUse hook in
`roles.py`, so it writes its own candidate file. The judge holds no write tool,
which is why it cannot grade its own draft. Both the backend and the GitHub
wrapper are constructor arguments, so the entire loop runs against fakes with no
SDK, no API key, and no network.
"""

from __future__ import annotations

import contextlib
import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import check_fields
import check_stop
import ticket as ticket_mod

BUDGET = 3
CANDIDATE_SUFFIX = ".enhancer-candidate.md"
LGTM = "LGTM"

# The doer writes here and nowhere else. It sits under `tickets/**`, which is
# the doer's declared scope, so the hook lets it through and lets nothing else.
DOER_ALLOW = ["tickets/**"]


class EnhancerError(RuntimeError):
    """The loop cannot continue for a reason a human has to fix."""


class TicketBlocked(RuntimeError):
    """Stop this one ticket and report why. The other tickets still run."""


# -- the Judge's reply ------------------------------------------------------

_FENCE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.S)


def parse_judge(text: str) -> dict:
    """Pull the Judge's `{kind, present_fields}` object out of its reply.

    The agent is told to reply with one JSON object and nothing else. Models
    wrap it in a fence anyway, or add a sentence in front. Accepting those is
    not the same as accepting anything: a reply with no object at all, or one
    missing `kind`, has to fail loudly. Treating an unreadable verdict as an
    empty field list would silently mark every ticket unready and never say why.
    """
    fenced = _FENCE.search(text)
    raw = fenced.group(1) if fenced else _outermost_object(text)
    if raw is None:
        raise EnhancerError(f"the judge returned no JSON object: {text[:200]!r}")
    try:
        verdict = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise EnhancerError(f"the judge's JSON did not parse: {exc}") from exc
    if not isinstance(verdict, dict) or "kind" not in verdict:
        raise EnhancerError(f"the judge's JSON has no `kind`: {raw[:200]!r}")
    verdict.setdefault("present_fields", [])
    return verdict


def _outermost_object(text: str) -> str | None:
    """The first `{...}` that balances. `str.rfind` would eat a trailing brace."""
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    for index in range(start, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


# -- persisted state --------------------------------------------------------


@dataclass
class State:
    """What one ticket's earlier polls left behind.

    `last_comment_id` is what stops the loop acting on the same comment forever.
    A poll that never records the id it acted on acts on it again next time, and
    on every poll after that.
    """

    github_issue: int | None = None
    last_comment_id: str | None = None
    round: int = 0
    previous_signature: list[str] | None = None
    # True until a poll has saved this ticket's state at least once. Derived
    # from the file, never from `github_issue`: step 2 fills that in before
    # step 3 asks, so reading it there would make every first poll look like a
    # later one and wait forever for a comment that never comes.
    fresh: bool = True

    @staticmethod
    def path(repo: Path, ticket_id: str) -> Path:
        return Path(repo) / ".harness" / f"last-enhancer-{ticket_id}.json"

    @classmethod
    def load(cls, repo: Path, ticket_id: str) -> State:
        path = cls.path(repo, ticket_id)
        if not path.exists():
            return cls()
        raw = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            github_issue=raw.get("github_issue"),
            last_comment_id=(
                None if raw.get("last_comment_id") is None else str(raw["last_comment_id"])
            ),
            round=int(raw.get("round", 0)),
            previous_signature=raw.get("previous_signature"),
            fresh=False,
        )

    def save(self, repo: Path, ticket_id: str) -> None:
        path = self.path(repo, ticket_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        body = {key: value for key, value in self.__dict__.items() if key != "fresh"}
        path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")

    def clear(self, repo: Path, ticket_id: str) -> None:
        self.path(repo, ticket_id).unlink(missing_ok=True)

    @property
    def first_poll(self) -> bool:
        """A fresh ticket gets one round, so the human has something to react to."""
        return self.fresh


# -- GitHub -----------------------------------------------------------------


class Gh:
    """A thin `gh` wrapper. Every call names the repo, so nothing guesses.

    This is a class rather than free functions so a test can pass a stand-in
    with the same six methods and never reach the network.
    """

    def __init__(self, owner: str, repo: str):
        self.slug = f"{owner}/{repo}"

    def _run(self, *args: str) -> str:
        proc = subprocess.run(
            ["gh", *args], text=True, capture_output=True, check=False, timeout=120
        )
        if proc.returncode != 0:
            raise EnhancerError(f"gh {' '.join(args)} failed: {proc.stderr.strip()}")
        return proc.stdout.strip()

    def find_issue(self, ticket_id: str) -> int | None:
        """The ticket's issue, whatever state it is in.

        Never `--state open`. A closed issue is still that ticket's issue, and
        searching only the open ones is what makes the loop create a second
        issue for a title that already has one.
        """
        out = self._run(
            "issue",
            "list",
            "--repo",
            self.slug,
            "--search",
            f'in:title "[{ticket_id}]"',
            "--state",
            "all",
            "--json",
            "number",
        )
        found = json.loads(out or "[]")
        return int(found[0]["number"]) if found else None

    def is_closed(self, issue: int) -> bool:
        out = self._run("issue", "view", str(issue), "--repo", self.slug, "--json", "state")
        return json.loads(out or "{}").get("state", "").upper() == "CLOSED"

    def create_issue(self, title: str, body: str) -> int:
        for label, color in (
            ("enhanced", "fbca04"),
            ("ready", "0e8a16"),
            ("needs-human", "d93f0b"),
        ):
            # A label that already exists is not a reason to stop.
            with contextlib.suppress(EnhancerError):
                self._run(
                    "label", "create", label, "--repo", self.slug, "--color", color, "--force"
                )
        url = self._run(
            "issue",
            "create",
            "--repo",
            self.slug,
            "--title",
            title,
            "--body",
            body,
        )
        return int(url.rstrip("/").rsplit("/", 1)[-1])

    def latest_comment(self, issue: int) -> tuple[str, str] | None:
        out = self._run(
            "api",
            f"repos/{self.slug}/issues/{issue}/comments",
            "--jq",
            "sort_by(.id) | .[-1] | {id, body}",
        )
        if not out:
            return None
        payload = json.loads(out)
        return str(payload["id"]), payload.get("body", "")

    def comment(self, issue: int, body: str) -> None:
        self._run("issue", "comment", str(issue), "--repo", self.slug, "--body", body)

    def add_label(self, issue: int, label: str) -> None:
        self._run("issue", "edit", str(issue), "--repo", self.slug, "--add-label", label)

    def labels(self, issue: int) -> list[str]:
        out = self._run("issue", "view", str(issue), "--repo", self.slug, "--json", "labels")
        return [entry["name"] for entry in json.loads(out or "{}").get("labels", [])]

    def set_body(self, issue: int, body: str) -> None:
        self._run("issue", "edit", str(issue), "--repo", self.slug, "--body", body)


# -- tickets ----------------------------------------------------------------


def strip_front_matter(text: str) -> str:
    """The issue body, without the raw `---` block.

    GitHub renders an unrecognized front matter block as a stray horizontal
    rule followed by the YAML as prose, so a reviewer sees noise above the
    ticket they are supposed to judge.
    """
    match = ticket_mod.FRONT_MATTER.match(text)
    return text[match.end() :].strip() if match else text.strip()


def open_tickets(repo: Path, loop: str = "enhancer") -> list[ticket_mod.Ticket]:
    """Every draft ticket this loop owns.

    A `.ready.md` file is the answer, not the question. A candidate file is the
    doer's unjudged draft, and it carries the real ticket's `state: draft` and
    `loop: enhancer`, so a glob that does not exclude it hands the next poll a
    second copy of a ticket no judge ever accepted.
    """
    folder = Path(repo) / "tickets"
    if not folder.is_dir():
        raise EnhancerError(f"no tickets/ directory in {repo}")
    found = []
    for path in sorted(folder.glob("*.md")):
        if path.name.endswith((".ready.md", CANDIDATE_SUFFIX)):
            continue
        parsed = ticket_mod.parse(path.read_text(encoding="utf-8"), ticket_id=path.stem)
        parsed.path = path
        if parsed.state == "draft" and parsed.meta.get("loop") == loop:
            found.append(parsed)
    return found


def set_front_matter(path: Path, **fields: str) -> None:
    """Rewrite front matter keys in place, adding any that are not there yet.

    A file with no block gets one. The doer is told to keep the front matter and
    a model that drops it should cost one rewritten header, not a ticket this
    loop can no longer find.
    """
    text = path.read_text(encoding="utf-8")
    match = ticket_mod.FRONT_MATTER.match(text)
    if not match:
        body = text.lstrip("\n")
        header = "\n".join(f"{key}: {value}" for key, value in fields.items())
        path.write_text(f"---\n{header}\n---\n\n{body}", encoding="utf-8")
        return
    lines = match.group(1).splitlines()
    remaining = dict(fields)
    for index, line in enumerate(lines):
        key = line.partition(":")[0].strip()
        if key in remaining:
            lines[index] = f"{key}: {remaining.pop(key)}"
    lines += [f"{key}: {value}" for key, value in remaining.items()]
    path.write_text("---\n" + "\n".join(lines) + "\n---\n" + text[match.end() :], encoding="utf-8")


# -- the loop ---------------------------------------------------------------


@dataclass
class Outcome:
    """One ticket's result from one poll. The report prints these and nothing else."""

    ticket_id: str
    status: str
    detail: str = ""

    def __str__(self) -> str:
        return f"{self.ticket_id:<8}{self.status:<12}{self.detail}"


@dataclass
class Enhancer:
    """The orchestrator. It owns the budget, the order, and every write."""

    repo: Path
    backend: object
    gh: object
    budget: int = BUDGET
    prompts: dict = field(default_factory=dict)

    def _ask(self, prompt: str, allow: list[str] | None = None):
        return self.backend.run(repo=Path(self.repo), prompt=prompt, allow=allow or [])

    def judge(self, path: Path) -> dict:
        """Grade one ticket file. The judge holds no write tool, so `allow` is empty."""
        result = self._ask(
            "Use the judge subagent. Read the ticket at "
            f"{Path(path).relative_to(self.repo)} and reply with one JSON object "
            'of the shape {"kind": ..., "present_fields": [...]} and nothing else.'
        )
        if not result.ok:
            raise EnhancerError(f"the judge failed: {result.output}")
        verdict = parse_judge(result.output)
        return check_fields.check(verdict["kind"], verdict.get("present_fields", []))

    def draft(
        self, tkt: ticket_mod.Ticket, kind: str, missing: list[str], comment: str | None
    ) -> Path:
        """Have the doer write a candidate. It writes the file, the hook scopes it.

        The doer is the only role here that holds `Write`, and the PreToolUse
        hook in `roles.py` keeps it inside `tickets/**`. The candidate path is
        inside that scope, so the hook allows this and still blocks everything
        else, which is the whole reason this port exists.
        """
        candidate = Path(self.repo) / "tickets" / f"{tkt.id}{CANDIDATE_SUFFIX}"
        relative = candidate.relative_to(self.repo)
        told = (
            f"The latest comment on the issue says: {comment}"
            if comment
            else "There is no comment yet. Rely on your own reading of the app under app/."
        )
        result = self._ask(
            f"Use the doer subagent. Rewrite ticket {tkt.id}, a {kind} ticket that is "
            f"missing {', '.join(missing) or 'nothing'}. {told} "
            f"Keep the front matter exactly as it is. Write the full rewritten ticket "
            f"to {relative} and write nothing else.",
            allow=DOER_ALLOW,
        )
        if not result.ok:
            raise EnhancerError(f"the doer failed: {result.output}")
        if not candidate.exists():
            raise EnhancerError(f"the doer wrote no candidate at {relative}")
        return candidate

    def poll(
        self, ticket_id: str | None = None, *, simulate_comment: str | None = None
    ) -> list[Outcome]:
        """One poll over every open ticket, or over the one that was named."""
        if ticket_id:
            path = Path(self.repo) / "tickets" / f"{ticket_id}.md"
            if not path.exists():
                raise EnhancerError(f"no ticket {ticket_id} in {self.repo}/tickets")
            parsed = ticket_mod.parse(path.read_text(encoding="utf-8"), ticket_id=ticket_id)
            parsed.path = path
            # `--ticket` names a ticket to consider, it is not a reason to skip
            # the state check `open_tickets` applies to everything it finds.
            # Without this a finished ticket runs again as though it were a
            # fresh draft, and the re-run opens a second issue for it.
            if parsed.state != "draft" or parsed.meta.get("loop") != "enhancer":
                found = f"{parsed.state} / {parsed.meta.get('loop') or 'no loop'}"
                return [Outcome(ticket_id, "skipped", f"already {found}")]
            tickets = [parsed]
        elif simulate_comment is not None:
            raise EnhancerError("--simulate-comment needs --ticket, it acts on one ticket")
        else:
            tickets = open_tickets(Path(self.repo))
        outcomes = []
        for tkt in tickets:
            try:
                outcomes.append(self._one(tkt, simulate_comment))
            except TicketBlocked as blocked:
                outcomes.append(Outcome(tkt.id, "blocked", str(blocked)))
        return outcomes

    def _one(self, tkt: ticket_mod.Ticket, simulate_comment: str | None) -> Outcome:
        state = State.load(Path(self.repo), tkt.id)

        # 2. find the issue. Never create one. First hit wins, in this order: the state
        # file, the ticket frontmatter, then a title search across every state.
        # The frontmatter matters because it outlives the state file, which the
        # `LGTM` pass deletes.
        recorded = tkt.meta.get("github_issue")
        issue = state.github_issue or (int(recorded) if recorded else None) or self.gh.find_issue(
            tkt.id
        )
        if issue is not None and self.gh.is_closed(issue):
            # Somebody closed the issue for a ticket that is still a draft,
            # which is not how you reset one. Creating a second issue here is
            # the duplicate this whole lookup exists to prevent.
            raise TicketBlocked(f"issue {issue} is closed; reopen it")
        if issue is None:
            raise TicketBlocked(f"{tkt.id}: no GitHub issue; run task create-test-tickets")
        set_front_matter(tkt.path, github_issue=str(issue))
        state.github_issue = issue

        # 3. Newest human comment is only inspected for exact LGTM.
        # A comment never starts an enhance round. A missing comment never stops one.
        _comment_id, comment = self._human_comment(issue, simulate_comment)

        # 4. an escalated ticket waits for a human, not for another poll.
        if "needs-human" in self.gh.labels(issue):
            return Outcome(tkt.id, "escalated", "needs-human is already set")

        # 5. grade the real ticket. The rubric decides ready, never the comment.
        verdict = self.judge(tkt.path)

        # 6. decide from `ready` and LGTM only. Label after a real write, not here.
        if verdict["ready"] and (comment or "").strip() == LGTM:
            set_front_matter(tkt.path, state="ready", loop="implementer")
            self.gh.add_label(issue, "ready")
            state.clear(Path(self.repo), tkt.id)
            return Outcome(tkt.id, "passed", "rubric green and a human said LGTM")
        if verdict["ready"]:
            if "enhanced" not in self.gh.labels(issue):
                self.gh.add_label(issue, "enhanced")
            if state.last_comment_id != "asked-lgtm":
                self.gh.comment(issue, "This ticket meets the rubric. Comment `LGTM` to release it.")
                state.last_comment_id = "asked-lgtm"
                state.save(Path(self.repo), tkt.id)
            return Outcome(tkt.id, "waiting", "ready, waiting for LGTM")

        # 7. enhance because the ticket still needs work, not because someone commented.
        signature = self._improve(tkt, verdict, None, issue)

        # 8. the exits, computed rather than judged.
        stop = check_stop.check(state.round, self.budget, signature, state.previous_signature)
        if stop["stop"]:
            self.gh.add_label(issue, "needs-human")
            return Outcome(tkt.id, "escalated", stop["reason"])
        state.round += 1
        state.previous_signature = signature
        if not signature:
            state.last_comment_id = "asked-lgtm"
        state.save(Path(self.repo), tkt.id)
        return Outcome(
            tkt.id, "waiting", f"round {state.round}, still missing {', '.join(signature)}"
        )

    def _comment(self, state: State, issue: int, simulate: str | None):
        """Step 3. Returns (id, text), or the no-new-comment sentinel."""
        if simulate is not None:
            # A stable id, so the same simulated text is the same comment twice.
            comment_id = f"sim:{simulate}"
            if comment_id == state.last_comment_id:
                return _NO_NEW_COMMENT, None
            return comment_id, simulate
        if state.first_poll:
            # A fresh ticket always gets one round, with no comment and no id.
            return None, None
        newest = self.gh.latest_comment(issue)
        if newest is None:
            return _NO_NEW_COMMENT, None
        comment_id, text = newest
        if state.last_comment_id is not None and comment_id <= state.last_comment_id:
            return _NO_NEW_COMMENT, None
        return comment_id, text


    def _human_comment(self, issue: int, simulate: str | None):
        """Newest human comment, used only to detect LGTM. Never aborts a poll."""
        if simulate is not None:
            return f"sim:{simulate}", simulate
        newest = self.gh.latest_comment(issue)
        if newest is None:
            return None, None
        return newest

    def _improve(self, tkt, verdict: dict, comment: str | None, issue: int) -> list[str]:
        """Step 7. Keep the draft only when it strictly closes gaps.

        "Not worse" is not good enough. A draft that trades one missing field
        for another looks like motion and is how a loop spends its whole budget
        standing still.
        """
        before = set(verdict["missing_fields"])
        candidate = self.draft(tkt, verdict["kind"], verdict["missing_fields"], comment)
        try:
            after_verdict = self.judge(candidate)
            after = set(after_verdict["missing_fields"])
            if after < before:
                shutil.copyfile(candidate, tkt.path)
                # The doer is told to keep the front matter, and a model that
                # forgets would cost the loop the issue number it needs to find
                # this ticket again. The orchestrator owns these keys, so it
                # writes them back rather than trusting the draft to carry them.
                set_front_matter(
                    tkt.path, id=tkt.id, state="draft", loop="enhancer", github_issue=str(issue)
                )
                self.gh.set_body(issue, strip_front_matter(tkt.path.read_text(encoding="utf-8")))
                self.gh.add_label(issue, "enhanced")
                still = after_verdict["missing_fields"]
                self.gh.comment(
                    issue,
                    f"Filled {', '.join(sorted(before - after))}. "
                    + (f"Still missing {', '.join(still)}." if still else "Ready for `LGTM`."),
                )
                return sorted(after)
            self.gh.comment(
                issue,
                f"The draft did not clear the rubric for a {verdict['kind']} ticket. "
                f"Still missing {', '.join(verdict['missing_fields'])}.",
            )
            return sorted(before)
        finally:
            candidate.unlink(missing_ok=True)


class _NoNewComment:
    """A sentinel. `None` is a real comment id here, meaning "first poll"."""

    def __repr__(self) -> str:  # pragma: no cover  (debugging only)
        return "<no new comment>"


_NO_NEW_COMMENT = _NoNewComment()
