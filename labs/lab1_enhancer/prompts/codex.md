# Prompt for Codex

This lab currently ships a Claude Code plugin only. A Codex-native
equivalent is follow-up work, not built yet, so there is no `loop.py` here
for Codex to fill and nothing in this folder for Codex to build.

Pick one of these for this hour:

1. Copy the finished plugin in, the same way [FALL-BEHIND.md](../FALL-BEHIND.md) does:

   ```bash
   mkdir -p .claude/agents .claude/skills
   cp -r ../../solutions/sol1_enhancer/.claude/agents/* .claude/agents/
   cp -r ../../solutions/sol1_enhancer/.claude/skills/* .claude/skills/
   cp ../../solutions/sol1_enhancer/config.json.example .
   ```

   Then set up your fork's `config.json` (see [README.md](../README.md)) and
   run it with Claude Code: `task run, --ticket T001`.

2. Watch or pair on the Claude Code build. See
   [prompts/claude-code.md](claude-code.md).

## Read what you copied

`solutions/sol1_enhancer/SPEC.md` is the full design for this lab.
