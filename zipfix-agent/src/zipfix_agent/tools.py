"""Tool helpers for the ZipFix Agent.

These are convenience wrappers used by the repair loop to inspect
project files before / after the agent runs.  They do NOT replace the
Claude Agent SDK built-in tools (Bash, Read, Edit) – those are granted
to the agent via ``allowed_tools`` in ``ClaudeAgentOptions``.
"""

from __future__ import annotations

import hashlib
from pathlib import Path


def list_project_files(project_dir: Path) -> list[str]:
    """Return a sorted list of relative paths to all files in *project_dir*."""
    return sorted(
        str(p.relative_to(project_dir))
        for p in project_dir.rglob("*")
        if p.is_file()
    )


def file_hashes(project_dir: Path) -> dict[str, str]:
    """Return ``{relative_path: sha256}`` for every file in *project_dir*."""
    hashes: dict[str, str] = {}
    for p in project_dir.rglob("*"):
        if p.is_file():
            h = hashlib.sha256(p.read_bytes()).hexdigest()
            hashes[str(p.relative_to(project_dir))] = h
    return hashes


def detect_modified_files(
    before: dict[str, str],
    after: dict[str, str],
) -> list[str]:
    """Compare two hash snapshots and return list of changed / added files."""
    modified: list[str] = []
    for path, new_hash in after.items():
        old_hash = before.get(path)
        if old_hash is None or old_hash != new_hash:
            modified.append(path)
    return sorted(modified)


def is_test_file(path: str) -> bool:
    """Heuristic: does *path* look like a test file?"""
    parts = Path(path).parts
    name = Path(path).name
    return (
        name.startswith("test_")
        or name.endswith("_test.py")
        or "tests" in parts
        or "test" in parts
    )
