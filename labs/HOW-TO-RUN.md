# How to run a lab prompt

Claude Code is not required.

Pick one coding agent you already use. Interactive paste works. Headless is better for a repeatable loop.

Do this from the repo root, with `.venv` active.

| Tool | Interactive | Headless |
|---|---|---|
| Claude Code | `claude` then paste the prompt | `claude -p "$(cat PROMPT)"` |
| OpenCode | `opencode` then paste | `opencode run "$(cat PROMPT)"` |
| Codex | `codex` then paste | `codex exec "$(cat PROMPT)"` |
| Grok Build | `grok` then paste | `grok -p "$(cat PROMPT)"` |

`PROMPT` is the lab file, for example `labs/m1-implementer/prompts/claude-code.md`.
The task is the same for every tool. Do not fill Agent SDK and LangGraph unless that is your chosen track.

The hidden grader and `python -m solutions.loops ...` still run with no coding-agent CLI at all.

## Claude Code headless

Install and log in however you already do (`claude`, or `ANTHROPIC_API_KEY`).

Print mode is headless. No TUI. The agent runs, prints, and exits.

```bash
cd /path/to/reliable-agentic-lab

claude -p "$(cat labs/m1-implementer/prompts/claude-code.md)" \
  --allowedTools "Read,Edit,Write,Bash,Glob,Grep"
```

Useful flags:

- `-p` / `--print` non-interactive
- `--allowedTools` so it does not stall on a permission prompt
- `--output-format json` if you want to log the run
- `--dangerously-skip-permissions` only on a throwaway worktree, never on a repo you care about

Pipe the file instead of `$(cat ...)` if your shell prefers stdin. Check `claude -h` for current stdin behavior.

Swap the path for Module 2, 3, or 4.

```bash
claude -p "$(cat labs/m2-harness/prompts/claude-code.md)" --allowedTools "Read,Edit,Write,Bash,Glob,Grep"
claude -p "$(cat labs/m3-enhancer/prompts/claude-code.md)" --allowedTools "Read,Edit,Write,Bash,Glob,Grep"
claude -p "$(cat labs/m4-fixer/prompts/claude-code.md)" --allowedTools "Read,Edit,Write,Bash,Glob,Grep"
```

After it exits, run the stub yourself and confirm pytest.

## OpenCode headless

```bash
opencode run --dir . "$(cat labs/m1-implementer/prompts/claude-code.md)"
```

Attach the prompt file if your build supports `--file`:

```bash
opencode run --dir . --file labs/m1-implementer/prompts/claude-code.md "Follow the attached lab prompt. Fill the stub. Do not edit graders."
```

Headless server (optional, avoids cold start):

```bash
opencode serve
opencode run --attach http://localhost:4096 "$(cat labs/m1-implementer/prompts/claude-code.md)"
```

## Codex headless

```bash
codex exec "$(cat labs/m1-implementer/prompts/claude-code.md)"
```

`codex exec` is the non-interactive path. No TUI. Use it in a script or in class when you do not want the editor chrome.

If your Codex build wants a working directory flag, pass the repo root. Stay inside this clone.

## Grok Build headless

```bash
grok -p "$(cat labs/m1-implementer/prompts/claude-code.md)" --no-auto-update
```

`-p` is print / headless, same idea as Claude Code. `--no-auto-update` keeps CI and class machines from stalling on an updater.

Log in with your SuperGrok account, or set `XAI_API_KEY` in `.env`.

Streaming JSON if you want a machine-readable trace:

```bash
grok -p "$(cat labs/m1-implementer/prompts/claude-code.md)" --output-format streaming-json --no-auto-update
```

## Rules that apply to every tool

- Work from the repo root.
- Fill only the lab stub. Do not edit `solutions/m2-harness/graders/`.
- Stop on the documented exit (grader green, ready label, budget).
- If the agent stalls, copy the matching folder from `solutions/` and continue.

## If you have none of these CLIs

Run the working examples:

```bash
python -m solutions.loops implementer --maker reference
```

Then paste a prompt later, or type the stub by hand. The loop is the lesson. The CLI is optional.
