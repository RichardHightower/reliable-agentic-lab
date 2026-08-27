# Take-home labs

Nobody is expected to finish these inside the five hours. Some people will try.

Both labs rebuild the Module 2 implementer in a different runtime. The graph does
not change. What changes is how the runtime enforces write scope, which is the
only interesting part.

| Runtime | How it separates the roles |
|---|---|
| Plain Python, `loops/` | The `Judge` class has no `write` method |
| Claude Agent SDK | A tool list per subagent, plus a `PreToolUse` hook for paths |
| LangChain Deep Agents | A tool list per subagent, with the path check inside the tool |

The answers are in `solutions/sol2_implementer_agent_sdk/` and
`solutions/sol2_implementer_deep_agents/`. Each holds a `SPEC.md` with the
step-by-step build. The other three labs are ported too, one folder per lab per
runtime, so `solutions/sol4_fixer_agent_sdk/` is lab 4 on the Agent SDK.

The translation both ports call lives in `solutions/agent_sdk/roles.py` and
`solutions/deep_agents/roles.py`. All four labs share it, and it reads the cast
from `solutions/roleplan.py`.

## Install

The five-hour labs need no model key. These two do.

```bash
pip install -r requirements-takehome.txt
```

| Variable | Needed for |
|---|---|
| `ANTHROPIC_API_KEY` | Both labs |
| `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` | Tracing. Optional. |

Without the Langfuse keys the run writes `work/traces/*.json` instead. That file
is the record either way. A dashboard nobody reads is decoration.

## The check that runs without any of it

```bash
task test -- loops/tests/test_runtime_ports.py
```

No SDK required, no key required. They assert that all three
runtimes read the same role table, in all four loops, and that the judge holds
no write tool in any of them. Run them before you run anything that costs money.
