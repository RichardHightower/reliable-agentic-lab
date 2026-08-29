# Lab 1 answer: the ticket enhancer, as a GitHub Copilot CLI plugin

A vague ticket goes in, a ready contract comes out. Nobody sits in an
interactive session watching it. The loop polls the ticket's GitHub issue for
comments and acts on what it finds.

The artifact is a GitHub Copilot CLI **agent plugin** named `ticket-enhancer`,
in `.github/plugins/ticket-enhancer/`. It holds one skill and two custom
agents. This folder is standalone: it depends on nothing in the repository
root and can be lifted out as its own repository.

`solutions/sol1_enhancer/` is the same loop built as a Claude Code plugin.
Same three roles, same rubric, same two gate scripts as the other Lab 1
product ports. Copilot CLI uses the CLI tool aliases (`read`, `search`,
`edit`, `execute`, `agent`) rather than the VS Code ids (`search/codebase`,
`runCommands`).

## Start here

1. [IMPLEMENTATION_NOTES.md](IMPLEMENTATION_NOTES.md). Read this first if
   `copilot skill list` does not name `enhancer-loop`. Copilot CLI loads
   project skills from `.github/skills/`, not from the plugin directory alone.
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
