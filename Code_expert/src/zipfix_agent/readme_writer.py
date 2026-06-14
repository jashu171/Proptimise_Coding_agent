"""Generate a human-readable README_REPORT.md for a completed repair."""

from __future__ import annotations

from pathlib import Path

from zipfix_agent.schemas import RepairResult


def write_report(result: RepairResult, output_path: Path) -> Path:
    """Write *result* as a Markdown report and return the file path."""
    lines: list[str] = [
        f"# ZipFix Repair Report – {result.project_name}",
        "",
        f"**Zip file:** `{result.zip_path}`  ",
        f"**Started:** {result.started_at.isoformat()}  ",
        f"**Finished:** {result.finished_at.isoformat() if result.finished_at else 'N/A'}  ",
        f"**Success:** {'✅ Yes' if result.success else '❌ No'}  ",
        "",
        "---",
        "",
        "## User's Prompt",
        "",
        f"> {result.user_prompt}" if result.user_prompt else "> (no prompt provided)",
        "",
        "---",
        "",
        "## Codebase Summary",
        "",
    ]

    if result.codebase_summary:
        lines.append(result.codebase_summary)
    else:
        lines.append("_No codebase summary generated._")

    lines.extend(["", "---", ""])

    # ── Repair Plan ──────────────────────────────────────────────────────
    lines.extend([
        "## Repair Plan",
        "",
    ])
    if result.repair_plan:
        lines.append(result.repair_plan)
    else:
        lines.append("_No repair plan generated._")

    lines.extend(["", "---", ""])

    # ── Scores ────────────────────────────────────────────────────────────
    lines.extend([
        "## Scores",
        "",
        "| Metric | Before | After |",
        "|--------|--------|-------|",
        f"| Tests passed | {result.score_before.tests_passed}/{result.score_before.tests_total} "
        f"| {result.score_after.tests_passed}/{result.score_after.tests_total} |",
        f"| Compile OK | {'✅' if result.score_before.compile_ok else '❌'} "
        f"| {'✅' if result.score_after.compile_ok else '❌'} |",
        f"| Score | {result.score_before.score:.2%} | {result.score_after.score:.2%} |",
        "",
        "---",
        "",
    ])

    # ── Iteration details ─────────────────────────────────────────────────
    if result.iterations:
        lines.extend([
            "## Iteration Scores",
            "",
            "| Iteration | Before | After | Tests | Status |",
            "|-----------|--------|-------|-------|--------|",
        ])
        for it in result.iterations:
            status = "✅" if it.score_after.score >= 1.0 else "🔧"
            lines.append(
                f"| {it.iteration} "
                f"| {it.score_before.score:.0%} "
                f"| {it.score_after.score:.0%} "
                f"| {it.score_after.tests_passed}/{it.score_after.tests_total} "
                f"| {status} |"
            )
        lines.extend(["", "---", ""])

    # ── Modified files ────────────────────────────────────────────────────
    lines.extend([
        "## Modified Files",
        "",
    ])
    if result.modified_files:
        for f in result.modified_files:
            lines.append(f"- `{f}`")
    else:
        lines.append("_No files were modified._")

    if result.test_files_modified:
        lines.extend([
            "",
            "> ⚠️ **Warning:** Test files were modified – this may violate the rules.",
        ])

    lines.extend(["", "---", ""])

    # ── Iteration detail sections ─────────────────────────────────────────
    for it in result.iterations:
        lines.extend([
            f"## Iteration {it.iteration} – Detail",
            "",
            f"**Score before:** {it.score_before.score:.2%}  ",
            f"**Score after:** {it.score_after.score:.2%}  ",
            "",
            "<details>",
            "<summary>Agent response</summary>",
            "",
            "```",
            it.agent_response if it.agent_response else "(no response)",
            "```",
            "",
            "</details>",
            "",
        ])

    # ── Error ─────────────────────────────────────────────────────────────
    if result.error:
        lines.extend([
            "## Error",
            "",
            f"```\n{result.error}\n```",
            "",
        ])

    report_text = "\n".join(lines) + "\n"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report_text, encoding="utf-8")
    return output_path
