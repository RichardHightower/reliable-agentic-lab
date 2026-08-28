---
marp: true
theme: spillwave
paginate: true
footer: Spillwave Solutions | spillwave.com
---
# sol4_fixer_agent_sdk

The working Module 4 loop. Issue 120.

`query()`, not `ClaudeSDKClient`. `permission_mode: acceptEdits`. Merge is never a tool.


---

# Layout

```
loop.py       summarize_failure + repair_until_green wrappers
fixer.py      the while loop
doers.py      none / reference / cli / SDK backend
gates.py      identical copy to sol3
contract.py   Taskfile + junit + coverage
roles.py      acceptEdits, PreToolUse deny tests/**
tests/        hook deny/allow, same-signature escalate
```

No `unattended.py`. Durable `.harness/state.json` and exit 0/2/1 lived there and were not copied. This CLI returns `0 if green else 1`. Name that drift.


---

# Learning objectives

- Walk `fixer.run`
- Set `permission_mode: acceptEdits` because nobody is in the chair
- Deny `tests/**` on the code implementer
- Stash before `--branch broken-pr`
- Leave a comment when the loop gives up


---

# Starting architecture

```
Trigger → fixer.run
            contract.run("test")
            green? PASS
            never ran? ESCALATE
            same failing ids twice? ESCALATE + comment
            else doer repairs inside app/**
         → .harness/last-fixer.json
         → Human merge
```


---

# Five unattended lines

```
permission_mode: acceptEdits     # nobody to click Allow
PreToolUse deny tests/**         # cannot weaken a test
max_turns=12                     # SDK inner budget; Python owns outer
tests after every turn = pytest  # not a claim
Merge is never a tool
```

Research port uses `dontAsk`. This one uses `acceptEdits`.


---

# `failure_summary`

```python
def failure_summary(run_result) -> str:
    failed = sorted(run_result.junit.failed_ids)
    lines = [f"{len(failed)} failing: {', '.join(failed[:5])}"] if failed else ["the suite is red"]
    error = ERROR_IN_OUTPUT.search(run_result.output or "")
    if error:
        lines.append(error.group(0).strip()[:200])
    return "\n".join(lines)
```


---

# Doers

| Spec | Behavior |
|---|---|
| `none` | writes nothing. Loop still reports the truth |
| `reference` | copies `known-good` inside WriteScope |
| `sdk` | `AgentSdkBackend` wrapping `query()` |
| `claude` / `codex` / `grok` | `CliBackend` |

Reference skipping `tests/**` is the whole point.


---

# Commands

```bash
cd solutions/sol4_fixer_agent_sdk
python3 -m pytest tests -q
python3 loop.py --table-only
# after stash:
python3 loop.py --repo ../../work/northwind-field-crm --branch broken-pr --doer none
python3 loop.py --repo ../../work/northwind-field-crm --branch broken-pr --doer reference
```


---

# Expected `--doer none`

```
attempt 1: 1 failing -> retry
attempt 2: 1 failing -> escalate
gate: escalate
The fixer gave up.
A human should take this one.
```


---

# Tests

| Test | Asserts |
|---|---|
| `test_hook_denies_test_write` | Write `tests/test_x.py` → deny |
| `test_hook_allows_app_write` | Write `app/main.py` → `{}` |
| `test_options_use_accept_edits` | `permission_mode == "acceptEdits"` |
| `test_same_failing_ids_escalate` | same signature → ESCALATE |
| `test_no_loops_import` | no `from loops` |


---

# Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Dirty tree | Lab 2 leftover | stash |
| Green on `none` | missing signature stop | `gates.decide` |
| Edited a test | hook fail-open | full deny envelope |
| Exit 1 on escalate | unattended.py missing | named drift, not a silent bug |


---

# Recap

Same graph, nobody at the keyboard. Reference doer still bound by WriteScope. Human owns merge.

Rebuild `unattended.py` in this folder if you need exit 2 for escalate.

---

# Prerequisites

```bash
cd solutions/sol4_fixer_agent_sdk
python3 -m pytest tests -q
git -C ../../work/northwind-field-crm stash --include-untracked
```

`--doer sdk` needs `claude-agent-sdk`. `--doer none` and `--doer reference` do not.

---

# `repair_until_green` wrapper

```python
def repair_until_green(contract, budget: int = 3, doer: str = "reference") -> dict:
    if doer == "sdk":
        doer = backend(contract)
    return fixer.run(repo=contract.repo, budget=budget, doer=doer, research_backend=None)
```

Saturday types a body. This folder delegates to `fixer.run`.

---

# Final checklist

- [ ] pytest green without a key
- [ ] table: judge `no`, coder denied `tests/**`
- [ ] `permission_mode == "acceptEdits"`
- [ ] `--doer none` on `broken-pr` escalates with a comment
- [ ] merge is not in any tool list
