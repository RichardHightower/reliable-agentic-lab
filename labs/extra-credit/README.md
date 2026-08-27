# Extra credit

Not on the Saturday clock. Do not skip Module 2 to work on these.

Five assignments, one folder each. They build on each other in order.

| # | Folder | You build | Answer |
|---|---|---|---|
| 1 | `ext_1_webhook` | one FastAPI `POST /github-webhook` that verifies the signature and routes events | `solutions/extra_credit/s_ext_1_webhook/` |
| 2 | `ext_2_ngrok` | a public URL for the receiver you just wrote, and one real delivery | its `README.md` |
| 3 | `ext_3_groom_ticket` | the groomer, triggered by a GitHub Actions issue event | `solutions/extra_credit/s_ext_3_groom_ticket/` |
| 4 | `ext_4_fix_pr` | the fixer, triggered by a failed check suite | `solutions/extra_credit/s_ext_4_fix_pr/` |
| 5 | `ext_5_digitalocean` | the same receiver on a Droplet behind nginx | its `README.md` |

Assignments 2 and 5 write no Python. They put assignment 1 somewhere GitHub can
reach it.

## Start one

Each folder holds its own `README.md` with the brief. Read
[SETUP.md](SETUP.md) first, then the folder you picked.

## The rule that does not change

The trigger moves out of the loop. The exits stay in it. A workflow file starts
the run. It never decides when to stop.

Claude Code is not required. See [../HOW-TO-RUN.md](../HOW-TO-RUN.md).
