# Extra credit solutions

One folder per assignment. `s_ext_<n>` matches `ext_<n>` under
`labs/extra-credit/`.

| Folder | Assignment | Holds |
|---|---|---|
| `s_ext_2_ngrok` | ngrok adapter for the Lab 1 enhancer plugin | `SPEC.md`, `bin/`, `Taskfile.yml`, `tests/` |
| `s_ext_5_digitalocean` | the Droplet deployment | `SPEC.md` |

The webhook, groom-ticket, and fix-pr solution folders are gone.
Those answers live in the Saturday lab folders instead.

## Shared, because more than one assignment reads it

| File | What it is |
|---|---|
| `github_api.py` | the GitHub client, labels, and attempt counting |
| `fake_github.py` | a client that records instead of calling, for the tests |
| `__init__.py` | `ROOT` and `TARGET`, defined once |

Assignment 2 copies `solutions/sol1_enhancer` into its own folder, then
adapts GitHub webhooks through ngrok onto `task run`. It does not import the
Lab 1 folder at runtime. Assignment 5 is still a procedure that puts a
receiver somewhere GitHub can reach.

## Run the tests

```bash
task test
```

The GitHub paths use `fake_github.py` and need no token. The ngrok adapter
tests need no ngrok and no Claude.

## The rule these assignments exist to show

The trigger moves out of the loop. The exits stay in it. A workflow file or
a webhook starts the run. It never decides when to stop. There is no shared
engine.
