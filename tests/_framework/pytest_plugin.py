"""Local pytest plugin supplying the runner-owned TestContext fixture."""

from __future__ import annotations

import pytest

from tests._framework.test_context import TestContext


@pytest.fixture(scope="session")
def test_context() -> TestContext:
    return TestContext.from_environment()
