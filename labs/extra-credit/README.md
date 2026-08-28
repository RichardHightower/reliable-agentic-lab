# Extra credit

Not on the Saturday clock. Do not skip Module 2 to work on these.

| # | Folder | You build | Answer |
|---|---|---|---|
| 1 | `ext_1_webhook` | one FastAPI `POST /github-webhook` that verifies the signature and calls `sol1_enhancer` | `solutions/extra_credit/s_ext_1_webhook/` |
| 2 | `ext_2_ngrok` | copy the Lab 1 plugin, run the ngrok adapter, one real GitHub delivery | `solutions/extra_credit/s_ext_2_ngrok/` |
| 5 | `ext_5_digitalocean` | the same receiver on a Droplet behind nginx | its `README.md` plus `deploy/` |

Assignment 1's filled answer shells out to
[`solutions/sol1_enhancer`](../../solutions/sol1_enhancer). It does not import it.

Assignment 2 copies the Lab 1 enhancer plugin and adds a small Python adapter
behind ngrok. Assignment 5 puts assignment 1 on a Droplet.

## Start one

Each folder holds its own `README.md` with the brief. Read
[SETUP.md](SETUP.md) first, then the folder you picked.

## The rule that does not change

The trigger moves out of the loop. The exits stay in it. A webhook starts the
run. It never decides when to stop.

Claude Code is not required for the tests. A live Droplet with
`AGENT_BACKEND=claude` does need it.
