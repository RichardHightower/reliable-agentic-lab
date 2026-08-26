# Prompt for LangGraph

Graph nodes: orchestrator, maker, checker, grader, gate.

Conditional edges from gate:

- pass -> END
- retry -> maker -> grader -> checker -> gate
- escalate -> END

Budget is a graph state field. Repeat failure is the same failed node ids twice.

If LangGraph is not installed, keep the node functions and drive them from `run_loop`.
Reference: `solutions/m2-harness/loops/implementer/orchestrator.py`.
