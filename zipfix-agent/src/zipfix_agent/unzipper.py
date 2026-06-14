"""Safe zip extraction with path-traversal protection."""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

from rich.console import Console

console = Console()


def safe_unzip(zip_path: Path, dest_dir: Path) -> Path:
    """Extract *zip_path* into *dest_dir* and return the project root.

    Raises ``ValueError`` on path-traversal attempts or invalid zips.
    """
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zf:
        # Security: reject entries that escape the destination
        for member in zf.namelist():
            resolved = (dest_dir / member).resolve()
            if not str(resolved).startswith(str(dest_dir.resolve())):
                raise ValueError(f"Path traversal detected in zip member: {member}")
        zf.extractall(dest_dir)

    # If the zip contains a single top-level directory, use that as project root
    top_items = list(dest_dir.iterdir())
    if len(top_items) == 1 and top_items[0].is_dir():
        return top_items[0]
    return dest_dir
