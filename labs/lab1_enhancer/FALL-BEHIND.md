# If you fall behind

Nobody is graded here. Falling behind on one lab must not cost you the next
one.

1. Stop typing and watch Rick finish the build.
2. Copy the answer for the tool you are running. Pick your section below.
3. Set up your own fork's `config.json`, see [README.md](README.md).
4. You now have a working ticket enhancer. Continue with the next module.

Every command below runs from `labs/lab1_enhancer/`.

## Claude code

This is Saturday's default path.

```bash
mkdir -p .claude/agents .claude/skills
cp -r ../../solutions/sol1_enhancer/.claude/agents/* .claude/agents/
cp -r ../../solutions/sol1_enhancer/.claude/skills/* .claude/skills/
cp ../../solutions/sol1_enhancer/config.json.example .
```

Run it: `task run, --ticket T001`.

The full design is
[solutions/sol1_enhancer/SPEC.md](../../solutions/sol1_enhancer/SPEC.md).

## Codex

```bash
mkdir -p .agents bin
cp -r ../../solutions/sol1_enhancer_codex/.agents/* .agents/
cp -r ../../solutions/sol1_enhancer_codex/bin/* bin/
cp ../../solutions/sol1_enhancer_codex/AGENTS.md .
cp ../../solutions/sol1_enhancer_codex/config.json.example .
chmod +x bin/*.sh
```

`bin/role.sh` starts the judge and the doer as their own read-only `codex
exec` processes. Isolation in Codex is a process sandbox, not a per-agent tool
list, so that script is the fence. Do not lose the execute bit.

The design is
[solutions/sol1_enhancer_codex/SPEC.md](../../solutions/sol1_enhancer_codex/SPEC.md),
and
[IMPLEMENTATION_NOTES.md](../../solutions/sol1_enhancer_codex/IMPLEMENTATION_NOTES.md)
explains the sandbox.

## Grok build

```bash
cp -R ../../solutions/sol1_enhancer_grok_build/.grok .
cp ../../solutions/sol1_enhancer_grok_build/AGENTS.md .
cp ../../solutions/sol1_enhancer_grok_build/config.json.example .
```

`cp -R` copies the three symlinks under `.grok/agents/` and `.grok/skills/` as
symlinks, which is what you want. They point at
`../plugins/ticket-enhancer/`, so they keep working after the copy.

Two things Grok needs before this runs at all:

1. Trust the checkout. Run `grok` here once with no arguments and accept the
   prompt. Headless `grok -p` never prompts.
2. Confirm the names, not the counts:

   ```bash
   grok inspect | grep -E "enhancer-loop|enhancer-judge|enhancer-doer"
   ```

   All three must be listed. If they are not, the symlinks did not survive the
   copy.

The design is
[solutions/sol1_enhancer_grok_build/SPEC.md](../../solutions/sol1_enhancer_grok_build/SPEC.md),
and
[IMPLEMENTATION_NOTES.md](../../solutions/sol1_enhancer_grok_build/IMPLEMENTATION_NOTES.md)
explains plugin loading.

## OpenCode

No OpenCode answer exists yet. Copy the Claude Code section above and run it
with Claude Code for this hour. See
[solutions/sol1_enhancer_opencode/README.md](../../solutions/sol1_enhancer_opencode/README.md).
