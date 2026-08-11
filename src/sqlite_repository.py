"""SQLite persistence for the modern Z21 file format."""

from pathlib import Path
import sqlite3
import tempfile
from typing import Any, Dict, Iterable, Optional, Set

from .data_models import FunctionInfo, Layout, Locomotive, Z21File
from .schema import (
    IN_STOCK_SINCE_COLUMNS,
    VEHICLE_READ_COLUMNS,
    first_available,
    locomotive_to_vehicle_values,
    values_for_columns,
)


class SQLiteZ21Repository:
    """Maps between a Z21 SQLite database and domain models."""

    def __init__(self, database_bytes: bytes):
        self.database_bytes = database_bytes

    @staticmethod
    def _temporary_database(database_bytes: bytes) -> Path:
        with tempfile.NamedTemporaryFile(delete=False,
                                         suffix=".sqlite") as database_file:
            database_file.write(database_bytes)
            return Path(database_file.name)

    @staticmethod
    def _tables(cursor: sqlite3.Cursor) -> Set[str]:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        return {row[0] for row in cursor.fetchall()}

    @staticmethod
    def _columns(cursor: sqlite3.Cursor, table: str) -> Set[str]:
        cursor.execute(f'PRAGMA table_info("{table}")')
        return {row[1] for row in cursor.fetchall()}

    @staticmethod
    def _row_value(row: sqlite3.Row, column: str,
                   default: Any = None) -> Any:
        return row[column] if column in row.keys() else default

    def load(self) -> Z21File:
        z21_file = Z21File()
        database_path = self._temporary_database(self.database_bytes)
        database = None
        try:
            database = sqlite3.connect(database_path)
            database.row_factory = sqlite3.Row
            cursor = database.cursor()
            tables = self._tables(cursor)
            if "vehicles" not in tables:
                return z21_file

            if "update_history" in tables:
                row = cursor.execute(
                    "SELECT MAX(to_database_version) FROM update_history"
                ).fetchone()
                if row and row[0] is not None:
                    z21_file.version = row[0]

            vehicle_columns = self._columns(cursor, "vehicles")
            selected_columns = [
                column for column in VEHICLE_READ_COLUMNS
                if column in vehicle_columns
            ]
            stock_column = first_available(IN_STOCK_SINCE_COLUMNS,
                                           vehicle_columns)
            if stock_column:
                selected_columns.append(stock_column)
            order_column = "position" if "position" in vehicle_columns else "id"
            cursor.execute(
                f'SELECT {", ".join(selected_columns)} FROM vehicles '
                f'WHERE type = 0 ORDER BY "{order_column}"')

            for vehicle in cursor.fetchall():
                locomotive = self._vehicle_from_row(vehicle, stock_column)
                vehicle_id = vehicle["id"]
                locomotive.vehicle_id = vehicle_id
                self._load_categories(cursor, tables, vehicle_id, locomotive)
                self._load_traction(cursor, tables, vehicle_id, locomotive)
                self._load_functions(cursor, tables, vehicle_id, locomotive)
                z21_file.locomotives.append(locomotive)

            if "layout_data" in tables:
                layout_columns = self._columns(cursor, "layout_data")
                if "name" in layout_columns:
                    for row in cursor.execute("SELECT name FROM layout_data"):
                        z21_file.layouts.append(Layout(name=row["name"] or ""))
            return z21_file
        finally:
            if database is not None:
                database.close()
            database_path.unlink(missing_ok=True)

    def _vehicle_from_row(self, row: sqlite3.Row,
                          stock_column: Optional[str]) -> Locomotive:
        value = self._row_value
        locomotive = Locomotive(
            address=value(row, "address", 0) or 0,
            name=value(row, "name", "") or "",
            speed=value(row, "max_speed", 0) or 0,
            direction=(value(row, "traction_direction", 0) or 0) == 1,
            image_name=value(row, "image_name", "") or "",
            full_name=value(row, "full_name", "") or "",
            railway=value(row, "railway", "") or "",
            description=value(row, "description", "") or "",
            article_number=value(row, "article_number", "") or "",
            decoder_type=value(row, "decoder_type", "") or "",
            build_year=value(row, "build_year", "") or "",
            buffer_length=value(row, "buffer_lenght", "") or "",
            model_buffer_length=value(row, "model_buffer_lenght", "") or "",
            service_weight=value(row, "service_weight", "") or "",
            model_weight=value(row, "model_weight", "") or "",
            rmin=value(row, "rmin", "") or "",
            ip=value(row, "ip", "") or "",
            drivers_cab=value(row, "drivers_cab", "") or "",
            active=bool(value(row, "active", 1)
                        if value(row, "active", 1) is not None else 1),
            speed_display=value(row, "speed_display", 0) or 0,
            rail_vehicle_type=value(row, "type", 0) or 0,
            crane=bool(value(row, "crane", 0) or 0),
        )
        if stock_column:
            locomotive.in_stock_since = value(row, stock_column, "") or ""
        return locomotive

    def _load_categories(self, cursor: sqlite3.Cursor, tables: Set[str],
                         vehicle_id: int, locomotive: Locomotive) -> None:
        if not {"categories", "vehicles_to_categories"}.issubset(tables):
            return
        link_columns = self._columns(cursor, "vehicles_to_categories")
        order = "vtc.id" if "id" in link_columns else "c.name"
        cursor.execute(
            f"""
            SELECT c.name FROM categories c
            INNER JOIN vehicles_to_categories vtc ON c.id = vtc.category_id
            WHERE vtc.vehicle_id = ? ORDER BY {order}
            """, (vehicle_id, ))
        locomotive.categories = [
            row["name"] for row in cursor.fetchall() if row["name"]
        ]

    @staticmethod
    def _load_traction(cursor: sqlite3.Cursor, tables: Set[str],
                       vehicle_id: int, locomotive: Locomotive) -> None:
        if "traction_list" not in tables:
            return
        row = cursor.execute(
            """
            SELECT regulation_step FROM traction_list WHERE loco_id = ?
            ORDER BY regulation_step LIMIT 1
            """, (vehicle_id, )).fetchone()
        if row:
            locomotive.regulation_step = row["regulation_step"] or 0

    def _load_functions(self, cursor: sqlite3.Cursor, tables: Set[str],
                        vehicle_id: int, locomotive: Locomotive) -> None:
        if "functions" not in tables:
            return
        function_columns = self._columns(cursor, "functions")
        wanted_columns = [
            "function", "position", "shortcut", "time", "image_name",
            "button_type", "is_configured"
        ]
        selected = [c for c in wanted_columns if c in function_columns]
        order = "position" if "position" in function_columns else "function"
        cursor.execute(
            f'SELECT {", ".join(selected)} FROM functions '
            f'WHERE vehicle_id = ? ORDER BY "{order}"', (vehicle_id, ))
        for row in cursor.fetchall():
            function_number = self._row_value(row, "function", 0) or 0
            is_active = bool(self._row_value(row, "is_configured", 1))
            locomotive.functions[function_number] = is_active
            locomotive.function_details[function_number] = FunctionInfo(
                function_number=function_number,
                image_name=self._row_value(row, "image_name", "") or "",
                shortcut=self._row_value(row, "shortcut", "") or "",
                position=self._row_value(row, "position", 0) or 0,
                time=(str(self._row_value(row, "time"))
                      if self._row_value(row, "time") is not None else "0"),
                button_type=self._row_value(row, "button_type", 0) or 0,
                is_active=is_active,
            )

    def save(self, z21_file: Z21File) -> bytes:
        database_path = self._temporary_database(self.database_bytes)
        database = None
        try:
            database = sqlite3.connect(database_path)
            database.row_factory = sqlite3.Row
            cursor = database.cursor()
            tables = self._tables(cursor)
            if "vehicles" not in tables:
                raise ValueError("SQLite database has no vehicles table")
            vehicle_columns = self._columns(cursor, "vehicles")

            kept_vehicle_ids = set()
            for locomotive in z21_file.locomotives:
                vehicle_id = self._find_vehicle_id(cursor, locomotive)
                if vehicle_id is None:
                    vehicle_id = self._insert_vehicle(
                        cursor, vehicle_columns, locomotive)
                else:
                    self._update_vehicle(cursor, vehicle_columns, vehicle_id,
                                         locomotive)
                locomotive.vehicle_id = vehicle_id
                locomotive.is_new_import = False
                kept_vehicle_ids.add(vehicle_id)
                self._sync_functions(cursor, tables, vehicle_id, locomotive)
                self._sync_categories(cursor, tables, vehicle_id,
                                      locomotive.categories)
                self._sync_traction(cursor, tables, vehicle_id,
                                    locomotive.regulation_step)

            self._delete_removed_locomotives(cursor, tables,
                                             kept_vehicle_ids)
            cursor.execute("PRAGMA user_version = 16")
            database.commit()
            database.close()
            database = None
            return database_path.read_bytes()
        finally:
            if database is not None:
                database.close()
            database_path.unlink(missing_ok=True)

    @staticmethod
    def _find_vehicle_id(cursor: sqlite3.Cursor,
                         locomotive: Locomotive) -> Optional[int]:
        stored_id = locomotive.vehicle_id
        if stored_id:
            row = cursor.execute("SELECT id FROM vehicles WHERE id = ?",
                                 (stored_id, )).fetchone()
            if row:
                return row["id"]
        if locomotive.is_new_import:
            return None
        for column, value in (("address", locomotive.address),
                              ("name", locomotive.name)):
            row = cursor.execute(
                f'SELECT id FROM vehicles WHERE type = 0 AND "{column}" = ?',
                (value, )).fetchone()
            if row:
                return row["id"]
        return None

    def _vehicle_values(self, vehicle_columns: Set[str],
                        locomotive: Locomotive,
                        position: Optional[int] = None) -> Dict[str, Any]:
        values = locomotive_to_vehicle_values(locomotive, position)
        stock_column = first_available(IN_STOCK_SINCE_COLUMNS,
                                       vehicle_columns)
        if stock_column:
            values[stock_column] = locomotive.in_stock_since or None
        return values_for_columns(values, vehicle_columns)

    def _update_vehicle(self, cursor: sqlite3.Cursor,
                        vehicle_columns: Set[str], vehicle_id: int,
                        locomotive: Locomotive) -> None:
        values = self._vehicle_values(vehicle_columns, locomotive)
        assignments = ", ".join(f'"{column}" = ?' for column in values)
        cursor.execute(f"UPDATE vehicles SET {assignments} WHERE id = ?",
                       (*values.values(), vehicle_id))

    def _insert_vehicle(self, cursor: sqlite3.Cursor,
                        vehicle_columns: Set[str],
                        locomotive: Locomotive) -> int:
        row = cursor.execute(
            "SELECT MAX(position) FROM vehicles WHERE type = 0").fetchone()
        next_position = (row[0] or 0) + 1
        values = self._vehicle_values(vehicle_columns, locomotive,
                                      next_position)
        columns = ", ".join(f'"{column}"' for column in values)
        placeholders = ", ".join("?" for _ in values)
        cursor.execute(
            f"INSERT INTO vehicles ({columns}) VALUES ({placeholders})",
            tuple(values.values()))
        return cursor.lastrowid

    @staticmethod
    def _function_time(raw_time: Any) -> Optional[float]:
        if raw_time in (None, "", "0"):
            return None
        try:
            return float(raw_time)
        except (TypeError, ValueError):
            return None

    def _sync_functions(self, cursor: sqlite3.Cursor, tables: Set[str],
                        vehicle_id: int, locomotive: Locomotive) -> None:
        if "functions" not in tables:
            return
        existing = {
            row[0] for row in cursor.execute(
                "SELECT function FROM functions WHERE vehicle_id = ?",
                (vehicle_id, ))
        }
        current = set(locomotive.function_details)
        for function_number in existing - current:
            cursor.execute(
                "DELETE FROM functions WHERE vehicle_id = ? AND function = ?",
                (vehicle_id, function_number))
        for function_number, info in locomotive.function_details.items():
            values = (
                info.position, info.shortcut or "",
                self._function_time(info.time), info.image_name or "",
                info.button_type, vehicle_id, function_number,
            )
            if function_number in existing:
                cursor.execute(
                    """
                    UPDATE functions SET position = ?, shortcut = ?, time = ?,
                        image_name = ?, button_type = ?, is_configured = 1,
                        show_function_number = 1
                    WHERE vehicle_id = ? AND function = ?
                    """, values)
            else:
                cursor.execute(
                    """
                    INSERT INTO functions
                    (position, shortcut, time, image_name, button_type,
                     vehicle_id, function, is_configured, show_function_number)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1)
                    """, values)

    def _sync_categories(self, cursor: sqlite3.Cursor, tables: Set[str],
                         vehicle_id: int,
                         category_names: Iterable[str]) -> None:
        if not {"categories", "vehicles_to_categories"}.issubset(tables):
            return
        category_ids = []
        seen = set()
        for raw_name in category_names:
            name = str(raw_name)
            normalized = name.casefold()
            if not name.strip() or normalized in seen:
                continue
            seen.add(normalized)
            row = cursor.execute(
                "SELECT id FROM categories WHERE name = ? COLLATE NOCASE",
                (name, )).fetchone()
            if row:
                category_id = row["id"]
            else:
                cursor.execute("INSERT INTO categories (name) VALUES (?)",
                               (name, ))
                category_id = cursor.lastrowid
            category_ids.append(category_id)

        link_columns = self._columns(cursor, "vehicles_to_categories")
        order = "id" if "id" in link_columns else "category_id"
        existing_ids = [
            row[0] for row in cursor.execute(
                f"SELECT category_id FROM vehicles_to_categories "
                f"WHERE vehicle_id = ? ORDER BY {order}", (vehicle_id, ))
        ]
        if existing_ids == category_ids:
            return
        cursor.execute(
            "DELETE FROM vehicles_to_categories WHERE vehicle_id = ?",
            (vehicle_id, ))
        cursor.executemany(
            """
            INSERT INTO vehicles_to_categories (vehicle_id, category_id)
            VALUES (?, ?)
            """, ((vehicle_id, category_id) for category_id in category_ids))

    @staticmethod
    def _sync_traction(cursor: sqlite3.Cursor, tables: Set[str],
                       vehicle_id: int, regulation_step: int) -> None:
        if "traction_list" not in tables:
            return
        if not regulation_step:
            cursor.execute("DELETE FROM traction_list WHERE loco_id = ?",
                           (vehicle_id, ))
            return
        cursor.execute(
            "UPDATE traction_list SET regulation_step = ? WHERE loco_id = ?",
            (regulation_step, vehicle_id))
        if cursor.rowcount == 0:
            cursor.execute(
                """
                INSERT INTO traction_list (loco_id, regulation_step, time)
                VALUES (?, ?, 0.0)
                """, (vehicle_id, regulation_step))

    @staticmethod
    def _delete_removed_locomotives(cursor: sqlite3.Cursor,
                                    tables: Set[str],
                                    kept_vehicle_ids: Set[int]) -> None:
        all_ids = {
            row[0] for row in cursor.execute(
                "SELECT id FROM vehicles WHERE type = 0")
        }
        for vehicle_id in all_ids - kept_vehicle_ids:
            if "functions" in tables:
                cursor.execute(
                    "DELETE FROM functions WHERE vehicle_id = ?",
                    (vehicle_id, ))
            if "vehicles_to_categories" in tables:
                cursor.execute(
                    "DELETE FROM vehicles_to_categories WHERE vehicle_id = ?",
                    (vehicle_id, ))
            if "traction_list" in tables:
                cursor.execute("DELETE FROM traction_list WHERE loco_id = ?",
                               (vehicle_id, ))
            cursor.execute("DELETE FROM vehicles WHERE id = ?", (vehicle_id, ))
