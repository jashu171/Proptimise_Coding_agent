"""Scoring logic – converts CheckResult data into a normalised ScoreCard."""

from __future__ import annotations

import re

from zipfix_agent.schemas import CheckResult, ScoreCard


def _parse_pytest_summary(output: str) -> tuple[int, int, int, int]:
    """Extract (total, passed, failed, error) from pytest short output.

    Falls back to (0, 0, 0, 0) if the output cannot be parsed.
    """
    passed = failed = errors = 0

    m_passed = re.search(r"(\d+)\s+passed", output)
    m_failed = re.search(r"(\d+)\s+failed", output)
    m_error = re.search(r"(\d+)\s+error", output)

    if m_passed:
        passed = int(m_passed.group(1))
    if m_failed:
        failed = int(m_failed.group(1))
    if m_error:
        errors = int(m_error.group(1))

    total = passed + failed + errors
    return total, passed, failed, errors


def calculate_score(pytest_result: CheckResult, compile_result: CheckResult) -> ScoreCard:
    """Build a ScoreCard from raw check results."""
    total, passed, failed, error = _parse_pytest_summary(pytest_result.output)
    compile_ok = compile_result.passed

    # Normalise: 70 % tests weight, 30 % compile weight
    test_ratio = (passed / total) if total > 0 else 0.0
    score = round(test_ratio * 0.7 + (1.0 if compile_ok else 0.0) * 0.3, 4)

    return ScoreCard(
        tests_total=total,
        tests_passed=passed,
        tests_failed=failed,
        tests_error=error,
        compile_ok=compile_ok,
        score=score,
    )
