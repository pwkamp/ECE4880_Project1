"""Consolidated runner entry point; detailed procedure is in README.md."""

from tests._framework.entrypoints import run_consolidated


def test_fw_001(test_context):
    assert test_context.test_id == 'FW-001'
    run_consolidated(test_context)
