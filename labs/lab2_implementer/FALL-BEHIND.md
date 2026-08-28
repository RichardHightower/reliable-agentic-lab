# If you fall behind

Nobody is graded here. Falling behind on one lab must not cost you the next one.

## Do this

1. Stop typing and watch Rick finish the build.
2. Save your attempt. The next step overwrites it.

   ```bash
   cp harness.py harness.py.my-attempt
   ```

3. Copy the answer in.

   ```bash
   cp ../../solutions/sol2_implementer/harness.py .
   ```

4. You now have a working ticket implementer and the harness. Continue with the next module.

## What you get

A reusable evaluation harness that plans, executes, verifies, and iterates.

## Read what you copied

`solutions/sol2_implementer/SPEC.md` is the step-by-step build for this lab. The same
answer sits in `solutions/sol2_implementer_codex`, `_grok_build`, and `_opencode`, one
per tool, each with the spec written for that tool.

## Coming back later

Put the empty stub back and try again:

```bash
git checkout -- harness.py
```

That restores this one file. Everything you need is in `prompts/`, and
`solutions/sol2_implementer/` is the reference the answer calls.
