# Ticket Implementer

Sunday ships a one-shot stub: `run.py`.

```bash
export PYTHONPATH="$PWD/crm"
python harness/loops/implementer/run.py
```

With no `ANTHROPIC_API_KEY`, it skips the model and runs the hidden grader.
That is enough to prove fail then pass.

Module 1 shrinks this to one live pass.
Module 2 wraps it with Maker, Checker, rubric, and gates.
