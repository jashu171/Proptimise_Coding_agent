"""Repair loop – iterative repair pipeline.

Flow:
  1. Unzip project
  2. Ask user for repair prompt (terminal input)
  3. Run baseline pytest to get failure output
  4. Read all source files locally (no LLM call)
  5. Run fixer agent, then verify and score
  6. Repeat up to 3 iterations until tests and compile pass
  7. Save JSON + Markdown report
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

import shutil
from rich.console import Console
from rich.panel import Panel

from zipfix_agent.agent import run_repair_agent
from zipfix_agent.checks import run_compile_check, run_pytest
from zipfix_agent.config import BASH_MAX_OUTPUT, MAX_OUTPUT_TOKENS, MODEL, OUTPUTS_DIR, PROMPTS_DIR
from zipfix_agent.readme_writer import write_report
from zipfix_agent.schemas import RepairIteration, RepairResult
from zipfix_agent.scoring import calculate_score
from zipfix_agent.skill_builder import build_single_shot_skill
from zipfix_agent.tools import detect_modified_files, file_hashes, is_test_file, list_project_files
from zipfix_agent.unzipper import safe_unzip

console = Console()
MAX_REPAIR_ITERATIONS = 3


def _load_base_prompt() -> str:
    path = PROMPTS_DIR / "system_prompt.txt"
    return path.read_text(encoding="utf-8")


def _read_project_files(project_dir: Path) -> str:
    """Read all non-binary, non-test source files and return them as a compact string."""
    SKIP_DIRS = {"__pycache__", ".venv", ".git", "node_modules", ".pytest_cache"}
    SKIP_EXTS = {".pyc", ".pyo", ".zip", ".egg", ".png", ".jpg", ".jpeg", ".gif", ".svg",
                 ".pdf", ".DS_Store"}
    max_file_chars = int(os.getenv("ZIPFIX_MAX_FILE_CHARS", str(BASH_MAX_OUTPUT)))

    parts = []
    for f in sorted(project_dir.rglob("*")):
        if not f.is_file():
            continue
        if any(p in SKIP_DIRS for p in f.parts):
            continue
        if f.suffix in SKIP_EXTS:
            continue
        try:
            content = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        rel = f.relative_to(project_dir)
        truncated = content[:max_file_chars]
        if len(content) > max_file_chars:
            truncated += "\n... [truncated]"
        parts.append(f"### {rel}\n```\n{truncated}\n```")

    return "\n\n".join(parts)


def _extract_json_payloads(text: str) -> list[object]:
    """Extract JSON objects/lists from plain or fenced model output."""
    candidates = re.findall(r"```(?:json)?\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
    stripped = text.strip()
    if stripped:
        candidates.append(stripped)

    payloads: list[object] = []
    for candidate in candidates:
        raw = candidate.strip()
        if not raw:
            continue
        try:
            payloads.append(json.loads(raw))
            continue
        except json.JSONDecodeError:
            pass

        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end > start:
            try:
                payloads.append(json.loads(raw[start:end + 1]))
            except json.JSONDecodeError:
                continue

    return payloads


def _safe_source_path(project_dir: Path, raw_path: str) -> Path | None:
    """Resolve a model-provided path and reject unsafe/test-file targets."""
    candidate = Path(raw_path)
    if candidate.is_absolute() or ".." in candidate.parts:
        console.print(f"[yellow]Ignoring unsafe edit path:[/] {raw_path}")
        return None

    resolved = (project_dir / candidate).resolve()
    try:
        rel = resolved.relative_to(project_dir.resolve())
    except ValueError:
        console.print(f"[yellow]Ignoring edit outside project:[/] {raw_path}")
        return None

    if is_test_file(str(rel)):
        console.print(f"[yellow]Ignoring attempted test edit:[/] {rel}")
        return None
    return resolved


def _normalise_text_edits(payload: object) -> list[dict[str, object]]:
    """Convert supported text-edit JSON shapes into a list of edit dicts."""
    if isinstance(payload, list):
        edits: list[dict[str, object]] = []
        for item in payload:
            edits.extend(_normalise_text_edits(item))
        return edits

    if not isinstance(payload, dict):
        return []

    if isinstance(payload.get("edits"), list):
        edits = []
        for item in payload["edits"]:
            if isinstance(item, dict):
                edits.append(item)
        return edits

    args = payload.get("arguments")
    if isinstance(args, dict):
        return [args]

    return [payload]


def _apply_text_edit_fallback(project_dir: Path, agent_response: str) -> list[str]:
    """Apply safe JSON text edits when a local model cannot invoke SDK tools.

    Supported response shapes:
    - {"edits": [{"file_path": "...", "old_string": "...", "new_string": "..."}]}
    - {"edits": [{"file_path": "...", "content": "full replacement"}]}
    - {"file_path": "...", "content": "full replacement"}
    - {"name": "Edit...", "arguments": {"file_path": "...", "old_string": "...", "new_string": "..."}}
    """
    changed: list[str] = []

    for payload in _extract_json_payloads(agent_response):
        for edit in _normalise_text_edits(payload):
            raw_path = edit.get("file_path") or edit.get("path")
            if not isinstance(raw_path, str):
                continue

            target = _safe_source_path(project_dir, raw_path)
            if target is None:
                continue

            rel = str(target.relative_to(project_dir))
            content = edit.get("content")
            if isinstance(content, str):
                if not content.endswith("\n"):
                    content += "\n"
                before = target.read_text(encoding="utf-8", errors="ignore") if target.exists() else ""
                if before != content:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(content, encoding="utf-8")
                    changed.append(rel)
                continue

            old_string = edit.get("old_string")
            new_string = edit.get("new_string")
            if isinstance(old_string, str) and isinstance(new_string, str):
                if not target.exists():
                    console.print(f"[yellow]Fallback edit target missing:[/] {rel}")
                    continue
                before = target.read_text(encoding="utf-8", errors="ignore")
                if old_string not in before:
                    console.print(f"[yellow]Fallback old_string not found in:[/] {rel}")
                    continue
                replace_all = bool(edit.get("replace_all", False))
                after = before.replace(old_string, new_string) if replace_all else before.replace(old_string, new_string, 1)
                if after != before:
                    target.write_text(after, encoding="utf-8")
                    changed.append(rel)

    return sorted(set(changed))


def _snapshot_source_files(project_dir: Path) -> dict[str, bytes]:
    """Capture source-file bytes so a non-improving iteration can be reverted."""
    snapshot: dict[str, bytes] = {}
    for path in project_dir.rglob("*"):
        if not path.is_file():
            continue
        rel = str(path.relative_to(project_dir))
        if "__pycache__" in path.parts or ".pytest_cache" in path.parts:
            continue
        if path.suffix in {".pyc", ".pyo"}:
            continue
        if is_test_file(rel):
            continue
        snapshot[rel] = path.read_bytes()
    return snapshot


def _restore_source_snapshot(project_dir: Path, snapshot: dict[str, bytes]) -> list[str]:
    """Restore source files from a prior snapshot."""
    restored: list[str] = []
    for rel, content in snapshot.items():
        path = project_dir / rel
        current = path.read_bytes() if path.exists() else None
        if current != content:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            restored.append(rel)
    return restored


def _source_repair_targets(project_dir: Path) -> list[Path]:
    """Return Python source files the repair loop is allowed to replace."""
    targets: list[Path] = []
    for path in sorted(project_dir.rglob("*.py")):
        rel = str(path.relative_to(project_dir))
        if "__pycache__" in path.parts or ".pytest_cache" in path.parts:
            continue
        if is_test_file(rel):
            continue
        targets.append(path)
    return targets


def _extract_code_response(text: str) -> str:
    """Extract a full-file code response from a model message."""
    match = re.search(r"```(?:python|py)?\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
    if match:
        text = match.group(1)
    return text.strip() + "\n"


def _request_full_file_repair(
    file_path: str,
    file_content: str,
    user_prompt: str,
    pytest_output: str,
    compile_output: str,
) -> str | None:
    """Ask LiteLLM directly for one full-file replacement."""
    base_url = os.getenv("ANTHROPIC_BASE_URL", "http://localhost:4000").rstrip("/")
    master_key = os.getenv("LITELLM_MASTER_KEY", "sk-local-zipfix-key")
    model = os.getenv("MODEL", MODEL)

    prompt = (
        "You are repairing one Python source file. Return ONLY the complete corrected "
        "file content. Do not return markdown explanations, JSON, shell commands, or tests. "
        "Do not add pytest imports, test functions, examples, or demo code to source files.\n\n"
        f"User task:\n{user_prompt}\n\n"
        f"Target file: {file_path}\n\n"
        f"Current pytest output:\n{pytest_output}\n\n"
        f"Current compile output:\n{compile_output}\n\n"
        f"Current file content:\n```python\n{file_content}\n```\n"
    )
    payload = json.dumps({
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Return only source code for the requested file. Preserve existing "
                    "public names and signatures. Fix the failing tests by changing implementation "
                    "source code only. Do not add tests or pytest code to source files."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "max_tokens": MAX_OUTPUT_TOKENS,
        "temperature": 0,
        "stream": False,
    }).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url}/v1/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {master_key}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        console.print(f"[yellow]Full-file fallback request failed:[/] {exc}")
        return None

    choices = body.get("choices", []) if isinstance(body, dict) else []
    if not choices:
        return None
    content = choices[0].get("message", {}).get("content", "")
    if not isinstance(content, str) or not content.strip():
        return None
    return _extract_code_response(content)


def _candidate_contains_test_code(content: str) -> bool:
    """Reject full-file source candidates that smuggle test code into source files."""
    suspicious_patterns = [
        r"^\s*import\s+pytest\b",
        r"^\s*from\s+pytest\s+import\b",
        r"^\s*def\s+test_",
        r"\bpytest\.",
        r"\bwith\s+pytest\.raises\b",
    ]
    return any(re.search(pattern, content, flags=re.MULTILINE) for pattern in suspicious_patterns)


def _try_validated_full_file_repair(
    project_dir: Path,
    user_prompt: str,
    pytest_result,
    compile_result,
    current_score,
) -> tuple[list[str], object, object, object]:
    """Try full-file replacements and keep only candidates that improve score."""
    changed: list[str] = []
    best_pytest = pytest_result
    best_compile = compile_result
    best_score = current_score

    for target in _source_repair_targets(project_dir):
        rel = str(target.relative_to(project_dir))
        original = target.read_text(encoding="utf-8", errors="ignore")
        candidate = _request_full_file_repair(
            file_path=rel,
            file_content=original,
            user_prompt=user_prompt,
            pytest_output=best_pytest.output,
            compile_output=best_compile.output,
        )
        if candidate is None or candidate == original:
            continue
        if _candidate_contains_test_code(candidate):
            console.print(f"[yellow]Rejected full-file fallback containing test code:[/] {rel}")
            continue

        target.write_text(candidate, encoding="utf-8")
        candidate_pytest = run_pytest(project_dir)
        candidate_compile = run_compile_check(project_dir)
        candidate_score = calculate_score(candidate_pytest, candidate_compile)

        if candidate_pytest.passed and candidate_compile.passed:
            changed.append(rel)
            return changed, candidate_pytest, candidate_compile, candidate_score

        if candidate_score.score > best_score.score:
            changed.append(rel)
            best_pytest = candidate_pytest
            best_compile = candidate_compile
            best_score = candidate_score
            continue

        target.write_text(original, encoding="utf-8")

    return sorted(set(changed)), best_pytest, best_compile, best_score


async def repair_zip_project(zip_path: Path) -> RepairResult:
    """Iterative repair pipeline for a zipped Python project."""
    project_name = zip_path.stem
    project_output_dir = OUTPUTS_DIR / project_name
    project_output_dir.mkdir(parents=True, exist_ok=True)

    zip_copy_path = project_output_dir / zip_path.name
    shutil.copy2(zip_path, zip_copy_path)

    dest_dir = project_output_dir / "scratch_project"
    result = RepairResult(zip_path=str(zip_copy_path), project_name=project_name)

    try:
        pipeline_start = time.time()

        # ── 1. Unzip ──────────────────────────────────────────────────────
        console.rule("[bold]📦 Step 1: Unzipping project")
        project_dir = safe_unzip(zip_copy_path, dest_dir)
        files = list_project_files(project_dir)
        py_files = [f for f in files if f.endswith(".py")]
        test_files = [f for f in py_files if "test" in f.lower()]
        console.print(f"  [green]✔ Unzipped[/]  {len(files)} files  ({len(py_files)} .py, {len(test_files)} test)")
        for f in files:
            icon = "🧪" if "test" in f.lower() else "📄"
            console.print(f"    {icon} [dim]{f}[/dim]")

        # ── 2. Ask user for prompt ────────────────────────────────────────
        console.print()
        console.rule("[bold]💬 Step 2: What should I fix?")
        console.print(
            "\n[bold yellow]Describe what you want the agent to fix.[/]\n"
            "[dim]Examples:\n"
            "  • 'fix all failing tests'\n"
            "  • 'fix import errors and make tests pass'\n"
            "  • Press Enter for default[/dim]\n"
        )
        user_prompt = input("🎯 Your prompt > ").strip()
        if not user_prompt:
            user_prompt = "Fix all failing tests and compilation errors."
            console.print("  [dim](Using default prompt)[/dim]")
        result.user_prompt = user_prompt
        console.print(f"\n  [bold]Prompt:[/bold] [cyan]{user_prompt}[/cyan]")

        # ── 3. Baseline checks ────────────────────────────────────────────
        console.print()
        console.rule("[bold]🔍 Step 3: Baseline checks")
        baseline_pytest = run_pytest(project_dir)
        baseline_compile = run_compile_check(project_dir)
        score_before = calculate_score(baseline_pytest, baseline_compile)
        result.score_before = score_before

        console.print(Panel(
            f"pytest:  {'✅ PASSED' if baseline_pytest.passed else '❌ FAILED'}\n"
            f"compile: {'✅ PASSED' if baseline_compile.passed else '❌ FAILED'}\n"
            f"score:   {score_before.score:.0%}",
            title="Baseline Score",
            border_style="red" if score_before.score < 1.0 else "green",
        ))

        if baseline_pytest.passed and baseline_compile.passed:
            console.print("[bold green]✅ All checks already pass — nothing to fix![/bold green]")
            result.success = True
            result.score_after = score_before
            result.finished_at = datetime.utcnow()
        else:
            # ── 4-6. Iterative repair loop ────────────────────────────────
            console.print()
            console.rule(f"[bold]⚡ Step 4: Repair loop (max {MAX_REPAIR_ITERATIONS} iterations)")

            initial_hashes = file_hashes(project_dir)
            system_prompt = build_single_shot_skill(_load_base_prompt())

            current_pytest = baseline_pytest
            current_compile = baseline_compile
            current_score = score_before
            last_no_improvement = False

            for iteration_num in range(1, MAX_REPAIR_ITERATIONS + 1):
                console.print()
                console.rule(f"[bold]🔁 Iteration {iteration_num}/{MAX_REPAIR_ITERATIONS}")
                source_context = _read_project_files(project_dir)
                console.print(
                    f"  [green]✔ Read latest source files[/]  "
                    f"({len(source_context)} chars)"
                )

                score_before_iteration = current_score
                retry_note = ""
                if iteration_num > 1:
                    retry_note = (
                        "\n## Previous Attempt Feedback\n"
                        f"The previous attempt ended at score "
                        f"{score_before_iteration.score:.0%}. "
                        "Use the current pytest/compile output below as the source of truth. "
                        "If the score did not improve, choose a different concrete fix instead "
                        "of repeating the same change. Prefer replacing the exact failing code "
                        "path instead of adding duplicate conditions.\n"
                    )
                    if last_no_improvement:
                        retry_note += (
                            "The previous non-improving source edit was reverted, so this "
                            "iteration starts from the best known project state.\n"
                        )

                fixer_prompt = (
                    f"## Task\n{user_prompt}\n\n"
                    f"## Iteration\n{iteration_num} of {MAX_REPAIR_ITERATIONS}\n"
                    f"{retry_note}\n"
                    f"## Current Score\n"
                    f"- Score: {score_before_iteration.score:.0%}\n"
                    f"- Tests: {score_before_iteration.tests_passed}/"
                    f"{score_before_iteration.tests_total} passed\n"
                    f"- Compile OK: {score_before_iteration.compile_ok}\n\n"
                    f"## Current Pytest Output\n```\n{current_pytest.output}\n```\n\n"
                    f"## Current Compile Errors\n```\n{current_compile.output}\n```\n\n"
                    f"## Current Source Files\n{source_context}\n\n"
                    "Apply the smallest source-code fixes needed to improve the score. "
                    "Do not edit tests unless the test itself is syntactically broken. "
                    "Use ONLY relative paths. Run `pytest` at the end to confirm progress.\n\n"
                    "If you cannot invoke the Edit/Write tools and can only respond with text, "
                    "return ONLY this JSON shape using exact snippets from the source files:\n"
                    "{\"edits\":[{\"file_path\":\"relative/path.py\",\"old_string\":\"exact old text\","
                    "\"new_string\":\"replacement text\"}]}\n"
                    "Use source files only. Never include tests/ paths. Do not return fake tool-call JSON."
                )

                source_snapshot = _snapshot_source_files(project_dir)
                hashes_before_agent = file_hashes(project_dir)
                agent_response = await run_repair_agent(project_dir, fixer_prompt, system_prompt)
                hashes_after_agent = file_hashes(project_dir)

                if hashes_after_agent == hashes_before_agent:
                    fallback_changed = _apply_text_edit_fallback(project_dir, agent_response)
                    if fallback_changed:
                        note = (
                            "\n\n[Local text-edit fallback applied files: "
                            + ", ".join(fallback_changed)
                            + "]"
                        )
                        agent_response += note
                        console.print(
                            "[green]✔ Applied local text-edit fallback:[/] "
                            + ", ".join(fallback_changed)
                        )
                    else:
                        console.print("[yellow]No files changed by SDK tools or text-edit fallback.[/yellow]")

                console.print()
                console.rule(f"[bold]📊 Verification after iteration {iteration_num}")
                current_pytest = run_pytest(project_dir)
                current_compile = run_compile_check(project_dir)
                current_score = calculate_score(current_pytest, current_compile)

                if not (current_pytest.passed and current_compile.passed):
                    full_file_changed, fallback_pytest, fallback_compile, fallback_score = _try_validated_full_file_repair(
                        project_dir=project_dir,
                        user_prompt=user_prompt,
                        pytest_result=current_pytest,
                        compile_result=current_compile,
                        current_score=current_score,
                    )
                    if full_file_changed:
                        agent_response += (
                            "\n\n[Validated full-file fallback applied files: "
                            + ", ".join(full_file_changed)
                            + "]"
                        )
                        current_pytest = fallback_pytest
                        current_compile = fallback_compile
                        current_score = fallback_score
                        console.print(
                            "[green]✔ Applied validated full-file fallback:[/] "
                            + ", ".join(full_file_changed)
                        )

                result.iterations.append(RepairIteration(
                    iteration=iteration_num,
                    agent_response=agent_response,
                    score_before=score_before_iteration,
                    score_after=current_score,
                ))
                result.score_after = current_score
                result.success = current_pytest.passed and current_compile.passed
                last_no_improvement = False

                delta = current_score.score - score_before_iteration.score
                console.print(Panel(
                    f"pytest:  {'✅ PASSED' if current_pytest.passed else '❌ FAILED'}\n"
                    f"compile: {'✅ PASSED' if current_compile.passed else '❌ FAILED'}\n"
                    f"score:   {score_before_iteration.score:.0%} → "
                    f"{current_score.score:.0%} ({delta:+.0%})",
                    title=f"Iteration {iteration_num} Score",
                    border_style="green" if result.success else "yellow",
                ))

                if result.success:
                    console.print("[bold green]✅ All checks pass — stopping repair loop.[/bold green]")
                    break

                if current_score.score <= score_before_iteration.score:
                    restored = _restore_source_snapshot(project_dir, source_snapshot)
                    current_pytest = run_pytest(project_dir)
                    current_compile = run_compile_check(project_dir)
                    current_score = calculate_score(current_pytest, current_compile)
                    result.score_after = current_score
                    last_no_improvement = True
                    if restored:
                        console.print(
                            "[yellow]No score improvement — reverted iteration edits:[/] "
                            + ", ".join(restored)
                        )

                if iteration_num < MAX_REPAIR_ITERATIONS:
                    console.print("[yellow]Checks still failing — running another repair iteration.[/yellow]")

            hashes_after = file_hashes(project_dir)
            modified = detect_modified_files(initial_hashes, hashes_after)
            result.modified_files = modified
            result.test_files_modified = any(is_test_file(f) for f in modified)
            result.finished_at = datetime.utcnow()

            total_time = time.time() - pipeline_start

            console.print(Panel(
                f"Success:    {'✅ YES' if result.success else '❌ NO'}\n"
                f"Score:      {score_before.score:.0%} → {result.score_after.score:.0%}\n"
                f"Iterations: {len(result.iterations)}/{MAX_REPAIR_ITERATIONS}\n"
                f"Changed:    {len(modified)} file(s)\n"
                f"Time:       {total_time:.1f}s",
                title="📋 Final Result",
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

    # ── Save outputs ──────────────────────────────────────────────────────
    console.print()
    console.rule("[bold]💾 Saving outputs")
    json_path = project_output_dir / "result.json"
    json_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    console.print(f"  [green]✔[/green] JSON saved:   {json_path}")

    report_path = project_output_dir / "README_REPORT.md"
    write_report(result, report_path)
    console.print(f"  [green]✔[/green] Report saved: {report_path}")
    console.print()

    return result
