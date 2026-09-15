"""Consolidated runner entry point; detailed procedure is in README.md."""

from tests._framework.entrypoints import run_consolidated


def test_db_004(test_context):
    assert test_context.test_id == 'DB-004'
    run_consolidated(test_context)
