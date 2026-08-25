# Module 4 troubleshooting

## Actions cannot import loops.implementer

The workflow must install `solutions/crm/requirements.txt` and set
`PYTHONPATH` the same way the local runner does.

## state.json is missing on the job

It is gitignored. Upload it as an artifact. That is the production record.

## Schedule fired while you were demoing

Use `workflow_dispatch` on Saturday. The cron is for after they go home.
