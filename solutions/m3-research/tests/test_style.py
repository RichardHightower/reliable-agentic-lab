from pathlib import Path
import sys

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

from style_enforcer import check_style, strip_emdashes


def test_enforcer_strips_emdash():
    cleaned = strip_emdashes("Store dates UTC\u2014then filter overdue.")
    assert "\u2014" not in cleaned


def test_style_fails_on_emdash():
    verdict = check_style("Hello\u2014world.")
    assert verdict["passed"] is False
    assert "emdash:em-dash" in verdict["failed_ids"]


def test_style_requires_mcp_expansion():
    verdict = check_style("The agent uses MCP to search.")
    assert verdict["passed"] is False
    assert "expand:MCP" in verdict["failed_ids"]


def test_style_passes_workshop_report():
    text = (
        "Research ran in a sub-agent over Model Context Protocol (MCP). "
        "The checker has no write tools."
    )
    assert check_style(text)["passed"] is True
