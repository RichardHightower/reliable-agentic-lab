"""The role objects. Kept as this name because older tests import it.

The implementation lives in `write_scope.py`. This module re-exports it so
the two files are not a silent byte-identical pair.
"""

from write_scope import *  # noqa: F403
from write_scope import (  # noqa: F401
    Doer,
    Judge,
    Orchestrator,
    Planner,
    Role,
    ScopeViolation,
    WriteScope,
    build,
)
