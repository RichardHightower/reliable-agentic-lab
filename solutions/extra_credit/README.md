# Extra credit solutions

One folder per assignment. `s_ext_<n>` matches `ext_<n>` under
`labs/extra-credit/`.

| Folder | Assignment | Holds |
|---|---|---|
| `s_ext_1_webhook` | the FastAPI receiver | `SPEC.md`, `webhook.py`, `tests/` |
| `s_ext_2_ngrok` | the public tunnel | `SPEC.md` |
| `s_ext_3_groom_ticket` | the groomer on Actions | `SPEC.md`, `groom_ticket.py`, `tests/` |
| `s_ext_4_fix_pr` | the fixer on Actions | `SPEC.md`, `fix_pr.py`, `tests/` |
| `s_ext_5_digitalocean` | the Droplet deployment | `SPEC.md` |

## Shared, because more than one assignment reads it

| File | What it is |
|---|---|
| `github_api.py` | the GitHub client, labels, and attempt counting |
| `fake_github.py` | a client that records instead of calling, for the tests |
| `__init__.py` | `ROOT` and `TARGET`, defined once |

Assignments 2 and 5 hold no Python. They put assignment 1 somewhere GitHub can
reach it, so their answer is a procedure.

## Run the tests

```bash
task test
```

The two local runs drive the real engine against `work/northwind-field-crm` and
skip when you have not cloned it. The GitHub paths use `fake_github.py` and need
no token.

## The rule these assignments exist to show

The trigger moves out of the loop. The exits stay in it. A workflow file starts
the run. It never decides when to stop. Every assignment here calls the matching
`solutions/solN_*` folder. There is no shared engine.
