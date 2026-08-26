# Prompt for LangGraph

Nodes: poll, classify, evaluate, comment, incorporate, label_ready, END.

Evaluate routes:

- ready -> label_ready -> END
- not ready -> comment -> (incorporate optional) -> evaluate
- budget spent -> END with needs-info

Keep long research out of the orchestrator state. Store it on disk. Put a summary on the state.
