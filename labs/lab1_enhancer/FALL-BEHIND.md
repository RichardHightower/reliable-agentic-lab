# If you fall behind

Nobody is graded here. Falling behind on one lab must not cost you the next
one.

## Do this

1. Stop typing and watch Rick finish the build.
2. Copy the answer's plugin scaffolding in:

   ```bash
   mkdir -p .claude/agents .claude/skills
   cp -r ../../solutions/sol1_enhancer/.claude/agents/* .claude/agents/
   cp -r ../../solutions/sol1_enhancer/.claude/skills/* .claude/skills/
   cp ../../solutions/sol1_enhancer/config.json.example .
   ```

3. Set up your own fork's `config.json`, see [README.md](README.md).
4. You now have a working ticket enhancer. Continue with the next module.

## What you get

A Claude Code plugin that grooms every open ticket in your fork, one poll
at a time.

## Read what you copied

`solutions/sol1_enhancer/SPEC.md` is the full design for this lab.
