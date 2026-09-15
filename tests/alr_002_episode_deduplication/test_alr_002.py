"""Consolidated runner entry point; detailed procedure is in README.md."""

from tests._framework.entrypoints import run_consolidated


def test_alr_002(test_context):
    assert test_context.test_id == 'ALR-002'
    run_consolidated(test_context)
