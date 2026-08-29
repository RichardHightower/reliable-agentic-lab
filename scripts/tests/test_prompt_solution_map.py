"""Every solutions/sol*_ folder has one lab prompt. No leftovers.

Labs 2 to 4 still ship four Saturday fill-the-stub prompts (claude-code,
codex, grok-build, opencode). Those fill harness.py / loop.py. They are not
solution variants. This test does not require a sol2_implementer folder for
them.

The 1:1 this file pins is: solution variant -> labs/<lab>/prompts/<tool>.md.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOLUTIONS = ROOT / "solutions"
LABS = ROOT / "labs"

# Suffix on the solution folder -> prompt filename in the lab.
VARIANT_PROMPT = {
    "agent_sdk": "agent-sdk.md",
    "deep_agents": "deep-agents.md",
    "codex": "codex.md",
    "grok_build": "grok-build.md",
    "opencode": "opencode.md",
}


def _lab_and_prompt(sol_name: str) -> tuple[str, str]:
    """sol1_enhancer_codex -> (lab1_enhancer, codex.md)."""
    for suffix, prompt in VARIANT_PROMPT.items():
        token = f"_{suffix}"
        if sol_name.endswith(token):
            base = sol_name[: -len(token)]
            return base.replace("sol", "lab", 1), prompt
    return sol_name.replace("sol", "lab", 1), "claude-code.md"


def _solution_folders() -> list[str]:
    return sorted(
        p.name
        for p in SOLUTIONS.iterdir()
        if p.is_dir() and p.name.startswith("sol")
    )


def test_every_solution_variant_has_a_lab_prompt() -> None:
    missing: list[str] = []
    for name in _solution_folders():
        lab, prompt = _lab_and_prompt(name)
        path = LABS / lab / "prompts" / prompt
        if not path.is_file():
            missing.append(f"{name} -> {path.relative_to(ROOT)}")
    assert missing == [], (
        "solution variant with no lab prompt:\n  " + "\n  ".join(missing)
    )


def test_every_variant_prompt_names_its_solution_folder() -> None:
    hits: list[str] = []
    for name in _solution_folders():
        lab, prompt = _lab_and_prompt(name)
        path = LABS / lab / "prompts" / prompt
        text = path.read_text(encoding="utf-8")
        needle = f"solutions/{name}"
        if needle not in text:
            hits.append(f"{path.relative_to(ROOT)} does not mention {needle}")
    assert hits == [], "prompt does not name its solution folder:\n  " + "\n  ".join(
        hits
    )
