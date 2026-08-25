# Module 4 solution: unattended production loop

Same stack. No human at the keyboard. GitHub Actions runs the harness with a budget.
State is a JSON file: ticket, branch, trace id, last score.

```bash
python solutions/m4-production/run_unattended.py --target m2
python solutions/m4-production/run_unattended.py --target m3
```

Workflow: `.github/workflows/unattended.yml`
