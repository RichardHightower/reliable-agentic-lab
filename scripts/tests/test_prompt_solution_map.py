"""Every solutions/sol*_ and extra_credit/s_ext_* folder has one lab prompt.

Labs 2 to 4 still ship four Saturday fill-the-stub prompts (claude-code,
codex, grok-build, opencode). Those fill harness.py / loop.py. They are not
solution variants. Extra credit keeps the same four as a pick-a-tool
launcher. This test does not require a sol2_implementer folder for them.

The 1:1 this file pins is: solution variant -> labs/<lab>/prompts/<file>.md.
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
    "vscode": "vscode.md",
    "copilot_cli": "copilot-cli.md",
    "antigravity": "antigravity.md",
}


def _lab_and_prompt(sol_name: str) -> tuple[str, str]:
    """sol1_enhancer_codex -> (lab1_enhancer, codex.md)."""
    for suffix, prompt in VARIANT_PROMPT.items():
        token = f"_{suffix}"
        if sol_name.endswith(token):
            base = sol_name[: -len(token)]
            return base.replace("sol", "lab", 1), prompt
    return sol_name.replace("sol", "lab", 1), "claude-code.md"


def _pairs() -> list[tuple[str, Path, str]]:
    """(citation, prompt path, label) for every solution variant."""
    pairs: list[tuple[str, Path, str]] = []
    for path in sorted(SOLUTIONS.iterdir()):
        if not path.is_dir() or not path.name.startswith("sol"):
            continue
        lab, prompt = _lab_and_prompt(path.name)
        pairs.append(
            (
                f"solutions/{path.name}",
                LABS / lab / "prompts" / prompt,
                path.name,
            )
        )
    extra = SOLUTIONS / "extra_credit"
    if extra.is_dir():
        for path in sorted(extra.iterdir()):
            if not path.is_dir() or not path.name.startswith("s_ext_"):
                continue
            rest = path.name[len("s_ext_") :]  # 1_webhook
            number, slug = rest.split("_", 1)
            prompt = f"ext{number}-{slug}.md"
            pairs.append(
                (
                    f"solutions/extra_credit/{path.name}",
                    LABS / "extra-credit" / "prompts" / prompt,
                    path.name,
                )
            )
    return pairs


def test_every_solution_variant_has_a_lab_prompt() -> None:
    missing: list[str] = []
    for _citation, path, name in _pairs():
        if not path.is_file():
            missing.append(f"{name} -> {path.relative_to(ROOT)}")
    assert missing == [], (
        "solution variant with no lab prompt:\n  " + "\n  ".join(missing)
    )


def test_every_variant_prompt_names_its_solution_folder() -> None:
    hits: list[str] = []
    for citation, path, _name in _pairs():
        text = path.read_text(encoding="utf-8")
        if citation not in text:
            hits.append(f"{path.relative_to(ROOT)} does not mention {citation}")
    assert hits == [], "prompt does not name its solution folder:\n  " + "\n  ".join(
        hits
    )
