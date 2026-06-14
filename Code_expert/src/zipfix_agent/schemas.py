"""Pydantic schemas shared across the ZipFix Agent pipeline."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class CheckResult(BaseModel):
    """Outcome of a single quality check (pytest / compile)."""

    name: str = Field(..., description="Check name, e.g. 'pytest' or 'compile'")
    passed: bool = False
    output: str = ""
    return_code: int = -1


class ScoreCard(BaseModel):
    """Numeric quality score for a project snapshot."""

    tests_total: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    tests_error: int = 0
    compile_ok: bool = False
    score: float = Field(default=0.0, description="0.0 – 1.0 normalised score")


class RepairIteration(BaseModel):
    """Record of a single repair iteration."""

    iteration: int
    agent_response: str = ""
    score_before: ScoreCard
    score_after: ScoreCard


class RepairResult(BaseModel):
    """Final output of the repair pipeline."""

    zip_path: str
    project_name: str
    user_prompt: str = ""
    codebase_summary: str = ""
    repair_plan: str = ""
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None
    iterations: list[RepairIteration] = []
    score_before: ScoreCard = Field(default_factory=ScoreCard)
    score_after: ScoreCard = Field(default_factory=ScoreCard)
    modified_files: list[str] = []
    test_files_modified: bool = False
    success: bool = False
    error: Optional[str] = None
