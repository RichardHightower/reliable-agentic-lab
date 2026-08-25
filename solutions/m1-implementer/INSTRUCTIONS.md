# Module 1 instructions

From the repo root:

```bash
python solutions/m1-implementer/loop.py
```

Pass looks like:

```json
{ "passed": true, "files": ["app/dates.py", "app/main.py", "..."] }
```

`solutions/m1-implementer/PR.md` is written on a successful run.
`work/` is gitignored.

## Talking points (45 minutes, anatomy then type)

- Trigger: a ready ticket on disk.
- Action: implement due dates on a worktree-style copy.
- Verify: hidden pytest, not a vibe check.
- Memory: the work copy and the PR body. Not chat history.
- Human oversight: a human still merges.

Where one-shot loops break: no contract, no stop, context rot.
That sets up Module 2.

## Do not

- Do not build the CRM.
- Do not open the harness UI yet.
- Do not run the enhancer.
