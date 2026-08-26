# Prompt for LangGraph

Build a tiny graph for the Ticket Implementer.

Nodes:

1. load_ready_ticket
2. plan
3. write_tests_or_rely_on_hidden_grader
4. implement
5. verify (pytest)
6. open_pr_body

Edges:

- verify pass -> open_pr_body -> END
- verify fail and budget remains -> implement
- verify fail and budget spent -> END with failure

Put the runnable entrypoint in `labs/m1-implementer/loop.py`.
If LangGraph is not installed, keep the same node names as functions and run them in a Python for-loop. The graph is the lesson. The library is optional.
