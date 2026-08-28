# Lab 1 answer: the ticket enhancer, as a Grok Build plugin

A vague ticket goes in, a ready contract comes out. Nobody sits in an
interactive session watching it. The loop polls the ticket's GitHub issue for
comments and acts on what it finds.

The artifact is a Grok Build **project plugin** named `ticket-enhancer`, in
`.grok/plugins/ticket-enhancer/`. It holds one skill and two agents. This
folder is standalone: it depends on nothing in the repository root and can be
lifted out as its own repository.

`solutions/sol1_enhancer/` is the same loop built as a Claude Code plugin.
Same three roles, same rubric, same two gate scripts.

## Start here

1. [IMPLEMENTATION_NOTES.md](IMPLEMENTATION_NOTES.md). Read this first if
   `task run` does nothing. A project plugin needs a trusted checkout, and
   headless Grok never asks for that trust.
2. [HOW_TO_RUN.md](HOW_TO_RUN.md). Set up your fork, run one poll, keep it
   polling.
3. [SPEC.md](SPEC.md). The design: the three roles, the three exits, and what
   "ready" means per ticket kind.

## The short version

```bash
task trust                 # step zero, once per checkout
cp config.json.example config.json   # fill in your GitHub username
task clone
task create-test-tickets
task run --
```
