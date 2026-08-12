import hashlib
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import zipfile

from src.data_models import Locomotive
from src.parser import Z21Parser


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = PROJECT_ROOT / "test.z21loco"


class PersistenceRegressionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.work_dir = Path(self.temp_dir.name)
        self.archive_path = self.work_dir / "working.z21loco"
        shutil.copy2(FIXTURE_PATH, self.archive_path)

    def test_editable_fields_survive_round_trip(self):
        parser = Z21Parser(self.archive_path)
        data = parser.parse()
        locomotive = data.locomotives[0]

        locomotive.buffer_length = "19.2 m"
        locomotive.model_buffer_length = "220 mm"
        locomotive.crane = True
        locomotive.categories = ["Diesel", "Regression Category"]
        locomotive.regulation_step = 2

        parser.write(data, self.archive_path)

        saved = Z21Parser(self.archive_path).parse().locomotives[0]
        self.assertEqual(saved.buffer_length, "19.2 m")
        self.assertEqual(saved.model_buffer_length, "220 mm")
        self.assertTrue(saved.crane)
        self.assertEqual(saved.categories,
                         ["Diesel", "Regression Category"])
        self.assertEqual(saved.regulation_step, 2)

        # Clearing relation-backed and boolean fields must persist as well.
        data = Z21Parser(self.archive_path).parse()
        data.locomotives[0].crane = False
        data.locomotives[0].categories = []
        data.locomotives[0].regulation_step = 0
        Z21Parser(self.archive_path).write(data, self.archive_path)
        cleared = Z21Parser(self.archive_path).parse().locomotives[0]
        self.assertFalse(cleared.crane)
        self.assertEqual(cleared.categories, [])
        self.assertEqual(cleared.regulation_step, 0)

    def test_no_op_round_trip_preserves_archive_members(self):
        # Unknown/unreferenced assets are still user data and must not be
        # discarded merely because the current model does not expose them.
        with zipfile.ZipFile(self.archive_path, "a") as archive:
            archive.writestr("unreferenced-user-asset.png", b"not-an-image")
        with zipfile.ZipFile(self.archive_path) as archive:
            before_members = archive.namelist()
        parser = Z21Parser(self.archive_path)

        parser.write(parser.parse(), self.archive_path)

        with zipfile.ZipFile(self.archive_path) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(archive.namelist(), before_members)

    def test_new_locomotive_uses_same_persistent_fields(self):
        parser = Z21Parser(self.archive_path)
        data = parser.parse()
        new_locomotive = Locomotive(
            address=999,
            name="Regression Locomotive",
            buffer_length="20 m",
            model_buffer_length="230 mm",
            categories=["Regression Category"],
            crane=True,
            regulation_step=1,
        )
        data.locomotives.append(new_locomotive)

        parser.write(data, self.archive_path)

        saved = next(
            locomotive
            for locomotive in Z21Parser(self.archive_path).parse().locomotives
            if locomotive.address == 999)
        self.assertEqual(saved.buffer_length, "20 m")
        self.assertEqual(saved.model_buffer_length, "230 mm")
        self.assertEqual(saved.categories, ["Regression Category"])
        self.assertTrue(saved.crane)
        self.assertEqual(saved.regulation_step, 1)

    def test_failed_validation_keeps_original_archive(self):
        parser = Z21Parser(self.archive_path)
        data = parser.parse()
        original_digest = hashlib.sha256(
            self.archive_path.read_bytes()).digest()

        with mock.patch.object(
                parser.archive,
                "_validate_candidate",
                side_effect=ValueError("simulated validation failure")):
            with self.assertRaisesRegex(ValueError,
                                        "simulated validation failure"):
                parser.write(data, self.archive_path)

        current_digest = hashlib.sha256(
            self.archive_path.read_bytes()).digest()
        self.assertEqual(current_digest, original_digest)
        self.assertEqual(list(self.work_dir.iterdir()), [self.archive_path])

    def test_written_database_passes_integrity_check(self):
        parser = Z21Parser(self.archive_path)
        parser.write(parser.parse(), self.archive_path)

        with zipfile.ZipFile(self.archive_path) as archive:
            sqlite_name = next(
                name for name in archive.namelist()
                if name.endswith(".sqlite"))
            sqlite_bytes = archive.read(sqlite_name)

        database_path = self.work_dir / "validated.sqlite"
        database_path.write_bytes(sqlite_bytes)
        database = sqlite3.connect(database_path)
        try:
            self.assertEqual(
                database.execute("PRAGMA integrity_check").fetchone()[0],
                "ok")
            self.assertEqual(
                database.execute("PRAGMA user_version").fetchone()[0], 16)
        finally:
            database.close()


if __name__ == "__main__":
    unittest.main()
