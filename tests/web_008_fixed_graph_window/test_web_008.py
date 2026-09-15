"""Consolidated runner entry point; detailed procedure is in README.md."""

from tests._framework.entrypoints import run_consolidated


def test_web_008(test_context):
    assert test_context.test_id == 'WEB-008'
    run_consolidated(test_context)
