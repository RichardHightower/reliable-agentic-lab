# Extra credit setup

Finish root SETUP.md first.

```bash
export PYTHONPATH="$PWD"
python solutions/extra_credit/groom_ticket.py --issue T001 --incorporate
python solutions/extra_credit/fix_pr.py --pr T001 --maker reference
```

GitHub mode needs `GITHUB_TOKEN` and `GITHUB_REPO`. Copy workflows from `labs/extra-credit/workflows/` onto **your fork** only.
