"""The SPEC names every fence by an identifier that exists in roles.py.

`SPEC.md` claims seven things this port enforces: no `Bash` on any role, a
subagent tool list replaces the parent list, per-role path scope on top of
that, the judge holds `read_file` only, `virtual_mode` is routing and not a
security boundary, orchestrator `permissions` deny writes, and the
general-purpose subagent is off. Each claim is written against one
identifier a reader can grep in `roles.py`, so the section cannot be
deleted or drift silently: delete it, and the first test below fails;
misspell one identifier, and it fails too.
"""

from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = (HERE.parent / "SPEC.md").read_text(encoding="utf-8")
ROLES_SOURCE = (HERE.parent / "roles.py").read_text(encoding="utf-8")

FENCE_IDENTIFIERS = [
    "write_file",
    "execute",
    "virtual_mode",
    "read_file",
    "ORCHESTRATOR_EXCLUDED_TOOLS",
    "general_purpose_subagent",
    "WriteScope",
    "scoped_write_tool",
    "permission_rules",
]

SCOPE_HEADING = "How this runtime enforces scope"


def test_the_spec_names_every_fence_identifier():
    for identifier in FENCE_IDENTIFIERS:
        assert identifier in SPEC, f"SPEC.md no longer names {identifier!r}"


def test_every_fence_identifier_exists_in_roles():
    for identifier in FENCE_IDENTIFIERS:
        assert identifier in ROLES_SOURCE, f"roles.py no longer defines {identifier!r}"


def test_the_spec_has_the_scope_section():
    assert SCOPE_HEADING in SPEC
