# If you fall behind

Nobody is graded here. Falling behind on one lab must not cost you the next one.

## Do this

1. Stop typing and watch Rick finish the build.
2. Save your attempt. The next step overwrites it.

   ```bash
   cp loop.py loop.py.my-attempt
   ```

3. Copy the answer in.

   ```bash
   cp ../../solutions/sol3_research/loop.py .
   ```

4. You now have a working research assistant over mcp. Continue with the next module.

## What you get

A working research assistant that cites what it retrieved.

## Read what you copied

`solutions/sol3_research/SPEC.md` is the step-by-step build for this lab. The same
answer sits in `solutions/sol3_research_codex`, `_grok_build`, and `_opencode`, one
per tool, each with the spec written for that tool.

## Coming back later

Put the empty stub back and try again:

```bash
git checkout -- loop.py
```

That restores this one file. Everything you need is in `prompts/`, and
`loops/researcher.py, loops/research.py, and loops/brief.py` is the reference the answer calls.
