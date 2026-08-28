# If you fall behind

Nobody is graded here. Falling behind on one lab must not cost you the next one.

## Do this

1. Stop typing and watch Rick finish the build.
2. Save your attempt. The next step overwrites it.

   ```bash
   cp harness.py harness.py.my-attempt
   ```

3. Watch Rick finish and type what he typed. There is no drop-in `harness.py`.

4. You now have a working ticket implementer and the harness. Continue with the next module.

## What you get

A reusable evaluation harness that plans, executes, verifies, and iterates.

## Read if you stall

`rubric.py` and `gates.py` in this folder. The takehome ports
`solutions/sol2_implementer_agent_sdk/` and
`solutions/sol2_implementer_deep_agents/` are a different runtime, not a
drop-in for this stub.

## Coming back later

Put the empty stub back and try again:

```bash
git checkout -- harness.py
```

That restores this one file. Everything you need is in `prompts/`, and
`rubric.py` and `gates.py` in this folder are the reference.
