import os
import sys
from types import ModuleType
import unittest
from unittest.mock import patch

from pc_client.database_adapter import (
    DATABASE_ADAPTER_FACTORY_ENV,
    NoOpDatabaseAdapter,
    load_database_adapter,
)
from pc_client.tests.test_ble_service import FakeDatabase


class DatabaseAdapterTests(unittest.TestCase):
    def test_no_environment_setting_selects_noop_adapter(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            adapter = load_database_adapter()

        self.assertIsInstance(adapter, NoOpDatabaseAdapter)
        self.assertFalse(adapter.persistence_configured)

    def test_environment_factory_loads_replaceable_adapter(self) -> None:
        module = ModuleType("test_project_database")
        expected = FakeDatabase()
        module.create_adapter = lambda: expected

        with (
            patch.dict(sys.modules, {module.__name__: module}),
            patch.dict(
                os.environ,
                {DATABASE_ADAPTER_FACTORY_ENV: "test_project_database:create_adapter"},
                clear=True,
            ),
        ):
            adapter = load_database_adapter()

        self.assertIs(adapter, expected)

    def test_invalid_factory_setting_has_an_actionable_error(self) -> None:
        with patch.dict(
            os.environ,
            {DATABASE_ADAPTER_FACTORY_ENV: "missing-separator"},
            clear=True,
        ):
            with self.assertRaisesRegex(RuntimeError, "module:factory"):
                load_database_adapter()


if __name__ == "__main__":
    unittest.main()
