# Prompt for LangChain Deep Agents

Take-home. Saturday is [prompts/claude-code.md](claude-code.md).

Build the ticket enhancer as a Python loop on LangChain Deep Agents. The
finished answer is `solutions/sol1_enhancer_deep_agents/`. Read its
[SPEC.md](../../../solutions/sol1_enhancer_deep_agents/SPEC.md),
[HOW_TO_RUN.md](../../../solutions/sol1_enhancer_deep_agents/HOW_TO_RUN.md),
and
[DESIGN_DOC.md](../../../solutions/sol1_enhancer_deep_agents/DESIGN_DOC.md)
before you type.

Python owns discovery, GitHub, the candidate file, and the exits. The model
drafts and grades. It does not write files. It does not run `/enhancer-loop`.

Needs `deepagents>=0.7`.

Work from the answer folder, or paste into `claude` from this lab folder.

```bash
cd solutions/sol1_enhancer_deep_agents
# or: cd labs/lab1_enhancer && claude
```

Interactive: run `claude` and paste each prompt below in turn.

Do not copy these harness fences into `solutions/sol1_enhancer/`. That folder
is the Saturday Claude Code plugin.

---

## Prompt 0: the things that will waste your hour

Learn these before you build anything. Each one fails silently.

1. Deep Agents scopes three ways and you need all three. A tool list per
   subagent. A path check inside the doer's write tool. Harness fences on
   the orchestrator. Any one of them left off is a hole the other two
   cannot see.
2. Turn the default `general-purpose` subagent off. It ships with the
   harness filesystem tools. Leaving it on is how a "scoped" agent writes
   `app/`.
3. Skills are mounted, not pasted. `skills/judge/SKILL.md` and
   `skills/doer/SKILL.md` load when the role is invoked. Do not paste
   `SKILL.md` into a subagent prompt. Do not shadow `read_file` with a
   custom tool.
4. `FilesystemBackend(root_dir=crm, virtual_mode=True)` so `..` cannot walk
   off the target repo. A custom write tool you wrote is not covered by
   that. Resolve the path yourself before you touch disk.
5. Homebrew Python will refuse `pip install` (PEP 668). `task setup` creates
   `.venv` in this folder.

---

## Prompt 1: the role table

```
Create roleplan.py and loop.py --table-only.

The enhancer cast is orchestrator, doer, judge. That list lives in
roleplan.py. Do not restate a scope anywhere else.

The judge holds no write tool. The doer's fallback scope is tickets/**.
The orchestrator writes nothing.

loop.py --table-only must run with no SDK, no API key, and no clone.
Print the role table. The judge must print no in the writes column.
If it prints yes, stop.
```

Run it:

```bash
task table
```

---

## Prompt 2: the three fences

```
Create roles.py. Use all three layers.

1. Each subagent gets its own tool list. The judge is never handed a write
   tool. Deep Agents supplies read-only filesystem tools through the
   mounted backend. Do not give the judge a custom write tool that shadows
   those routes.

2. Path scope lives inside the doer's write tool. The tool checks
   tickets/** before it touches disk. Resolve the path under the target
   repo first. Refuse .. as a real escape, not as a glob. Return a short
   REFUSED sentence, do not raise. An exception string in context starts a
   retry loop.

3. Fence the harness the way the product actually works in 0.7:
   - FilesystemBackend(root_dir=crm, virtual_mode=True)
   - CompositeBackend mounts this folder's skills/ and AGENTS.md
   - permissions= deny writes on the orchestrator, allow tickets/** on the
     doer, deny writes on the judge
   - A harness profile hides write_file, edit_file, delete, and execute
     from the orchestrator, and turns off the default general-purpose
     subagent
   - The judge uses response_format so {kind, present_fields} is a schema,
     not a regex over a graph-state repr

(1) and (2) are what task test pins down with no SDK installed. (3) is
what build_agent does on a real run.
```

---

## Prompt 3: skills, not a stuffed prompt

```
Create skills/judge/SKILL.md and skills/doer/SKILL.md.

Deep Agents loads the body when the role is invoked. Do not paste SKILL.md
into a subagent prompt.

The judge grades one ticket file. It holds no write tool. It does not
compute ready. Reply with one JSON object and nothing else:
{"kind": "feature", "present_fields": ["problem", "proposal"]}.

kind is bug, feature, or ui. present_fields lists only required fields
that have real content. A heading with an empty body is not present.

The doer drafts a full replacement ticket body. Investigate app/ before
inventing. Return the draft as text.
```

---

## Prompt 4: the deterministic half

```
Create check_fields.py and check_stop.py.

check_fields.py reads {"kind", "present_fields"} and prints
{"kind", "present_fields", "missing_fields", "ready"}. It computes
missing_fields from its own rubric table.

Bug needs title, steps, expected, actual, environment.
Feature needs problem, proposal, value, criteria.
UI needs those four plus a wireframe.

check_stop.py reads {"round", "budget", "signature", "previous_signature"}
and prints {"stop", "reason"}. stop is true when the signature repeats
(not the first round), or when round + 1 reaches budget.

Both have --demo with asserts. Python computes ready and stop. The model
does not.
```

Run them: `task checks`

---

## Prompt 5: the Python orchestrator

`enhancer.py` is the same file the Agent SDK port runs, give or take the
comment marker. It never imports a runtime. It takes a backend.

```
Create enhancer.py. Same eight steps as the Claude Code skill, in Python.

The model drafts and grades. Everything else is computed.

Every comment the loop posts ends with <!-- enhancer-loop -->. The newest
comment query skips any comment carrying that marker, so the loop cannot
spend every poll answering its own last reply. Do not filter by author
instead. You run as your own gh account and would drop your own LGTM.

Find the GitHub issue. Never create one. Lookup order: state file, then
frontmatter, then a title search across every state. Never only the open
ones. A closed issue is still that ticket's issue.

Add enhanced on first touch, not at create time. ready plus exact LGTM
releases the ticket. A red rubric never consumes an LGTM. The candidate
replaces the real ticket only when its missing set is a proper subset.
"Not worse" is not good enough.
```

---

## Prompt 6: Taskfile and tests

```
Give the folder task setup, task table, task checks, task test,
task clone, task create-test-tickets, task reset-test-tickets,
task run, and task poll-forever.

task setup creates .venv and installs deepagents>=0.7 plus pytest.
task table, task checks, and task test need no SDK, no key, and no clone.

Pin: judge holds no write tool; the doer's write tool refuses a path
outside tickets/**; .loop.yml merges over the defaults; the backend drops
any file the scope does not permit.
```

---

## Verify

```bash
cp config.json.example config.json   # fill in your GitHub username
echo 'ANTHROPIC_API_KEY=sk-ant-...' >> ../../.env
task setup
task table          # judge writes must print no
task checks
task test
task clone
task create-test-tickets
timeout 420 task run --
task run -- --ticket T001
task run -- --ticket T001 --simulate-comment LGTM
```

`--simulate-comment` needs `--ticket`. `task run` is
`python3 loop.py --once --repo <target>`. Extra flags after `--` go to
`loop.py`.

---

## Prompt 7: compare against the answer

```
Diff what I built against solutions/sol1_enhancer_deep_agents/, field by
field and step by step, not just the raw text. Tell me where they differ
in behavior, not just wording, and for each difference, whether it is a
real gap or a legitimate different choice. I will decide what to change.
```

## If you fall behind

[FALL-BEHIND.md](../FALL-BEHIND.md) has the run commands for this runtime.
The answer is the folder. Reading it costs you nothing.
