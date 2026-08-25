from __future__ import annotations

import re

EMDASHES = ("\u2014", "\u2013", "---")


def strip_emdashes(text: str) -> str:
    out = text
    out = out.replace("\u2014", ". ")
    out = out.replace("\u2013", ", ")
    out = out.replace("---", ". ")
    out = re.sub(r" +", " ", out)
    out = re.sub(r" \.", ".", out)
    return out


def remaining_emdashes(text: str) -> list[str]:
    hits = []
    if "\u2014" in text:
        hits.append("em-dash")
    if "\u2013" in text:
        hits.append("en-dash")
    if "---" in text:
        hits.append("triple-hyphen")
    return hits


def first_use_expanded(text: str, abbr: str, expansion: str) -> bool:
    if abbr not in text and abbr.lower() not in text:
        return True
    pattern = re.compile(re.escape(expansion), re.I)
    abbr_pattern = re.compile(r"\b" + re.escape(abbr) + r"\b")
    first_abbr = abbr_pattern.search(text)
    if not first_abbr:
        return True
    first_exp = pattern.search(text)
    if first_exp is None:
        return False
    return first_exp.start() <= first_abbr.start()


def long_sentences(text: str, limit: int = 35) -> list[str]:
    body = text
    for fence in re.findall(r"```.*?```", body, flags=re.S):
        body = body.replace(fence, " ")
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", body) if s.strip()]
    return [s for s in sentences if len(s.split()) > limit]


def check_style(text: str) -> dict:
    issues: list[dict] = []
    for kind in remaining_emdashes(text):
        issues.append(
            {
                "severity": "critical",
                "id": f"emdash:{kind}",
                "description": f"Style enforcer found {kind}. Do not use em dashes.",
            }
        )
    if not first_use_expanded(text, "MCP", "Model Context Protocol"):
        issues.append(
            {
                "severity": "major",
                "id": "expand:MCP",
                "description": "Expand MCP to Model Context Protocol on first use.",
            }
        )
    if not first_use_expanded(text, "CRM", "customer relationship management"):
        issues.append(
            {
                "severity": "major",
                "id": "expand:CRM",
                "description": "Expand CRM to customer relationship management on first use.",
            }
        )
    for sentence in long_sentences(text):
        issues.append(
            {
                "severity": "major",
                "id": "sentence-length",
                "description": "One idea per sentence. This sentence is over 35 words.",
                "current_text": sentence[:120],
            }
        )
    blocking = [i for i in issues if i["severity"] in {"critical", "major"}]
    return {
        "status": "pass" if not blocking else "fail",
        "issues": issues,
        "failed_ids": [i["id"] for i in blocking],
        "passed": not blocking,
    }
