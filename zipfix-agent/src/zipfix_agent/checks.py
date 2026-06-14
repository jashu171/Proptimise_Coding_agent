"""Quality checks – pytest runner and compile verification."""

from __future__ import annotations

import subprocess
from pathlib import Path

from zipfix_agent.config import BASH_MAX_OUTPUT
from zipfix_agent.schemas import CheckResult


def run_pytest(project_dir: Path) -> CheckResult:
    """Run ``pytest`` inside *project_dir* and return a CheckResult."""
    try:
        proc = subprocess.run(
            ["python", "-m", "pytest", "--tb=short", "-q"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=120,
        )
        output = (proc.stdout + "\n" + proc.stderr).strip()
        # Truncate to keep payloads manageable
        if len(output) > BASH_MAX_OUTPUT:
            output = output[:BASH_MAX_OUTPUT] + "\n... [truncated]"
        return CheckResult(
            name="pytest",
            passed=proc.returncode == 0,
            output=output,
            return_code=proc.returncode,
        )
    except subprocess.TimeoutExpired:
        return CheckResult(name="pytest", passed=False, output="pytest timed out after 120s", return_code=-1)
    except FileNotFoundError:
        return CheckResult(name="pytest", passed=False, output="pytest not found", return_code=-1)


def run_compile_check(project_dir: Path) -> CheckResult:
    """Attempt ``py_compile`` on every *.py* file in *project_dir*."""
    errors: list[str] = []
    py_files = list(project_dir.rglob("*.py"))
    for pf in py_files:
        try:
            subprocess.run(
                ["python", "-m", "py_compile", str(pf)],
                capture_output=True,
                text=True,
                timeout=30,
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            errors.append(f"{pf.relative_to(project_dir)}: {exc.stderr.strip()}")
        except subprocess.TimeoutExpired:
            errors.append(f"{pf.relative_to(project_dir)}: compile timed out")

    if errors:
        output = "\n".join(errors)
        if len(output) > BASH_MAX_OUTPUT:
            output = output[:BASH_MAX_OUTPUT] + "\n... [truncated]"
        return CheckResult(name="compile", passed=False, output=output, return_code=1)

    return CheckResult(name="compile", passed=True, output=f"All {len(py_files)} files compiled OK", return_code=0)
