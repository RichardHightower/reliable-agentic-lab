# Extra credit solutions

One folder per assignment. `s_ext_<n>` matches `ext_<n>` under
`labs/extra-credit/`.

| Folder | Assignment | Holds |
|---|---|---|
| `s_ext_1_webhook` | the FastAPI receiver that calls `sol1_enhancer` | `SPEC.md`, `webhook.py`, `call_sol1.py`, `tests/` |
| `s_ext_2_ngrok` | the public tunnel | `SPEC.md` |
| `s_ext_5_digitalocean` | the Droplet deployment | `SPEC.md`, `deploy/` |

## Shared, because more than one assignment reads it

| File | What it is |
|---|---|
| `github_api.py` | the GitHub client, labels, and attempt counting |
| `fake_github.py` | a client that records instead of calling, for the tests |
| `__init__.py` | `ROOT` and `TARGET`, defined once |

The receiver does not import `solutions/sol1_enhancer`. It shells out to
`task run -- --ticket T001` in that folder. The exits stay there.

Assignments 2 and 5 hold no Python. They put assignment 1 somewhere GitHub can
reach it, so their answer is a procedure plus the scripts under `deploy/`.

## Run the tests

```bash
task test
```

The GitHub paths use `fake_github.py` and need no token. The sol1 handoff is
monkeypatched in the webhook tests, so Claude Code is not required to go green.

## The rule these assignments exist to show

The trigger moves out of the loop. The exits stay in it. A webhook starts the
run. It never decides when to stop. There is no shared engine.
