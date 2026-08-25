# Module 4 setup

Local:

```bash
python solutions/m4-production/run_unattended.py --target m2
python solutions/m4-production/run_unattended.py --target m3
```

Actions: `.github/workflows/unattended.yml`

Triggers:

- `workflow_dispatch` with target `m2` or `m3`
- `pull_request`
- weekday schedule

GitHub account with Actions enabled is already a workshop prereq.
