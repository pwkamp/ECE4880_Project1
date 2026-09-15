"""Consolidated runner entry point; detailed procedure is in README.md."""

from tests._framework.entrypoints import run_consolidated


def test_sys_004(test_context):
    assert test_context.test_id == 'SYS-004'
    run_consolidated(test_context)
