# Troubleshooting. Lab 2

## `ModuleNotFoundError: No module named 'loops'`

Your stub is missing its first import. Every stub starts with:

```python
import _root  # noqa: F401
```

`_root.py` sits in this folder and puts the repo root on `sys.path`. No
PYTHONPATH needed.

## `task: command not found`

Install Task. See [SETUP.md](../../SETUP.md).

## `task test` says no target repo

Run `task clone` from the repo root. The demo repository lands in `work/`.

## Your agent was refused a push

```
BLOCKED by pre-tool hook: git push
```

Working as designed. Run `task test`, get it green, push again. The gate reads
`.harness/receipt.json` and nothing else, and a receipt only counts when the
suite passed against exactly this tree.

## `NotImplementedError: fill me in`

That is the stub. Fill it.

## The loop escalates and you expected a pass

Read the reason it printed. It names the row that failed and why it stopped.
That reading is the skill this workshop is about, not a sign something broke.

## You are out of time

Stop and run `git checkout done-m2`. See [FALL-BEHIND.md](FALL-BEHIND.md).

## Something is genuinely broken

Tell Rick. A fresh clone plus `task setup` plus `task test` should be 129 green
checks, and anything else is a real bug.
