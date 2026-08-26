# Prompt for Claude Code

Claude Code is not required. See [labs/HOW-TO-RUN.md](../../HOW-TO-RUN.md).

Headless (no TUI):

```bash
claude -p "$(cat labs/m3-enhancer/prompts/claude-code.md)" --allowedTools "Read,Edit,Write,Bash,Glob,Grep"
```

Interactive: run `claude` at the repo root and paste everything below this line.

Fill `labs/m3-enhancer/loop.py`.

This is the Ticket Enhancer. It is also the Module 3 research assistant.

Behavior:

1. Poll the local board for T001.
2. Classify bug, feature, or user interface.
3. Score against the type criteria in the Product Requirements Document.
4. If not ready, post a comment with concrete missing pieces and a suggested ready body.
5. If `--incorporate`, write the suggested body onto the ticket (human accepted the edit).
6. When success criteria are testable, apply the `ready` label and stop.

Use `solutions/tickets/T001-due-dates.ready.md` as the gold contract for T001.
Use `solutions/loops/criteria.py` if you want the same rubric as the working example.

MCP-shaped tools you may pretend to have: read repo, read ticket, write comment, mark ready.
No merge. No production deploy.

Research stays in this loop. The orchestrator only sees a summary.
