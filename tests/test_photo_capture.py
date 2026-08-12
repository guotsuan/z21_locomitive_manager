import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.photo_capture import (
    CaptureMode,
    ContinuityCameraError,
    ContinuityCameraService,
)


class ContinuityCameraServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_directory.cleanup)
        self.temp_path = Path(self.temp_directory.name)
        self.source_path = self.temp_path / "main.swift"
        self.source_path.write_text("// test helper", encoding="utf-8")
        self.info_plist_path = self.temp_path / "Info.plist"
        self.info_plist_path.write_text("<plist/>", encoding="utf-8")
        self.service = ContinuityCameraService(
            source_path=self.source_path,
            cache_directory=self.temp_path / "cache",
            info_plist_path=self.info_plist_path,
        )

    @staticmethod
    def completed_with_result(payload):
        def run(command, **kwargs):
            result_index = command.index("--result-file") + 1
            Path(command[result_index]).write_text(payload, encoding="utf-8")
            return subprocess.CompletedProcess(
                args=command, returncode=0, stdout="", stderr="")
        return run

    def test_capture_returns_helper_file(self):
        captured_path = self.temp_path / "captured.pdf"
        captured_path.write_bytes(b"pdf")
        payload = ('{"status":"ok","mode":"scan","path":"'
                   + str(captured_path) + '"}\n')
        with mock.patch.object(self.service, "_ensure_helper",
                               return_value=Path("/fake/helper.app")), \
                mock.patch("src.photo_capture.shutil.which",
                           return_value="/usr/bin/open"), \
                mock.patch("src.photo_capture.subprocess.run",
                           side_effect=self.completed_with_result(payload)):
            result = self.service.capture(CaptureMode.SCAN)

        self.assertIsNotNone(result)
        self.assertEqual(result.path, captured_path)
        self.assertEqual(result.mode, CaptureMode.SCAN)

    def test_cancelled_capture_returns_none(self):
        payload = '{"status":"cancelled","mode":"photo"}\n'
        with mock.patch.object(self.service, "_ensure_helper",
                               return_value=Path("/fake/helper.app")), \
                mock.patch("src.photo_capture.shutil.which",
                           return_value="/usr/bin/open"), \
                mock.patch("src.photo_capture.subprocess.run",
                           side_effect=self.completed_with_result(payload)):
            result = self.service.capture(CaptureMode.PHOTO)

        self.assertIsNone(result)

    def test_missing_result_file_is_rejected(self):
        payload = ('{"status":"ok","mode":"photo",'
                   '"path":"/missing"}\n')
        with mock.patch.object(self.service, "_ensure_helper",
                               return_value=Path("/fake/helper.app")), \
                mock.patch("src.photo_capture.shutil.which",
                           return_value="/usr/bin/open"), \
                mock.patch("src.photo_capture.subprocess.run",
                           side_effect=self.completed_with_result(payload)):
            with self.assertRaisesRegex(ContinuityCameraError, "missing file"):
                self.service.capture(CaptureMode.PHOTO)

    def test_capture_launches_a_bundled_app_with_result_file(self):
        payload = '{"status":"cancelled","mode":"scan"}\n'
        with mock.patch.object(self.service, "_ensure_helper",
                               return_value=Path("/fake/helper.app")), \
                mock.patch("src.photo_capture.shutil.which",
                           return_value="/usr/bin/open"), \
                mock.patch("src.photo_capture.subprocess.run",
                           side_effect=self.completed_with_result(payload)) as run:
            self.service.capture(CaptureMode.SCAN)

        command = run.call_args.args[0]
        self.assertEqual(command[:5], [
            "/usr/bin/open", "-W", "-n", "/fake/helper.app", "--args"])
        self.assertIn("--result-file", command)


if __name__ == "__main__":
    unittest.main()
