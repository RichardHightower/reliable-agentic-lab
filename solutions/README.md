# Solutions

The reference implementation of every loop lives in `loops/` at the repo root.
It is not hidden, and reading it is not cheating.

This folder holds the same loops written against other runtimes. They are the
slide code, they drive the discussion, and they are the answer key for the
take-home labs in `labs/takehome/`.

| Folder | Runtime | Observability |
|---|---|---|
| `agent_sdk/` | Claude Agent SDK | Langfuse, optional |
| `deep_agents/` | LangChain Deep Agents | Langfuse, optional |
| `extra_credit/` | GitHub Actions and webhooks | Local JSON |

Nobody is expected to finish a take-home lab inside the five hours. Some will
try.

## Why a second runtime exists at all

To show that the harness is the product and the framework is not. The rubric,
the red gate, the write scope, and the exits are the same in all three. Only
the plumbing changes.

If porting a loop to a new runtime requires changing `loops/`, the design leaked.
