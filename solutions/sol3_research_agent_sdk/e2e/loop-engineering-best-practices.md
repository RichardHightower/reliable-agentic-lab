# Commissioning brief: Loop engineering best practices

Write an evidence-backed technical white paper for engineering leaders deciding
how to operate agentic loops safely.

The paper must explain bounded execution, independent verification, evidence
grounding, deterministic quality gates, retry limits, cost limits, and
escalation to a person. Prefer specifications, official SDK documentation, and
other primary sources. State limitations and tradeoffs; do not present a model's
self-report as a reliable stop condition.

Plan exactly these two figures, with these identifiers:

1. `control-loop`: plan, research, independent verification, writing,
   deterministic checking, and the pass/retry/escalate exits.
2. `trust-boundary`: primary sources, researcher, independent verifier, scoped
   writer, and the deterministic gate, showing which actor may influence each
   artifact.

The article should have at least three substantive sections in addition to its
abstract and references. Every substantive recommendation must be grounded in
retrieved evidence.
