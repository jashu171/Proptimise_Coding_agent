"""Centralised configuration loaded from environment variables.

All env vars are read once at import-time via ``python-dotenv`` so that every
module sees a consistent snapshot.  No secrets are hardcoded.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# ── Load .env from agent package root ────────────────────────────────────────
_AGENT_ROOT = Path(__file__).resolve().parents[2]
_WORKSPACE_ROOT = _AGENT_ROOT.parent
load_dotenv(_AGENT_ROOT / ".env")

# ── Model selection ──────────────────────────────────────────────────────────
MODEL: str = os.getenv("MODEL", "gpt-4o-mini")
REASONING_MODEL: str = os.getenv("REASONING_MODEL", "gpt-4o-mini")

# ── Agent behaviour limits ───────────────────────────────────────────────────
MAX_TURNS: int = int(os.getenv("CLAUDE_CODE_MAX_TURNS", "10"))
MAX_OUTPUT_TOKENS: int = int(os.getenv("CLAUDE_CODE_MAX_OUTPUT_TOKENS", "3000"))
BASH_MAX_OUTPUT: int = int(os.getenv("BASH_MAX_OUTPUT_LENGTH", "2000"))

# ── Paths ────────────────────────────────────────────────────────────────────
PROMPTS_DIR: Path = _AGENT_ROOT / "prompts"
DATASET_DIR: Path = _AGENT_ROOT / "dataset" / "cases"

INPUTS_DIR: Path = Path(os.getenv("ZIPFIX_INPUTS_DIR", _WORKSPACE_ROOT / "inputs"))
OUTPUTS_DIR: Path = Path(os.getenv("ZIPFIX_OUTPUTS_DIR", _WORKSPACE_ROOT / "outputs"))

# Legacy name retained so older imports keep working.
UPLOADS_DIR: Path = INPUTS_DIR

# ── Ensure output dirs exist ────────────────────────────────────────────────
for _d in (INPUTS_DIR, OUTPUTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)
