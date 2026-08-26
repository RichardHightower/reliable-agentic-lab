# Model Context Protocol servers

`.mcp.json` ships with this repo, so your coding agent finds the same two
servers everyone else in the room has.

| Server | Key needed | What it gives you |
|---|---|---|
| `context7` | none | Current library documentation. HTTP, no account. |
| `perplexity-ask` | yours | Web research with citations. |

## Perplexity is optional

Set `PERPLEXITY_API_KEY` in `.env` if you have one. If you do not, you have two
other ways to run the research loop, and you pick:

```bash
task loop:research -- --question "..." --backend websearch   # your agent's own search
task loop:research -- --question "..." --backend fixture     # recorded, works offline
```

The loop does not know which one it is holding. That is the Module 3 lesson:
name the boundary, and keep the caller ignorant of what is behind it.

## Approving the servers

Your agent asks once per project. Approve `context7` at minimum. Nothing in the
labs requires `perplexity-ask`.

## What these servers may not do

Neither server can write a file, run a command, commit, or push. A tool contract
is a short list of what an agent may do and a much more interesting list of what
it may not.
