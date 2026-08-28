# Spec. Extra credit 4. Repair a pull request from GitHub Actions

The Module 4 fixer, started by a failed check suite. The loop does not change.

Stub: `labs/extra-credit/ext_4_fix_pr/fix_pr.py`.
Answer: `fix_pr.py` in this folder.

## Build it step by step

1. Read the pull request by number with `github_api.GitHub`.

2. Call `fixer.run` from this folder with the target repo. It takes `repo`, `doer`, and
   `budget`, and it returns a trace whose `green` key says whether the suite
   passed.

3. Count attempts with an `agent-attempts-N` label. Stop at the budget.

4. Skip the run when `agent-in-progress` is already set, and clear the label in a
   `finally` block.

5. Comment when you give up. A loop that stops silently is worse than one that
   fails loudly, because nobody learns it stopped.

6. Write `work/last-fix.json`.

## Verify

```bash
python solutions/extra_credit/s_ext_4_fix_pr/fix_pr.py --pr T001 --doer reference
task test
```

The local run needs the cloned target repo. `tests/test_fix_pr.py` skips without
it rather than failing, because a missing clone is not a broken fixer.
