# Extra credit 4. Repair a broken pull request from GitHub Actions

The Module 4 fixer, started by a failed check suite instead of by you.

## Fill

`fix_pr.py` in this folder.

## What it must do

1. Read the pull request by number through the GitHub API.
2. Repair it with `loops.fixer`. The loop does not change, only the trigger.
3. Count attempts with an `agent-attempts-N` label. Stop at the budget.
4. Skip the run when `agent-in-progress` is already set.
5. Comment when it gives up. Silence is the worst outcome.
6. Write `work/last-fix.json`.

## Copy the workflow onto your fork

```bash
cp labs/extra-credit/ext_4_fix_pr/workflows/fix-broken-pr.yml \
   .github/workflows/fix-broken-pr.yml
```

Do not enable it on the instructor repo.

## Verify

```bash
python solutions/extra_credit/s_ext_4_fix_pr/fix_pr.py --pr T001 --doer reference
```

## Answer

`solutions/extra_credit/s_ext_4_fix_pr/`.
