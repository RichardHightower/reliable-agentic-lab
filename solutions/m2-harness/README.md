# Module 2 solution: evaluation harness

Wraps the Ticket Implementer. Maker writes CRM files. Checker has no write tools.
Python holds the loop. Hidden pytest is the grader.

```bash
PYTHONPATH=solutions/m2-harness python -m loops.implementer --maker none
PYTHONPATH=solutions/m2-harness python -m loops.implementer --maker reference
pytest solutions/m2-harness/tests solutions/m2-harness/graders -q
```

Exit: pass, max loops, repeated failure signature.
