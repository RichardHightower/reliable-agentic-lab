# Prompt for OpenCode

No OpenCode answer exists yet. An OpenCode-native ticket enhancer is coming
soon, and `solutions/sol1_enhancer_opencode/` is a stub until then. See
[its README.md](../../../solutions/sol1_enhancer_opencode/README.md).

Do not copy the Claude Code plugin and call it an OpenCode build. A `.claude/`
tree is not something OpenCode runs. Copying it gives you a folder that looks
finished and does nothing from your tool.

Pick one of these for this hour.

## Run the Claude Code answer

The honest fallback. You get a working enhancer and see the loop behave, you
just drive it with Claude Code rather than OpenCode.

```bash
mkdir -p .claude/agents .claude/skills
cp -r ../../solutions/sol1_enhancer/.claude/agents/* .claude/agents/
cp -r ../../solutions/sol1_enhancer/.claude/skills/* .claude/skills/
cp ../../solutions/sol1_enhancer/config.json.example .
```

Set up your fork's `config.json`, see [README.md](../README.md), then run
`task run -- --ticket T001` with Claude Code.

## Build it for a tool that has an answer

Better use of the hour if you want to build rather than watch. Both of these
ship a finished answer, a spec, and implementation notes:

- [prompts/codex.md](codex.md), a Codex skill set. Isolation is a process
  sandbox.
- [prompts/grok-build.md](grok-build.md), a Grok Build project plugin.
  Isolation is a per-agent tool list, plus a trust step that catches everyone.

## Watch or pair

Follow the Claude Code build, see [prompts/claude-code.md](claude-code.md).

## Read the design either way

[solutions/sol1_enhancer/SPEC.md](../../../solutions/sol1_enhancer/SPEC.md) is
the full design for this lab. The rubric, the red gate, the write scope, and
the stop conditions are the same whichever tool runs them. That is the point
of the module, and it is what you will port when the OpenCode answer lands.
