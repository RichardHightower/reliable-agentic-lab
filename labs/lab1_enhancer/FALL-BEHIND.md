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
   cp ../../solutions/sol1_enhancer/loop.py .
   ```

4. You now have a working ticket enhancer. Continue with the next module.

## What you get

A working autonomous loop, running on your machine.

## Read what you copied

`solutions/sol1_enhancer/SPEC.md` is the step-by-step build for this lab. The same
answer sits in `solutions/sol1_enhancer_codex`, `_grok_build`, and `_opencode`, one
per tool, each with the spec written for that tool.

## Coming back later

Put the empty stub back and try again:

```bash
git checkout -- loop.py
```

That restores this one file. Everything you need is in `prompts/`, and
`loops/enhancer.py and loops/criteria.py` is the reference the answer calls.
