"""ZIP archive access and safe replacement for Z21 files."""

from dataclasses import dataclass
import os
from pathlib import Path
import sqlite3
import tempfile
from typing import Mapping, Optional
import zipfile


@dataclass(frozen=True)
class ArchiveFormat:
    """Recognized data members inside a Z21 ZIP archive."""

    sqlite_path: Optional[str] = None
    xml_path: Optional[str] = None


class Z21Archive:
    """Owns ZIP discovery, member access, validation, and atomic writes."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def inspect(self) -> ArchiveFormat:
        with zipfile.ZipFile(self.path, "r") as archive:
            names = archive.namelist()
        return ArchiveFormat(
            sqlite_path=next(
                (name for name in names if name.endswith(".sqlite")), None),
            xml_path=next(
                (name for name in names if name.endswith(".xml")), None),
        )

    def read_member(self, member_path: str) -> bytes:
        with zipfile.ZipFile(self.path, "r") as archive:
            return archive.read(member_path)

    def replace_sqlite(self, sqlite_path: str, sqlite_data: bytes,
                       output_path: Path, expected_locomotives: int,
                       extra_members: Optional[Mapping[str, bytes]] = None) -> Path:
        """Build, validate, and atomically install an updated archive."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
                delete=False,
                suffix=output_path.suffix or ".z21",
                dir=output_path.parent) as candidate_file:
            candidate_path = Path(candidate_file.name)

        try:
            self._build_candidate(sqlite_path, sqlite_data, candidate_path,
                                  extra_members or {})
            self._validate_candidate(candidate_path, expected_locomotives)
            os.replace(candidate_path, output_path)
            return output_path
        finally:
            candidate_path.unlink(missing_ok=True)

    def _build_candidate(self, sqlite_path: str, sqlite_data: bytes,
                         candidate_path: Path,
                         extra_members: Mapping[str, bytes]) -> None:
        with zipfile.ZipFile(self.path, "r") as source_archive:
            with zipfile.ZipFile(candidate_path, "w",
                                 zipfile.ZIP_DEFLATED) as output_archive:
                for item in source_archive.infolist():
                    data = (sqlite_data if item.filename == sqlite_path else
                            extra_members.get(
                                item.filename,
                                source_archive.read(item.filename)))
                    copied_info = zipfile.ZipInfo(filename=item.filename,
                                                   date_time=item.date_time)
                    copied_info.compress_type = (
                        zipfile.ZIP_DEFLATED
                        if item.filename == sqlite_path else item.compress_type)
                    copied_info.external_attr = item.external_attr
                    copied_info.comment = item.comment
                    copied_info.extra = item.extra
                    output_archive.writestr(copied_info, data)
                existing = set(source_archive.namelist())
                for member_name, data in extra_members.items():
                    if member_name not in existing:
                        output_archive.writestr(member_name, data)

    def _validate_candidate(self, archive_path: Path,
                            expected_locomotives: int) -> None:
        with zipfile.ZipFile(archive_path, "r") as archive:
            corrupt_member = archive.testzip()
            if corrupt_member:
                raise ValueError(
                    f"Written archive contains corrupt member: {corrupt_member}")
            sqlite_files = [
                name for name in archive.namelist()
                if name.endswith(".sqlite")
            ]
            if len(sqlite_files) != 1:
                raise ValueError(
                    "Written archive must contain exactly one SQLite database")
            database_bytes = archive.read(sqlite_files[0])

        with tempfile.NamedTemporaryFile(delete=False,
                                         suffix=".sqlite") as database_file:
            database_file.write(database_bytes)
            database_path = Path(database_file.name)

        try:
            database = sqlite3.connect(database_path)
            try:
                integrity = database.execute(
                    "PRAGMA integrity_check").fetchone()
                if not integrity or integrity[0] != "ok":
                    raise ValueError(
                        "Written SQLite database failed integrity check: "
                        f"{integrity}")
                tables = {
                    row[0] for row in database.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'")
                }
                if "vehicles" not in tables:
                    raise ValueError(
                        "Written SQLite database has no vehicles table")
                actual_locomotives = database.execute(
                    "SELECT COUNT(*) FROM vehicles WHERE type = 0"
                ).fetchone()[0]
                if actual_locomotives != expected_locomotives:
                    raise ValueError(
                        "Written locomotive count does not match in-memory "
                        f"data: expected {expected_locomotives}, "
                        f"got {actual_locomotives}")
            finally:
                database.close()
        finally:
            database_path.unlink(missing_ok=True)
