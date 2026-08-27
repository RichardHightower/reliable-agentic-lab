from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def fake_langchain(monkeypatch: pytest.MonkeyPatch):
    def tool(name_or_func=None):
        if callable(name_or_func):
            return name_or_func
        return lambda func: func

    module = types.ModuleType("langchain.tools")
    module.tool = tool
    package = types.ModuleType("langchain")
    package.tools = module
    monkeypatch.setitem(sys.modules, "langchain", package)
    monkeypatch.setitem(sys.modules, "langchain.tools", module)
    return module
