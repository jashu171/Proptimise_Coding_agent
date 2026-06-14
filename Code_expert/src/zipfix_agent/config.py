"""Centralised configuration loaded from environment variables.

All env vars are read once at import-time via ``python-dotenv`` so that every
module sees a consistent snapshot.  No secrets are hardcoded.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# ── Load .env from project root ──────────────────────────────────────────────
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_PROJECT_ROOT / ".env")

# ── Model selection ──────────────────────────────────────────────────────────
MODEL: str = os.getenv("MODEL", "gpt-4o-mini")
REASONING_MODEL: str = os.getenv("REASONING_MODEL", "gpt-4o-mini")

# ── Agent behaviour limits ───────────────────────────────────────────────────
MAX_TURNS: int = int(os.getenv("CLAUDE_CODE_MAX_TURNS", "6"))
MAX_OUTPUT_TOKENS: int = int(os.getenv("CLAUDE_CODE_MAX_OUTPUT_TOKENS", "6000"))
BASH_MAX_OUTPUT: int = int(os.getenv("BASH_MAX_OUTPUT_LENGTH", "6000"))

# ── Paths ────────────────────────────────────────────────────────────────────
PROMPTS_DIR: Path = _PROJECT_ROOT / "prompts"
DATASET_DIR: Path = _PROJECT_ROOT / "dataset" / "cases"
UPLOADS_DIR: Path = _PROJECT_ROOT / "uploads"
OUTPUTS_DIR: Path = _PROJECT_ROOT / "outputs"

# ── Ensure output dirs exist ────────────────────────────────────────────────
for _d in (UPLOADS_DIR, OUTPUTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)
