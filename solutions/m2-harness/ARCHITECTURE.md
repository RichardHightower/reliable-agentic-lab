# Module 2 architecture

```
orchestrator
  holds budget
  sees summaries and scores only
    -> Maker
         read/write scoped CRM files
         no ticket state changes
    -> Grader
         pytest hidden contract
    -> Checker
         read only
    -> Gate
         pass | retry | escalate
    -> Trace JSON
```

Python owns the retry loop. The model does not count attempts.

Forbidden to both sub-agents: edit graders, merge, deploy.

Contract: `contracts/module2-harness.md`.
Rubric source: `solutions/tickets/T001-due-dates.ready.md`.
