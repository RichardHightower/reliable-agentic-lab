# reliable-agentic-lab

Working solutions for **Engineering Reliable Agentic AI Systems**.
Packt workshop. Saturday 29 August 2026. 10:00 to 15:00 Central.

Instructor: Rick Hightower.

Do not invent a new outline. This repo maps onto the locked four modules.

Start here:

- [SETUP.md](SETUP.md)
- [INSTRUCTIONS.md](INSTRUCTIONS.md)

## Layout

```
solutions/crm              known-good CRM with due dates
solutions/tickets          markdown tickets, including the ready T001 contract
solutions/m1-implementer   one autonomous loop
solutions/m2-harness       Maker, Checker, rubric, hidden grader, gates
solutions/m3-research      report loop. Fact-check. Style enforcer.
solutions/m4-production    unattended runner plus GitHub Actions
labs/                      exercises later. Empty until solutions pass.
```

Every solutions package has `README.md`, `SETUP.md`, `INSTRUCTIONS.md`,
`ARCHITECTURE.md`, and `TROUBLESHOOTING.md`.

No per-module branches. Solutions live in folders. Labs come after.

## What they take home

1. A running loop.
2. A reusable harness.
3. One Model Context Protocol (MCP) research assistant that writes a report, fact-checks it, and enforces style.
4. A production-ready Actions architecture.
