# Instructions

Fill the four functions in `labs/m2-harness/harness.py`.

```bash
PYTHONPATH=labs/m2-harness python labs/m2-harness/harness.py --maker none
```

Then prove retry:

```bash
PYTHONPATH=labs/m2-harness python labs/m2-harness/harness.py --maker reference
```


Pass means: gate is pass, retry, or escalate, with a budget of 3 and repeat-failure detection

If you stall, open `FALL-BEHIND.md`.
