# Instructions

From the repo root:

```bash
python -m solutions.loops enhancer --ticket T001 --incorporate
python -m solutions.loops implementer --maker reference
python -m solutions.loops fixer --maker reference
```

Each command writes a trace under `solutions/loops/work/`.

Pass:

- Enhancer: T001 has the `ready` label
- Implementer: hidden grader green and `PR-T001` exists
- Fixer: the PR is passing, or a give-up comment is on the PR
