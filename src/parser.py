"""Public parser facade for Z21 locomotive archives."""

from pathlib import Path
from typing import Optional
import xml.etree.ElementTree as ET
import zipfile

from .archive import Z21Archive
from .data_models import FunctionInfo, Locomotive, UnknownBlock, Z21File
from .sqlite_repository import SQLiteZ21Repository


class Z21Parser:
    """Coordinate archive detection with format-specific repositories."""

    def __init__(self, file_path: Path):
        self.file_path = Path(file_path)
        self.archive = Z21Archive(self.file_path)

    def parse(self) -> Z21File:
        """Parse a SQLite/XML Z21 archive or preserve unknown binary data."""
        try:
            archive_format = self.archive.inspect()
            if archive_format.sqlite_path:
                database_bytes = self.archive.read_member(
                    archive_format.sqlite_path)
                return SQLiteZ21Repository(database_bytes).load()
            if archive_format.xml_path:
                xml_content = self.archive.read_member(
                    archive_format.xml_path).decode("utf-8", errors="ignore")
                return self._parse_xml(xml_content)
            return Z21File()
        except zipfile.BadZipFile:
            binary_data = self.file_path.read_bytes()
            return Z21File(unknown_blocks=[
                UnknownBlock(offset=0,
                             length=len(binary_data),
                             data=binary_data)
            ])

    def write(self, z21_file: Z21File,
              output_path: Optional[Path] = None) -> Path:
        """Persist a Z21 model using its format-specific repository."""
        output_path = Path(output_path) if output_path else self.file_path
        archive_format = self.archive.inspect()
        if not archive_format.sqlite_path:
            raise NotImplementedError("Writing XML format not yet implemented")

        database_bytes = self.archive.read_member(archive_format.sqlite_path)
        updated_database = SQLiteZ21Repository(database_bytes).save(z21_file)
        expected_locomotives = sum(
            1 for locomotive in z21_file.locomotives
            if locomotive.rail_vehicle_type == 0)
        return self.archive.replace_sqlite(
            archive_format.sqlite_path,
            updated_database,
            output_path,
            expected_locomotives,
        )

    def _parse_xml(self, xml_content: str) -> Z21File:
        z21_file = Z21File()
        try:
            root = ET.fromstring(xml_content)
            export_metadata = root.find("exportmeta")
            if export_metadata is not None:
                version_element = export_metadata.find("version")
                if version_element is not None and version_element.text:
                    z21_file.version = int(version_element.text)

            locomotives = root.find("locos")
            if locomotives is not None:
                for locomotive_element in locomotives.findall("loco"):
                    z21_file.locomotives.append(
                        self._parse_locomotive(locomotive_element))
        except (ET.ParseError, ValueError):
            encoded_xml = xml_content.encode("utf-8")
            z21_file.unknown_blocks.append(
                UnknownBlock(offset=0,
                             length=len(encoded_xml),
                             data=encoded_xml))
        return z21_file

    @staticmethod
    def _element_text(parent: ET.Element, name: str,
                      default: str = "") -> str:
        element = parent.find(name)
        return (element.text
                if element is not None and element.text is not None else
                default)

    def _parse_locomotive(self, element: ET.Element) -> Locomotive:
        locomotive = Locomotive(
            address=int(self._element_text(element, "address", "0")),
            name=self._element_text(element, "name"),
            speed=int(self._element_text(element, "max_speed", "0")),
            direction=(int(
                self._element_text(element, "traction_direction", "1")) == 1),
        )

        functions = element.find("functions")
        if functions is None:
            return locomotive

        for function_element in functions.findall("function_element"):
            function_text = self._element_text(function_element, "function")
            if not function_text:
                continue
            function_number = int(function_text)
            is_active = int(
                self._element_text(function_element, "active", "1")) == 1
            locomotive.functions[function_number] = is_active
            locomotive.function_details[function_number] = FunctionInfo(
                function_number=function_number,
                image_name=self._element_text(function_element, "image_name"),
                shortcut=self._element_text(function_element, "shortcut"),
                position=int(
                    self._element_text(function_element, "position", "0")),
                time=self._element_text(function_element, "time", "0"),
                button_type=int(
                    self._element_text(function_element, "button_type", "0")),
                is_active=is_active,
            )
        return locomotive
