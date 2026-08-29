# Lab 1 answer: the ticket enhancer, as a Google Antigravity plugin

A vague ticket goes in, a ready contract comes out. Nobody sits in an
interactive session watching it. The loop polls the ticket's GitHub issue for
comments and acts on what it finds.

The artifact is a Google Antigravity **plugin** named `ticket-enhancer`,
in `.agents/plugins/ticket-enhancer/`. It holds one skill and two custom
subagents. This folder is standalone: it depends on nothing in the repository
root and can be lifted out as its own repository.

`solutions/sol1_enhancer/` is the same loop built as a Claude Code plugin.
`solutions/sol1_enhancer_copilot_cli/` is the same loop as a Copilot CLI plugin.
Same three roles, same rubric, same two gate scripts. Antigravity isolation
is `view_file` + `grep_search`, with `invoke_subagent` as the spawn tool.

## Start here

1. [IMPLEMENTATION_NOTES.md](IMPLEMENTATION_NOTES.md). Read this first if
   `/enhancer-loop` does not appear. Antigravity loads workspace skills from
   `.agents/skills/`, not from the plugin directory alone.
2. [HOW_TO_RUN.md](HOW_TO_RUN.md). Set up your fork, run one poll, keep it
   polling.
3. [SPEC.md](SPEC.md). The design: the three roles, the three exits, and what
   "ready" means per ticket kind.

## The short version

```bash
task inspect               # step zero, the three names on disk
cp config.json.example config.json   # fill in your GitHub username
task clone
task create-test-tickets
task run --
```
