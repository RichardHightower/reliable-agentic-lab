# If you fall behind

Nobody is graded here. Falling behind on one lab must not cost you the next
one.

1. Stop typing and watch Rick finish the build.
2. Copy the answer for the tool you are running. Pick your section below.
3. Set up your own fork's `config.json`, see [README.md](README.md).
4. You now have a working ticket enhancer. Continue with the next module.

Every command below runs from `labs/lab1_enhancer/`.

`task run` looks at the skill tree you copied and calls that CLI. A Grok
copy does not need Claude Code on PATH. `task detect` prints the choice.

## Claude code

This is Saturday's default path.

```bash
mkdir -p .claude/agents .claude/skills
cp -r ../../solutions/sol1_enhancer/.claude/agents/* .claude/agents/
cp -r ../../solutions/sol1_enhancer/.claude/skills/* .claude/skills/
cp ../../solutions/sol1_enhancer/config.json.example .
```

Run it: `task create-test-tickets` then `task run --`. Needs `claude` on
PATH.

The full design is
[solutions/sol1_enhancer/SPEC.md](../../solutions/sol1_enhancer/SPEC.md).

## Codex

```bash
mkdir -p .agents bin
cp -r ../../solutions/sol1_enhancer_codex/.agents/* .agents/
cp ../../solutions/sol1_enhancer_codex/bin/role.sh bin/
cp ../../solutions/sol1_enhancer_codex/bin/fence_check.sh bin/
cp ../../solutions/sol1_enhancer_codex/AGENTS.md .
cp ../../solutions/sol1_enhancer_codex/config.json.example .
chmod +x bin/*.sh
```

Copy `role.sh` and `fence_check.sh` only. Do not copy the whole `bin/`
over this folder's `bin/run_loop.sh`. That script is what makes
`task run` call `codex` instead of `claude`.

`bin/role.sh` starts the judge and the doer as their own read-only `codex
exec` processes. Isolation in Codex is a process sandbox, not a per-agent tool
list, so that script is the fence. Do not lose the execute bit.

Run it: `task detect` should print `codex`. Then
`task create-test-tickets` and `task run --`. Needs `codex` on PATH.

The design is
[solutions/sol1_enhancer_codex/SPEC.md](../../solutions/sol1_enhancer_codex/SPEC.md),
and
[IMPLEMENTATION_NOTES.md](../../solutions/sol1_enhancer_codex/IMPLEMENTATION_NOTES.md)
explains the sandbox.

## Grok build

```bash
cp -R ../../solutions/sol1_enhancer_grok_build/.grok .
cp ../../solutions/sol1_enhancer_grok_build/AGENTS.md .
cp ../../solutions/sol1_enhancer_grok_build/config.json.example .
```

`cp -R` copies the three symlinks under `.grok/agents/` and `.grok/skills/` as
symlinks, which is what you want. They point at
`../plugins/ticket-enhancer/`, so they keep working after the copy.

Two things Grok needs before this runs at all:

1. Trust the checkout. Run `grok` here once with no arguments and accept the
   prompt. Headless `grok -p` never prompts.
2. Confirm the names, not the counts:

   ```bash
   grok inspect | grep -E "enhancer-loop|enhancer-judge|enhancer-doer"
   ```

   All three must be listed. If they are not, the symlinks did not survive the
   copy.

Run it: `task detect` should print `grok`. Then
`task create-test-tickets` and `task run --`. Needs `grok` on PATH, not
`claude`.

The design is
[solutions/sol1_enhancer_grok_build/SPEC.md](../../solutions/sol1_enhancer_grok_build/SPEC.md),
and
[IMPLEMENTATION_NOTES.md](../../solutions/sol1_enhancer_grok_build/IMPLEMENTATION_NOTES.md)
explains plugin loading.

## OpenCode

```bash
cp -R ../../solutions/sol1_enhancer_opencode/.opencode .
cp ../../solutions/sol1_enhancer_opencode/opencode.json .
cp ../../solutions/sol1_enhancer_opencode/AGENTS.md .
cp ../../solutions/sol1_enhancer_opencode/config.json.example .
```

Isolation is the per-agent `permission` block: `edit: deny` and `bash: deny`
on the judge and the doer. Headless is `opencode run`, not the TUI.

Run it: `task detect` should print `opencode`. Then
`task create-test-tickets` and `task run --`. Needs `opencode` on PATH.

The design is
[solutions/sol1_enhancer_opencode/SPEC.md](../../solutions/sol1_enhancer_opencode/SPEC.md),
and
[IMPLEMENTATION_NOTES.md](../../solutions/sol1_enhancer_opencode/IMPLEMENTATION_NOTES.md)
explains loading and the judge jail.

## Visual Studio Code

