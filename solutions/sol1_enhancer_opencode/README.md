# sol1_enhancer_opencode

An OpenCode-native ticket enhancer is coming soon. This folder is a stub.

It used to hold a generated Python port, `loop.py` and friends. That shape no
longer matches Lab 1, whose answer is a plugin or a skill set rather than a
Python stub, so the stale files are gone rather than left to mislead you.

Need a working answer this weekend? Use
[solutions/sol1_enhancer](../sol1_enhancer), the Claude Code plugin. It is the
reference answer for Lab 1, and
[its SPEC.md](../sol1_enhancer/SPEC.md) is the full design.

The other two tool answers are built, if you want to compare how each product
expresses the same loop:

- [sol1_enhancer_codex](../sol1_enhancer_codex), a Codex skill set under
  `.agents/`, with each role in its own sandboxed process.
- [sol1_enhancer_grok_build](../sol1_enhancer_grok_build), a Grok Build project
  plugin under `.grok/`, with three registration symlinks.
