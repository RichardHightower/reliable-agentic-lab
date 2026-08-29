# Agent instructions for this folder

The artifact here is a GitHub Copilot CLI agent plugin, `ticket-enhancer`, in
`.github/plugins/ticket-enhancer/`. Use it. Do not build a `.claude/` tree
here, and do not copy one in from `solutions/sol1_enhancer/`.

## The three roles

- `enhancer-judge` is a custom agent under
  `com.github.copilot/agents/`. It grades one ticket and returns JSON.
  It holds no `edit`, no `execute`/`shell`, and no `agent` tool. A judge that
  could edit the ticket could grade its own work.
- `enhancer-doer` is a custom agent under the same restrictions. It returns a
  candidate ticket body as plain text. It cannot save that text anywhere.
- `enhancer-loop` is the plugin skill and the orchestrator. It is the only
  role that writes the ticket file or calls `gh`.

Keep that split. Adding `edit` to either agent removes the reason the loop
can be trusted.

## Two rules that are easy to get wrong

Both deterministic gates live in
`.github/plugins/ticket-enhancer/skills/enhancer-loop/scripts/`. Call them. Do
not decide `ready`, a stable failure, or a spent budget in prose. A stop
condition a model reasons about is a stop condition a model can talk past.

Run Copilot CLI from this folder. It discovers `.github/skills/` and
`.github/agents/` from its cwd, so a run started at the lab repo root cannot
see this skill. See [IMPLEMENTATION_NOTES.md](IMPLEMENTATION_NOTES.md).
