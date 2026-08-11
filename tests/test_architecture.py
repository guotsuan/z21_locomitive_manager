import unittest
from pathlib import Path

from src.archive import Z21Archive
from src.parser import Z21Parser
from src.sqlite_repository import SQLiteZ21Repository


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = PROJECT_ROOT / "test.z21loco"


class ArchitectureBoundaryTests(unittest.TestCase):
    def test_archive_discovers_format_without_parsing_domain_data(self):
        archive_format = Z21Archive(FIXTURE_PATH).inspect()

        self.assertIsNotNone(archive_format.sqlite_path)
        self.assertIsNone(archive_format.xml_path)

    def test_sqlite_repository_round_trip_is_archive_independent(self):
        archive = Z21Archive(FIXTURE_PATH)
        sqlite_path = archive.inspect().sqlite_path
        self.assertIsNotNone(sqlite_path)
        database_bytes = archive.read_member(sqlite_path)
        repository = SQLiteZ21Repository(database_bytes)
        data = repository.load()
        data.locomotives[0].buffer_length = "repository boundary"

        saved_database = repository.save(data)
        reloaded = SQLiteZ21Repository(saved_database).load()

        self.assertEqual(reloaded.locomotives[0].buffer_length,
                         "repository boundary")

    def test_parser_remains_public_facade(self):
        parsed = Z21Parser(FIXTURE_PATH).parse()

        self.assertEqual(len(parsed.locomotives), 1)
        self.assertEqual(parsed.locomotives[0].name, "DE 18 VOSSLOH")


if __name__ == "__main__":
    unittest.main()
