# Architecture

Local board stands in for GitHub.

Poll. Classify or detect failure. Act. Verify. Exit.

| Agent | Tools | Forbidden |
|---|---|---|
| Enhancer | read ticket, comment, label ready | merge, deploy, edit CRM |
| Implementer | read ready ticket, edit CRM, pytest | edit graders, merge |
| Fixer | read pytest, edit CRM, comment on PR | merge, deploy |

Exit is always explicit: ready label, green grader, max retries, or abandon comment.
