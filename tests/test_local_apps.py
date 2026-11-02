"""Launcher checks without starting processes or opening user dashboards."""
import os
import socket
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from internships_project import local_apps as apps


class LocalAppsTests(unittest.TestCase):
    def setUp(self):
        apps._children.clear()

    def tearDown(self):
        apps._children.clear()

    def test_local_boundary_and_hosted_refusal(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertTrue(apps.local_launch_allowed("localhost", "127.0.0.1"))
            self.assertFalse(apps.local_launch_allowed("example.com", "127.0.0.1"))
            self.assertFalse(apps.local_launch_allowed("localhost", "192.168.1.2"))
        with patch.dict(os.environ, {"RAILWAY_PROJECT_ID": "test"}):
            self.assertFalse(apps.local_launch_allowed("localhost", "127.0.0.1"))

    def test_allowlist(self):
        with self.assertRaises(ValueError):
            apps.launch_app("../app.py")

    def test_city_skips_occupied_port_and_keeps_replacement_reserved(self):
        with socket.socket() as occupied:
            occupied.bind(("127.0.0.1", 0))
            occupied.listen()
            original = occupied.getsockname()[1]
            with apps.reserve_local_socket("127.0.0.1", original) as listener:
                selected = listener.getsockname()[1]
                self.assertNotEqual(selected, original)
                with socket.socket() as competitor:
                    with self.assertRaises(OSError):
                        competitor.bind(("127.0.0.1", selected))

    def test_city_reservation_stays_local(self):
        with self.assertRaises(ValueError):
            apps.reserve_local_socket("0.0.0.0", 7862)
        with self.assertRaises(ValueError):
            apps.reserve_local_socket("127.0.0.1", 70000)

    def test_real_child_readiness_and_reuse(self):
        # A real local HTTP child exercises Popen/readiness without Gradio or data.
        with TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "dashboard.py").write_text(
                "import os\nfrom http.server import HTTPServer, BaseHTTPRequestHandler\n"
                "class Handler(BaseHTTPRequestHandler):\n"
                " def do_GET(self):\n  self.send_response(200)\n  self.end_headers()\n  self.wfile.write(b'local test dashboard')\n"
                "HTTPServer(('127.0.0.1', int(os.environ['MARKETDESK_APP_PORT'])), Handler).serve_forever()\n",
                encoding="utf-8")
            try:
                with patch.object(apps, "ROOT", root), patch.dict(apps.APPS, {"markets": "dashboard.py"}):
                    first = apps.launch_app("markets", timeout=8)
                    self.assertTrue(apps.launch_app("markets")["reused"])
                    self.assertTrue(first["url"].startswith("http://127.0.0.1:"))
            finally:
                for process, _ in apps._children.values():
                    process.terminate()
                    process.wait(timeout=5)

    @patch.object(apps, "_ready", return_value=True)
    @patch.object(apps.subprocess, "Popen")
    def test_reuse_and_separate_ports(self, spawn, ready):
        spawn.return_value = Mock(poll=Mock(return_value=None))
        one = apps.launch_app("markets")
        again = apps.launch_app("markets")
        other = apps.launch_app("internships")
        self.assertEqual(one["url"], again["url"])
        self.assertTrue(again["reused"])
        self.assertNotEqual(one["url"], other["url"])
        self.assertEqual(spawn.call_count, 2)
        args, kwargs = spawn.call_args
        self.assertEqual(args[0][1], str(apps.ROOT / "app_internships.py"))
        self.assertEqual(kwargs["env"]["MARKETDESK_NO_BROWSER"], "1")
        self.assertEqual(kwargs["env"]["GRADIO_SERVER_NAME"], "127.0.0.1")
        self.assertFalse(kwargs.get("shell", False))

    @patch.object(apps, "_ready", return_value=False)
    @patch.object(apps.subprocess, "Popen")
    def test_start_failure_is_explained(self, spawn, ready):
        spawn.return_value = Mock(poll=Mock(return_value=1))
        with self.assertRaisesRegex(RuntimeError, "environnement Python"):
            apps.launch_app("markets")

    @patch.object(apps.subprocess, "Popen")
    def test_timeout_keeps_instance_for_retry(self, spawn):
        spawn.return_value = Mock(poll=Mock(return_value=None))
        with self.assertRaisesRegex(RuntimeError, "même instance"):
            apps.launch_app("markets", timeout=0)
        with patch.object(apps, "_ready", return_value=True):
            self.assertTrue(apps.launch_app("markets")["reused"])
        self.assertEqual(spawn.call_count, 1)


if __name__ == "__main__":
    unittest.main()
