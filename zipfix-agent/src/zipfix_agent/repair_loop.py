"""Repair loop – orchestrates the full interactive pipeline.

Flow:
  1. Unzip project
  2. Ask user for repair prompt (terminal input)
  3. Analyse codebase structure (planner subagent)
  4. Create repair plan (planner subagent)
  5. Build custom skill (dynamic system prompt)
  6. Run fixer agent in a 3-iteration loop with before/after scoring
  7. Generate JSON + Markdown report

All steps are logged to the terminal so the user can see progress.
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

import shutil
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from zipfix_agent.agent import run_repair_agent
from zipfix_agent.analyzer import analyze_codebase, create_repair_plan
from zipfix_agent.checks import run_compile_check, run_pytest
from zipfix_agent.config import OUTPUTS_DIR, PROMPTS_DIR
from zipfix_agent.readme_writer import write_report
from zipfix_agent.schemas import RepairIteration, RepairResult, ScoreCard
from zipfix_agent.scoring import calculate_score
from zipfix_agent.skill_builder import build_custom_skill
from zipfix_agent.tools import detect_modified_files, file_hashes, is_test_file, list_project_files
from zipfix_agent.unzipper import safe_unzip

console = Console()


def _load_base_prompt() -> str:
    """Load the base fixer system prompt."""
    path = PROMPTS_DIR / "system_prompt.txt"
    return path.read_text(encoding="utf-8")


def _print_score_table(iterations: list[RepairIteration]) -> None:
    """Print a rich table summarising all iteration scores."""
    table = Table(title="📊 Iteration Scores", show_lines=True)
    table.add_column("Iteration", style="bold cyan", justify="center")
    table.add_column("Before", style="red", justify="center")
    table.add_column("After", style="green", justify="center")
    table.add_column("Tests", justify="center")
    table.add_column("Status", justify="center")

    for it in iterations:
        before_pct = f"{it.score_before.score:.0%}"
        after_pct = f"{it.score_after.score:.0%}"
        tests = f"{it.score_after.tests_passed}/{it.score_after.tests_total}"
        status = "✅" if it.score_after.score >= 1.0 else "🔧"
        table.add_row(str(it.iteration), before_pct, after_pct, tests, status)

    console.print(table)


async def repair_zip_project(
    zip_path: Path,
    max_iterations: int = 3,
) -> RepairResult:
    """End-to-end interactive repair pipeline for a zipped Python project.

    1. Safely unzip.
    2. Ask the user for their repair prompt.
    3. Analyse codebase (planner subagent).
    4. Create repair plan (planner subagent).
    5. Build custom skill (dynamic system prompt).
    6. Run fixer agent up to *max_iterations* times with scoring.
    7. Generate report.
    """
    project_name = zip_path.stem
    project_output_dir = OUTPUTS_DIR / project_name
    project_output_dir.mkdir(parents=True, exist_ok=True)

    # Copy original zip to the isolated output folder
    zip_copy_path = project_output_dir / zip_path.name
    shutil.copy2(zip_path, zip_copy_path)

    dest_dir = project_output_dir / "scratch_project"
    result = RepairResult(zip_path=str(zip_copy_path), project_name=project_name)

    try:
        pipeline_start = time.time()

        # ── 1. Unzip ──────────────────────────────────────────────────────
        console.rule("[bold]📦 Step 1: Unzipping project")
        console.print(f"  [dim]Source:[/dim] {zip_path}")
        console.print(f"  [dim]Copied to:[/dim] {zip_copy_path}")
        console.print(f"  [dim]Extracting to:[/dim] {dest_dir}")
        project_dir = safe_unzip(zip_copy_path, dest_dir)
        console.print(f"  [green]✔ Unzipped successfully[/green]")
        console.print(f"  [dim]Project root:[/dim] {project_dir}")

        files = list_project_files(project_dir)
        py_files = [f for f in files if f.endswith('.py')]
        test_files = [f for f in py_files if 'test' in f.lower()]
        console.print(f"  [dim]Total files:[/dim]  {len(files)}")
        console.print(f"  [dim]Python files:[/dim] {len(py_files)}")
        console.print(f"  [dim]Test files:[/dim]   {len(test_files)}")
        console.print()
        for f in files:
            icon = '🧪' if 'test' in f.lower() else '📄'
            console.print(f"    {icon} [dim]{f}[/dim]")

        # ── 2. Ask user for prompt ────────────────────────────────────────
        console.print()
        console.rule("[bold]💬 Step 2: What should I fix?")
        console.print(
            "\n[bold yellow]Describe what you want the agent to fix.[/]\n"
            "[dim]Examples:\n"
            "  • 'fix all failing tests'\n"
            "  • 'debug the calculator module'\n"
            "  • 'fix import errors and make tests pass'\n"
            "  • Press Enter for default prompt[/dim]\n"
        )
        user_prompt = input("🎯 Your prompt > ").strip()
        if not user_prompt:
            user_prompt = "Fix all failing tests and compilation errors. Make all tests pass."
            console.print(f"  [dim](Using default prompt)[/dim]")
        result.user_prompt = user_prompt
        console.print(f"\n  [bold]User prompt:[/bold] [cyan]{user_prompt}[/cyan]")

        # ── 3. Baseline checks ────────────────────────────────────────────
        console.print()
        console.rule("[bold]🔍 Step 3: Running baseline checks")
        console.print("  [dim]Running pytest...[/dim]")
        baseline_pytest = run_pytest(project_dir)
        console.print("  [dim]Running compile check...[/dim]")
        baseline_compile = run_compile_check(project_dir)
        score_before = calculate_score(baseline_pytest, baseline_compile)
        result.score_before = score_before

        console.print()
        console.print(Panel(
            f"pytest:  {'✅ PASSED' if baseline_pytest.passed else '❌ FAILED'}\n"
            f"compile: {'✅ PASSED' if baseline_compile.passed else '❌ FAILED'}\n"
            f"tests:   {score_before.tests_passed}/{score_before.tests_total} passed\n"
            f"score:   {score_before.score:.0%}",
            title="Baseline Score",
            border_style="red" if score_before.score < 1.0 else "green",
        ))

        # Show test failure details
        if not baseline_pytest.passed:
            console.print("  [bold red]Test failures:[/bold red]")
            # Show last 10 lines of pytest output (usually the summary)
            output_lines = baseline_pytest.output.strip().split('\n')
            for line in output_lines[-10:]:
                console.print(f"    [dim]{line}[/dim]")

        # ── 4. Analyse codebase (planner subagent) ────────────────────────
        console.print()
        console.rule("[bold]🧠 Step 4: Analysing codebase structure")
        console.print("  [dim]Planner subagent is reading the project files...[/dim]")
        codebase_summary = await analyze_codebase(project_dir)
        result.codebase_summary = codebase_summary
        console.print()
        console.print(Panel(
            codebase_summary[:800] + ('...' if len(codebase_summary) > 800 else ''),
            title="Codebase Summary",
            border_style="blue",
        ))

        # ── 5. Create repair plan (planner subagent) ──────────────────────
        console.print()
        console.rule("[bold]📝 Step 5: Creating repair plan")
        console.print("  [dim]Planner subagent is creating a step-by-step repair plan...[/dim]")
        repair_plan = await create_repair_plan(
            project_dir, user_prompt, codebase_summary, baseline_pytest.output,
        )
        result.repair_plan = repair_plan
        console.print()
        console.print(Panel(
            repair_plan[:1200] + ('...' if len(repair_plan) > 1200 else ''),
            title="Repair Plan",
            border_style="yellow",
        ))

        # ── 6. Build custom skill ─────────────────────────────────────────
        console.print()
        console.rule("[bold]🛠️  Step 6: Building custom skill")
        console.print("  [dim]Assembling: base rules + user prompt + codebase summary + repair plan[/dim]")
        base_prompt = _load_base_prompt()
        custom_skill = build_custom_skill(
            base_prompt, user_prompt, codebase_summary, repair_plan,
        )
        console.print(f"  [green]✔ Custom skill assembled[/green]  ({len(custom_skill)} chars)")
        console.print("  [dim]The fixer agent will use this as its system prompt.[/dim]")

        # ── 7. Snapshot before repairs ────────────────────────────────────
        hashes_before = file_hashes(project_dir)

        # ── 8. Iterative repair loop ──────────────────────────────────────
        for i in range(1, max_iterations + 1):
            console.print()
            console.rule(f"[bold]🔧 Repair Iteration {i}/{max_iterations}")
            iter_start = time.time()

            # Score before this iteration
            console.print("  [dim]Running pre-iteration checks...[/dim]")
            pre_pytest = run_pytest(project_dir)
            pre_compile = run_compile_check(project_dir)
            iter_score_before = calculate_score(pre_pytest, pre_compile)
            console.print(
                f"  [dim]Pre-score:[/dim] {iter_score_before.score:.0%}  "
                f"(tests: {iter_score_before.tests_passed}/{iter_score_before.tests_total})"
            )

            # Build iteration-specific prompt
            prompt_parts = [
                f"Repair iteration {i} of {max_iterations}.",
                f"Project directory: {project_dir}",
                "",
                "Current test output:",
                pre_pytest.output[:3000],
                "",
                "Current compile status:",
                pre_compile.output[:2000],
                "",
                "Follow the repair plan. Fix the issues and re-run pytest to verify.",
            ]
            prompt = "\n".join(prompt_parts)

            # Run fixer agent
            console.print("  [bold cyan]Launching fixer agent...[/bold cyan]")
            agent_response = await run_repair_agent(project_dir, prompt, custom_skill)

            # Score after this iteration
            console.print("  [dim]Running post-iteration checks...[/dim]")
            post_pytest = run_pytest(project_dir)
            post_compile = run_compile_check(project_dir)
            iter_score_after = calculate_score(post_pytest, post_compile)

            # Record iteration
            iteration = RepairIteration(
                iteration=i,
                agent_response=agent_response,
                score_before=iter_score_before,
                score_after=iter_score_after,
            )
            result.iterations.append(iteration)

            elapsed = time.time() - iter_start
            console.print()
            console.print(Panel(
                f"Before: {iter_score_before.score:.0%}  →  After: {iter_score_after.score:.0%}\n"
                f"Tests:  {iter_score_after.tests_passed}/{iter_score_after.tests_total} passed\n"
                f"Time:   {elapsed:.1f}s",
                title=f"Iteration {i} Result",
                border_style="green" if iter_score_after.score >= 1.0 else "yellow",
            ))

            # Early stop if everything passes
            if post_pytest.passed and post_compile.passed:
                console.print("[bold green]  ✅ All checks pass — stopping early![/bold green]")
                break

        # ── 9. Final bookkeeping ──────────────────────────────────────────
        console.print()
        console.rule("[bold]📊 Final Results")
        console.print("  [dim]Computing final scores and detecting changes...[/dim]")

        hashes_after = file_hashes(project_dir)
        modified = detect_modified_files(hashes_before, hashes_after)
        result.modified_files = modified
        result.test_files_modified = any(is_test_file(f) for f in modified)

        console.print("  [dim]Running final checks...[/dim]")
        final_pytest = run_pytest(project_dir)
        final_compile = run_compile_check(project_dir)
        result.score_after = calculate_score(final_pytest, final_compile)
        result.success = final_pytest.passed and final_compile.passed
        result.finished_at = datetime.utcnow()

        total_time = time.time() - pipeline_start

        # ── 10. Print summary table ───────────────────────────────────────
        console.print()
        _print_score_table(result.iterations)

        console.print()
        console.print(Panel(
            f"Success:    {'✅ YES' if result.success else '❌ NO'}\n"
            f"Score:      {result.score_before.score:.0%} → {result.score_after.score:.0%}\n"
            f"Iterations: {len(result.iterations)}\n"
            f"Time:       {total_time:.1f}s\n"
            f"Files changed: {len(modified)}",
            title="Pipeline Summary",
            border_style="green" if result.success else "red",
        ))

        if result.test_files_modified:
            console.print("[bold yellow]⚠️  Warning: Test files were modified![/bold yellow]")

        if modified:
            console.print("\n[bold]Modified files:[/bold]")
            for f in modified:
                console.print(f"  • {f}")

    except Exception as exc:
        result.error = str(exc)
        result.finished_at = datetime.utcnow()
        console.print(f"[bold red]Pipeline error: {exc}[/bold red]")

    # ── 11. Save JSON result ──────────────────────────────────────────────
    console.print()
    console.rule("[bold]💾 Saving outputs")
    json_path = project_output_dir / "result.json"
    json_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    console.print(f"  [green]✔[/green] JSON saved:   {json_path}")

    # ── 12. Generate report ───────────────────────────────────────────────
    report_path = project_output_dir / "README_REPORT.md"
    write_report(result, report_path)
    console.print(f"  [green]✔[/green] Report saved: {report_path}")
    console.print()

    return result
