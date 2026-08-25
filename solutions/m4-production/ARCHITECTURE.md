# Module 4 architecture

```
GitHub Actions
  -> run_unattended.py --target m2|m3
       -> Module 2 harness or Module 3 report loop
       -> state.json
       -> upload traces as artifacts
```

Nothing new is invented here. The loop already had a budget and a gate.
Production is that loop plus durable state plus a trigger that is not you.
