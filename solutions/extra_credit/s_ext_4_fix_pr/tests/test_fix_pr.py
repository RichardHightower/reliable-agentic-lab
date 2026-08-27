"""Extra credit 4. The PR fixer, driven locally."""

from __future__ import annotations

import pytest

from solutions.extra_credit import TARGET
from solutions.extra_credit.s_ext_4_fix_pr import fix_pr

needs_target = pytest.mark.skipif(
    not TARGET.exists(), reason="run `task setup` to clone the target repo"
)


@needs_target
def test_local_fixer_reference(tmp_path, monkeypatch):
    monkeypatch.setattr(fix_pr, "WORK", tmp_path)
    payload = fix_pr.run_local("T001", doer="reference", budget=2)
    assert payload["green"] is True
    assert (tmp_path / "last-fix.json").exists()
