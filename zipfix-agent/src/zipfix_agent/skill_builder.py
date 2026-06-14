"""Skill builder – assembles a custom system prompt for the fixer agent.

Combines the base repair rules with the user's intent, codebase structure,
and the planner's repair plan into a single system prompt (the "custom skill").
"""

from __future__ import annotations


def build_custom_skill(
    base_prompt: str,
    user_prompt: str,
    codebase_summary: str,
    repair_plan: str,
) -> str:
    """Combine base rules + user intent + structure + plan into one system prompt.

    Parameters
    ----------
    base_prompt:
        The base fixer rules from ``prompts/system_prompt.txt``.
    user_prompt:
        What the user asked for in the terminal.
    codebase_summary:
        The analyser's structured summary of the project.
    repair_plan:
        The planner subagent's step-by-step repair plan.

    Returns
    -------
    str
        The assembled system prompt to pass to the fixer agent.
    """
    sections = [
        base_prompt.strip(),
        "",
        "---",
        "",
        "## User's Request",
        user_prompt.strip(),
        "",
        "---",
        "",
        "## Codebase Structure",
        codebase_summary.strip(),
        "",
        "---",
        "",
        "## Repair Plan (follow these steps)",
        repair_plan.strip(),
        "",
        "---",
        "",
        "Execute the repair plan above step by step.",
        "After each file edit, run pytest to verify.",
        "If a step doesn't apply or is already fixed, skip it.",
    ]

    return "\n".join(sections)
