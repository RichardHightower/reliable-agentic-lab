---
name: test-sol1-ticket-enhancer
description: "Test any standalone `solutions/sol1_*enhancer*` ticket-enhancer demo end to end: reset and seed its GitHub test tickets, run one poll, inspect live issues and diagnostics, post reviewer `LGTM` through the browser, and verify the ready or fail-closed exits. Use when asked to test, demo, smoke-test, or compare a sol1 ticket-enhancer runtime such as Claude Code, Agent SDK, Codex, Grok, or OpenCode."
---

# Test a sol1 ticket enhancer

Run this workflow from the selected standalone solution folder. Do not turn it
into a shared test framework; each `solutions/sol1_*` folder owns its commands
and runtime.

## Scope and preparation

1. Set `SOLUTION` to the requested solution folder, for example
   `solutions/sol1_enhancer_agent_sdk`.
2. Read that folder's `Taskfile.yml`, `HOW_TO_RUN.md`, and `SPEC.md` before
   using its live commands. Confirm its configured fork and target checkout.
3. Run the deterministic checks first:

   ```bash
   cd "$SOLUTION"
   task test
   task checks
   ```

4. Use `task setup` and `task clone` only when the folder requires them and
   they have not already been completed. Never use the shared `Saturday`
   solution as the target when testing a take-home port.

## Start a fresh live scenario

`reset-test-tickets` changes GitHub issues: run it only against the designated
test fork and only with the user's authorization for the live reset.

```bash
cd "$SOLUTION"
task reset-test-tickets
task create-test-tickets
task run --
```

`task run --` polls; it does not create issues. `task create-test-tickets`
opens the demo issues. Do not close individual issues by hand as a substitute
for reset: the reset task retires them and clears local state consistently.

For a long-running observation, use the solution's `task poll-forever --` only
when the user asks for continuous polling. Otherwise use bounded single polls.

## Watch the first poll

Capture the terminal output and inspect `.harness/` before rerunning anything.
For the Agent SDK port, a hung SDK query is capped at 180 seconds and its raw
events are written to `.harness/last-doer-T<id>.md`.

The seeded scenario normally contains:

| Ticket | Expected role in the test |
| --- | --- |
| T001 | Feature: due dates; should become a complete ticket. |
| T900 | Bug: empty-query search; may fail closed as `needs-human`. |
| T901 | UI: customer notes; should include a readable ASCII wireframe. |
| T902 | Feature: task CSV export; should become a concrete CSV contract. |

Treat the run as healthy when at least three tickets are enhanced and an
unhealthy ticket is isolated rather than stalling later tickets. A per-ticket
timeout, malformed candidate, budget exhaustion, or no-progress stop must add
`needs-human` for that issue and the poll must continue to the next ticket.

## Review the actual GitHub issues

Use the browser when the user asks to review or approve the issues.

1. Claim the existing test-fork issue tab if it is already open; otherwise
   navigate directly to the known issue URL.
2. Inspect the issue body and newest enhancer comment. Do not approve an issue
   merely because it has an `enhanced` label.
3. Confirm the draft is specific to `app/`, not generic product prose:

   - A feature or bug has **Problem**, **Proposal**, **Value**, and numbered
     `(AC-n)` acceptance criteria.
   - A UI ticket has those sections plus a readable ASCII wireframe. It must
     contain real lines and spaces, never literal `\\n`, `\\t`, or `\\r` text.
   - Acceptance criteria name concrete routes, files, fields, response
     behavior, or observable UI behavior appropriate to the ticket.
   - The issue body itself has the full draft; an internal tool dump, a Grep
     result, or a code fence alone is a failed candidate.

4. If the browser appears stale, reload once and re-inspect before acting. If
   an authoritative GitHub API check is available, use it to resolve a
   browser-rendering mismatch; do not mark an unverified draft `LGTM`.

## Approve with `LGTM`

Posting a comment changes the external test issue. Obtain explicit user
authorization before submitting it unless the user already asked to mark the
specific reviewed tickets `LGTM`.

For every verified ticket to approve:

1. Open the issue's **Add a comment** form.
2. Enter exactly `LGTM`—no punctuation or extra review text.
3. Submit **Comment** and confirm the new comment appears.

Approve only the complete tickets. Leave an incomplete ticket unapproved so its
failure path remains visible. Do not use `LGTM` to try to start an enhancement;
it releases a ticket only after the rubric is green.

Run one more poll:

```bash
cd "$SOLUTION"
task run --
```

For each approved green ticket, verify all of the following:

- terminal result is `passed` with the LGTM-ready reason;
- GitHub carries the `ready` label;
- the local ticket front matter is `state: ready` and `loop: implementer`.

For the unapproved green tickets, expect `waiting` and no repeated doer call.
For a failed ticket, expect `needs-human`, no hang, and continued processing of
later tickets.

## Diagnose a failure before changing code

Record the ticket id, issue URL, outcome line, labels, newest comment, and any
matching `.harness/last-doer-T<id>.md` file. Classify the break at one boundary:

- **No issue:** run `task create-test-tickets`; do not expect `task run` to
  create it.
- **Hang or timeout:** retain the raw diagnostic; verify later tickets ran.
- **Bad issue body:** compare the doer raw payload, candidate extraction, and
  GitHub body. Reject escaped layout or non-ticket tool output.
- **Waiting after approval:** verify the newest human comment is exactly
  `LGTM` and the rubric is green.
- **Unexpected ready:** check that the issue was reviewed and the local ticket
  moved to the implementer loop.

Report the per-ticket results and evidence first. Do not reset tickets again
until the user asks for another fresh run.
