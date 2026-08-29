# Agent instructions for this folder

The artifact here is a Google Antigravity plugin, `ticket-enhancer`, in
`.agents/plugins/ticket-enhancer/`. Use it. Do not build a `.claude/` tree
here, and do not copy one in from `solutions/sol1_enhancer/`.

## The three roles

- `enhancer-judge` is a custom subagent under `agents/`. It grades one ticket
  and returns JSON. It holds no `replace_file_content`, no `run_command`, and
  no `invoke_subagent`. A judge that could edit the ticket could grade its
  own work. `subagent: true`, `mainAgent: false`, `commandExecutionPolicy: off`.
- `enhancer-doer` is a custom subagent under the same restrictions. It returns
  a candidate ticket body as plain text. It cannot save that text anywhere.
- `enhancer-loop` is the plugin skill and the orchestrator. It is the only
  role that writes the ticket file or calls `gh`.

Keep that split. Adding `replace_file_content` to either agent removes the
reason the loop can be trusted.

## Two rules that are easy to get wrong

Both deterministic gates live in
`.agents/plugins/ticket-enhancer/skills/enhancer-loop/scripts/`. Call them. Do
not decide `ready`, a stable failure, or a spent budget in prose. A stop
condition a model reasons about is a stop condition a model can talk past.

Run `agy` from this folder, or open this folder as the Antigravity workspace.
Antigravity discovers `.agents/skills/` and `.agents/agents/` from the
workspace root, so a run started at the lab repo root cannot see this skill.
See [IMPLEMENTATION_NOTES.md](IMPLEMENTATION_NOTES.md).