```bash
cp -R ../../solutions/sol1_enhancer_vscode/.github .
cp -R ../../solutions/sol1_enhancer_vscode/.vscode .
cp ../../solutions/sol1_enhancer_vscode/AGENTS.md .
cp ../../solutions/sol1_enhancer_vscode/config.json.example .
mkdir -p bin
cp ../../solutions/sol1_enhancer_vscode/bin/fence_check.py bin/
```

`cp -R` copies the three symlinks under `.github/agents/` and `.github/skills/`
as symlinks, which is what you want. They point at
`../plugins/ticket-enhancer/`, so they keep working after the copy.

Two things VS Code needs before this runs at all:

1. Open **this folder** as the workspace, or run Copilot CLI from here.
   Skills are discovered from the workspace root.
2. Confirm the names:

   ```bash
   python3 bin/fence_check.py
   copilot skill list
   ```

   `enhancer-loop` must be listed. If it is not, the symlinks did not survive
   the copy, or Copilot started at the repo root.

The design is
[solutions/sol1_enhancer_vscode/SPEC.md](../../solutions/sol1_enhancer_vscode/SPEC.md),
and
[IMPLEMENTATION_NOTES.md](../../solutions/sol1_enhancer_vscode/IMPLEMENTATION_NOTES.md)
explains plugin loading.

## GitHub Copilot CLI

```bash
cp -R ../../solutions/sol1_enhancer_copilot_cli/.github .
cp ../../solutions/sol1_enhancer_copilot_cli/AGENTS.md .
cp ../../solutions/sol1_enhancer_copilot_cli/config.json.example .
mkdir -p bin
cp ../../solutions/sol1_enhancer_copilot_cli/bin/fence_check.py bin/
```

`cp -R` copies the three symlinks under `.github/agents/` and `.github/skills/`
as symlinks, which is what you want. They point at
`../plugins/ticket-enhancer/`, so they keep working after the copy.

Two things Copilot CLI needs before this runs at all:

1. Start `copilot` from **this folder**. Skills are discovered from cwd.
2. Confirm the names:

   ```bash
   python3 bin/fence_check.py
   copilot skill list
   ```

   `enhancer-loop` must be listed. If it is not, the symlinks did not survive
   the copy, or Copilot started at the repo root.

The design is
[solutions/sol1_enhancer_copilot_cli/SPEC.md](../../solutions/sol1_enhancer_copilot_cli/SPEC.md),
and
[IMPLEMENTATION_NOTES.md](../../solutions/sol1_enhancer_copilot_cli/IMPLEMENTATION_NOTES.md)
explains plugin loading.

## Google Antigravity

```bash
cp -R ../../solutions/sol1_enhancer_antigravity/.agents .
cp ../../solutions/sol1_enhancer_antigravity/AGENTS.md .
cp ../../solutions/sol1_enhancer_antigravity/config.json.example .
mkdir -p bin
cp ../../solutions/sol1_enhancer_antigravity/bin/fence_check.py bin/
```

`cp -R` copies the three symlinks under `.agents/agents/` and `.agents/skills/`
as symlinks, which is what you want. They point at
`../plugins/ticket-enhancer/`, so they keep working after the copy.

Two things Antigravity needs before this runs at all:

1. Open **this folder** as the workspace, or run `agy` from here.
   Skills are discovered from the workspace root.
2. Confirm the names:

   ```bash
   python3 bin/fence_check.py
   ```

   `enhancer-loop` must be listed. If it is not, the symlinks did not survive
   the copy, or `agy` started at the repo root.

The design is
[solutions/sol1_enhancer_antigravity/SPEC.md](../../solutions/sol1_enhancer_antigravity/SPEC.md),
and
[IMPLEMENTATION_NOTES.md](../../solutions/sol1_enhancer_antigravity/IMPLEMENTATION_NOTES.md)
explains plugin loading.

## Claude Agent SDK (take-home)

Do not copy these fences into this lab folder. Run the answer:

```bash
cd ../../solutions/sol1_enhancer_agent_sdk
cp config.json.example config.json   # fill in your GitHub username
echo 'ANTHROPIC_API_KEY=sk-ant-...' >> ../../.env
task setup
task table          # judge writes must print no
task test
task clone
task create-test-tickets
task run --
```

The build prompts are [prompts/agent-sdk.md](prompts/agent-sdk.md). The design
is
[solutions/sol1_enhancer_agent_sdk/SPEC.md](../../solutions/sol1_enhancer_agent_sdk/SPEC.md).

## LangChain Deep Agents (take-home)

Do not copy these fences into this lab folder. Run the answer:

```bash
cd ../../solutions/sol1_enhancer_deep_agents
cp config.json.example config.json   # fill in your GitHub username
echo 'ANTHROPIC_API_KEY=sk-ant-...' >> ../../.env
task setup
task table          # judge writes must print no
task test
task clone
task create-test-tickets
task run --
```

The build prompts are [prompts/deep-agents.md](prompts/deep-agents.md). The
design is
[solutions/sol1_enhancer_deep_agents/SPEC.md](../../solutions/sol1_enhancer_deep_agents/SPEC.md).
