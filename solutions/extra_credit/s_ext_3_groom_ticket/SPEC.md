# Spec. Extra credit 3. Groom a ticket from GitHub Actions

The Module 1 enhancer, started by an issue event. The judge does not change.

Stub: `labs/extra-credit/ext_3_groom_ticket/groom_ticket.py`.
Answer: `groom_ticket.py` in this folder.

## Build it step by step

1. Read one issue by number with `github_api.GitHub`.

2. Turn the issue into a `Ticket`.

   A GitHub issue is a title and a body. `ticket.parse` wants one markdown
   document, so join them. `_as_ticket` in the answer does this.

3. Judge it with `criteria.judge` in this folder. Do not write a second judge.

4. Act on the verdict.

   Ready means add the `ready` label and comment. Not ready means comment the
   missing parts, one bullet each.

5. Count attempts with an `agent-attempts-N` label. At the budget, comment that
   you stopped and why, then exit.

6. Skip the run when `agent-in-progress` is already on the issue. Clear the label
   in a `finally` block, so a crash does not wedge the issue.

7. Write `work/last-groom.json`.

## Verify

```bash
python solutions/extra_credit/s_ext_3_groom_ticket/groom_ticket.py --issue T001 --incorporate
task test
```

`tests/test_groom_ticket.py` drives the GitHub path with `fake_github.py`, so it
needs no token.
