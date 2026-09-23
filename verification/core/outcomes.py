"""Canonical qualification outcomes and their presentation labels."""

from __future__ import annotations


PASS_OVERRIDE = "PASS_OVERRIDE"
TEST_OUTCOMES = ("PASS", PASS_OVERRIDE, "FAIL", "BLOCKED", "SKIPPED", "NOT_APPLICABLE")
PASSING_OUTCOMES = {"PASS", PASS_OVERRIDE, "NOT_APPLICABLE"}


def normalize_outcome(value: str) -> str:
    normalized = value.strip().upper().replace("-", "_").replace(" ", "_")
    if normalized in {"PASS_(OVERRIDE)", "PASS_OVERRIDE"}:
        return PASS_OVERRIDE
    return normalized


def display_outcome(value: str) -> str:
    return "PASS (OVERRIDE)" if value == PASS_OVERRIDE else value
