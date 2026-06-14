"""Codebase analyser and repair planner – uses the planner subagent."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console

from zipfix_agent.agent import run_planner_agent
from zipfix_agent.config import PROMPTS_DIR
from zipfix_agent.tools import list_project_files

console = Console()


def _load_planner_prompt() -> str:
    """Load the planner system prompt from disk."""
    path = PROMPTS_DIR / "planner_prompt.txt"
    return path.read_text(encoding="utf-8")


async def analyze_codebase(project_dir: Path) -> str:
    """Use the planner subagent to read and summarise the project structure.

    Returns a structured summary with: file tree, main modules, test
    coverage, dependencies, and obvious error patterns.
    """
    files = list_project_files(project_dir)
    file_tree = "\n".join(f"  - {f}" for f in files)

    prompt = (
        f"Analyse this Python project at: {project_dir}\n\n"
        f"File tree:\n{file_tree}\n\n"
        "Read the key source files and test files. "
        "Return a structured summary with:\n"
        "1. What the project does (1-2 sentences)\n"
        "2. Main modules and their purpose\n"
        "3. Test files and what they test\n"
        "4. Any dependencies (from requirements.txt or pyproject.toml if present)\n"
        "5. Any obvious issues you spot (syntax errors, import errors, etc.)\n\n"
        "Keep it concise — this is for planning, not a full audit."
    )

    system_prompt = _load_planner_prompt()
    console.print("[bold magenta]📋 Analysing codebase structure...[/]")
    summary = await run_planner_agent(project_dir, prompt, system_prompt)
    return summary


async def create_repair_plan(
    project_dir: Path,
    user_prompt: str,
    codebase_summary: str,
    test_output: str,
) -> str:
    """Use the planner subagent to create a numbered repair plan.

    Parameters
    ----------
    project_dir:
        Path to the extracted project.
    user_prompt:
        The user's repair instructions from terminal input.
    codebase_summary:
        Output from ``analyze_codebase()``.
    test_output:
        The raw pytest output showing failures.

    Returns
    -------
    str
        A numbered, step-by-step repair plan.
    """
    prompt = (
        f"Create a repair plan for this Python project at: {project_dir}\n\n"
        f"## User's Request\n{user_prompt}\n\n"
        f"## Codebase Summary\n{codebase_summary}\n\n"
        f"## Current Test Output\n{test_output[:3000]}\n\n"
        "Based on the above, create a numbered step-by-step repair plan.\n"
        "For each step, specify:\n"
        "- The exact file to change\n"
        "- The function or section to modify\n"
        "- What the fix should be\n\n"
        "Read the actual source files to confirm your analysis before planning.\n"
        "Output ONLY the repair plan — no code edits."
    )

    system_prompt = _load_planner_prompt()
    console.print("[bold magenta]📝 Creating repair plan...[/]")
    plan = await run_planner_agent(project_dir, prompt, system_prompt)
    return plan
