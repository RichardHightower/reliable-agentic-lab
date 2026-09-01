# Bug rubric: source evidence

A bug ticket is not ready because it has nice-looking sections. The Judge
must point to a code path that can produce the claimed Actual behavior.

`check_fields.py` requires `source_evidence` on kind `bug`, and only counts
it when `source_status` is `supported`. `contradicted` blocks the ticket
even if every heading is filled. That is the gate T900 runs through.

Four newer ports raised this bar first (Grok Build, VS Code, Copilot CLI,
Antigravity). Every sol1 port now uses the same rubric. See issue #277.
