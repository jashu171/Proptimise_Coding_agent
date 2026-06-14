#!/usr/bin/env python3
"""Run the ZipFix Agent repair pipeline on a zipped Python project.

Usage:
    python scripts/run_agent.py ./dataset/cases/broken_calc.zip
    python scripts/run_agent.py          # interactive prompt for zip path
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# ── Load .env from project root ──────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ImportError:
    pass

from rich.console import Console  # noqa: E402

# Ensure src/ is importable when running from repo root
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from zipfix_agent.config import UPLOADS_DIR  # noqa: E402
from zipfix_agent.repair_loop import repair_zip_project  # noqa: E402

console = Console()


async def _main() -> None:
    # ── Resolve zip path ──────────────────────────────────────────────────
    if len(sys.argv) > 1:
        zip_path = Path(sys.argv[1])
    else:
        zip_files = sorted(list(UPLOADS_DIR.glob("*.zip")))
        if zip_files:
            console.print("\n[bold cyan]Found zip files in uploads/:[/]")
            for idx, path in enumerate(zip_files, 1):
                console.print(f"  [bold][{idx}][/bold] {path.name}")
            console.print()
            raw = input("Enter number, or input path to another zip file: ").strip()
            if raw.isdigit():
                idx = int(raw) - 1
                if 0 <= idx < len(zip_files):
                    zip_path = zip_files[idx]
                else:
                    console.print(f"[bold red]Error:[/] Invalid choice index: {raw}")
                    sys.exit(1)
            else:
                zip_path = Path(raw)
        else:
            raw = input("Enter zip file path: ").strip()
            zip_path = Path(raw)

    if not zip_path or not zip_path.exists() or not zip_path.suffix == ".zip":
        console.print(f"[bold red]Error:[/] {zip_path} does not exist or is not a .zip file.")
        sys.exit(1)

    zip_path = zip_path.resolve()
    console.rule(f"[bold]🚀 ZipFix Agent – {zip_path.name}")

    # ── Run pipeline ──────────────────────────────────────────────────────
    result = await repair_zip_project(zip_path)

    # ── Print final summary ───────────────────────────────────────────────
    console.rule("[bold]📋 Final Result")
    console.print(f"  Success: {'✅' if result.success else '❌'}")
    console.print(f"  Score:   {result.score_before.score:.0%} → {result.score_after.score:.0%}")
    console.print(f"  Iterations: {len(result.iterations)}")
    if result.error:
        console.print(f"  [red]Error: {result.error}[/red]")


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()
