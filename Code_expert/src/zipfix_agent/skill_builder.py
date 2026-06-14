"""Skill builder – assembles the system prompt for the fixer agent."""

from __future__ import annotations


def build_single_shot_skill(base_prompt: str) -> str:
    """Build a minimal, token-efficient system prompt for the single-shot fixer agent."""
    return "\n".join([
        base_prompt.strip(),
        "",
        "## RULES",
        "- Use ONLY relative paths in every tool call. NEVER absolute paths.",
        "- When calling Read: omit pages param (reads whole file) or use '1-100'. NEVER pages=''.",
        "- Do NOT read .pyc or binary files.",
        "- Fix only source files. Never edit test files.",
        "- After all edits, run `pytest` to verify.",
        "- If tool calls are not available and you must answer with text, return ONLY JSON in this shape:",
        '  {"edits":[{"file_path":"relative/path.py","old_string":"exact old text","new_string":"replacement text"}]}',
        "- Never return fake tool-call JSON as plain text.",
    ])


# Keep legacy function for backwards compatibility
def build_custom_skill(
    base_prompt: str,
    user_prompt: str,
    codebase_summary: str,
    repair_plan: str,
) -> str:
    return build_single_shot_skill(base_prompt)
