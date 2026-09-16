import os
import unittest
from unittest import mock

import main as backend_main
from pc_client.protocol import CONFIG


class MainTests(unittest.TestCase):
    @mock.patch("main.uvicorn.run")
    def test_native_run_keeps_loopback_default(self, run: mock.Mock) -> None:
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("THERMOMETER_API_HOST", None)
            backend_main.main()

        self.assertEqual(run.call_args.kwargs["host"], CONFIG.service.api_host)

    @mock.patch("main.uvicorn.run")
    def test_container_can_bind_all_interfaces(self, run: mock.Mock) -> None:
        with mock.patch.dict(
            os.environ, {"THERMOMETER_API_HOST": "0.0.0.0"}
        ):
            backend_main.main()

        self.assertEqual(run.call_args.kwargs["host"], "0.0.0.0")

    @mock.patch("main.uvicorn.run")
    def test_native_port_can_follow_launcher_configuration(self, run: mock.Mock) -> None:
        with mock.patch.dict(os.environ, {"THERMOMETER_API_PORT": "8123"}):
            backend_main.main()

        self.assertEqual(run.call_args.kwargs["port"], 8123)


if __name__ == "__main__":
    unittest.main()
