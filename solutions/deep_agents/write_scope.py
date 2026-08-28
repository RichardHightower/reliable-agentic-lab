"""Write scope. Copied into this folder on purpose.

Do not import this from another package. If another folder needs it, copy the file.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from pathlib import PurePosixPath


class ScopeViolation(PermissionError):
    """A role tried to write outside its declared scope."""


def _matches(relative: str, patterns: list[str]) -> bool:
    """Glob match with `**` meaning "any depth", the way .loop.yml reads."""
    path = PurePosixPath(relative)
    for pattern in patterns:
        if fnmatch.fnmatch(relative, pattern):
            return True
        # `tests/**` should also match `tests/a.py`, not only `tests/a/b.py`.
        if pattern.endswith("/**") and (
            relative == pattern[:-3] or relative.startswith(pattern[:-2])
        ):
            return True
        if pattern == "**":
            return True
        try:
            if path.match(pattern):
                return True
        except ValueError:
            pass
    return False


@dataclass(frozen=True)
class WriteScope:
    """What one role may write. Deny always beats allow."""

    allow: list[str] = field(default_factory=list)
    deny: list[str] = field(default_factory=list)

    def permits(self, relative: str) -> bool:
        relative = str(PurePosixPath(relative))
        if _matches(relative, self.deny):
            return False
        return _matches(relative, self.allow)

    def check(self, relative: str) -> None:
        if not self.permits(relative):
            raise ScopeViolation(
                f"write to {relative} is outside this role's scope "
                f"(allow={self.allow or 'nothing'}, deny={self.deny or 'nothing'})"
            )
