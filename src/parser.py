"""
Parser for Z21 file format.

The .z21 file is actually a ZIP archive containing:
- Format 1 (old): loco_data.xml - XML file with locomotive and accessory data
- Format 2 (new): Loco.sqlite - SQLite database with locomotive data
- Images: PNG/JPG files for locomotives, wagons, and backgrounds
"""

import zipfile
import xml.etree.ElementTree as ET
import sqlite3
import tempfile
from pathlib import Path
from typing import Optional, Dict
from .data_models import Z21File, Locomotive, Accessory, Layout, Settings, UnknownBlock, FunctionInfo


class Z21Parser:
    """Parser for Z21 files (ZIP archives containing XML/SQLite and images)."""
    
    def __init__(self, file_path: Path):
        """
        Initialize parser.
        
        Args:
            file_path: Path to Z21 file
        """
        self.file_path = Path(file_path)
        
    def parse(self) -> Z21File:
        """
        Parse Z21 file and return data model.
        
        Supports both XML format (old) and SQLite format (new).
        
        Returns:
            Z21File object containing parsed data
        """
        z21_file = Z21File()
        
        try:
            with zipfile.ZipFile(self.file_path, 'r') as zf:
                # List all files in the archive
                file_list = zf.namelist()
                
                # Detect format: look for SQLite first (newer format)
                sqlite_file = None
                for filename in file_list:
                    if filename.endswith('.sqlite'):
                        sqlite_file = filename
                        break
                
                if sqlite_file:
                    # Parse SQLite format (new format)
                    self._parse_sqlite(zf, sqlite_file, z21_file)
                else:
                    # Look for XML file (old format)
                    xml_file = None
                    for filename in file_list:
                        if filename.endswith('.xml'):
                            xml_file = filename
                            break
                    
                    if xml_file:
                        # Read and parse XML
                        xml_content = zf.read(xml_file).decode('utf-8', errors='ignore')
                        self._parse_xml(xml_content, z21_file)
                
                # Store image files info (for now, just track them)
                # TODO: Extract and store images if needed
                for filename in file_list:
                    if filename.endswith(('.png', '.jpg', '.jpeg')):
                        # Images can be extracted later if needed
                        pass
                        
        except zipfile.BadZipFile:
            # Fallback: treat as unknown binary if not a ZIP
            z21_file.unknown_blocks.append(
                UnknownBlock(
                    offset=0,
                    length=self.file_path.stat().st_size,
                    data=self.file_path.read_bytes()
                )
            )
        
        return z21_file
    
    def _parse_sqlite(self, zipfile_obj: zipfile.ZipFile, sqlite_path: str, z21_file: Z21File):
        """Parse SQLite database from ZIP file."""
        # Extract SQLite database to temporary file
        sqlite_data = zipfile_obj.read(sqlite_path)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.sqlite') as tmp:
            tmp.write(sqlite_data)
            tmp_path = tmp.name
        
        try:
            # Connect to database
            db = sqlite3.connect(tmp_path)
            db.row_factory = sqlite3.Row  # Enable column access by name
            cursor = db.cursor()
            
            # Parse version from update_history (if available)
            cursor.execute("SELECT MAX(to_database_version) as version FROM update_history")
            version_row = cursor.fetchone()
            if version_row and version_row['version']:
                z21_file.version = version_row['version']
            
            # Parse locomotives from vehicles table (type=0 means locomotive)
            cursor.execute("""
                SELECT id, name, address, max_speed, active, traction_direction, 
                       image_name, drivers_cab, description
                FROM vehicles 
                WHERE type = 0
                ORDER BY position
            """)
            
            vehicles = cursor.fetchall()
            
            for vehicle in vehicles:
                loco = Locomotive()
                loco.address = vehicle['address'] or 0
                loco.name = vehicle['name'] or ''
                loco.speed = vehicle['max_speed'] or 0
                loco.direction = (vehicle['traction_direction'] or 0) == 1
                # Store vehicle ID for reliable updates (using a custom attribute)
                loco._vehicle_id = vehicle['id']  # type: ignore
                
                # Parse functions for this vehicle
                cursor.execute("""
                    SELECT function, position, shortcut, time, image_name, 
                           show_function_number, is_configured, button_type
                    FROM functions
                    WHERE vehicle_id = ?
                    ORDER BY position
                """, (vehicle['id'],))
                
                functions = cursor.fetchall()
                for func in functions:
                    func_num = func['function'] or 0
                    # Function is considered active if it exists in the table
                    loco.functions[func_num] = True
                    
                    # Store detailed function information
                    func_info = FunctionInfo(
                        function_number=func_num,
                        image_name=func['image_name'] or '',
                        shortcut=func['shortcut'] or '',
                        position=func['position'] or 0,
                        time=str(func['time']) if func['time'] is not None else '0',
                        button_type=func['button_type'] if func['button_type'] is not None else 0,
                        is_active=True  # All functions in the table are considered active
                    )
                    loco.function_details[func_num] = func_info
                
                # TODO: Parse CVs if available in database
                
                z21_file.locomotives.append(loco)
            
            # Parse accessories (type != 0 in vehicles table)
            # TODO: Implement accessory parsing
            
            # Parse layouts
            cursor.execute("SELECT id, name FROM layout_data")
            layouts_data = cursor.fetchall()
            for layout_row in layouts_data:
                layout = Layout()
                layout.name = layout_row['name'] or ''
                z21_file.layouts.append(layout)
            
            db.close()
        finally:
            # Clean up temporary file
            Path(tmp_path).unlink()
    
    def _parse_xml(self, xml_content: str, z21_file: Z21File):
        """Parse XML content and populate Z21File data model."""
        try:
            root = ET.fromstring(xml_content)
            
            # Parse export metadata
            exportmeta = root.find('exportmeta')
            if exportmeta is not None:
                version_elem = exportmeta.find('version')
                if version_elem is not None and version_elem.text:
                    z21_file.version = int(version_elem.text)
            
            # Parse locomotives
            locos = root.find('locos')
            if locos is not None:
                for loco_elem in locos.findall('loco'):
                    loco = self._parse_locomotive(loco_elem)
                    z21_file.locomotives.append(loco)
            
            # Parse accessories (if present)
            # TODO: Identify accessory elements in XML
            
            # Parse layouts (if present)
            # TODO: Identify layout elements in XML
            
        except ET.ParseError as e:
            # If XML parsing fails, store as unknown
            z21_file.unknown_blocks.append(
                UnknownBlock(
                    offset=0,
                    length=len(xml_content),
                    data=xml_content.encode('utf-8')
                )
            )
    
    def _parse_locomotive(self, loco_elem: ET.Element) -> Locomotive:
        """Parse a locomotive element from XML."""
        loco = Locomotive()
        
        # Parse basic fields
        address_elem = loco_elem.find('address')
        if address_elem is not None and address_elem.text:
            loco.address = int(address_elem.text)
        
        name_elem = loco_elem.find('name')
        if name_elem is not None and name_elem.text:
            loco.name = name_elem.text
        
        # Parse max_speed
        max_speed_elem = loco_elem.find('max_speed')
        if max_speed_elem is not None and max_speed_elem.text:
            loco.speed = int(max_speed_elem.text)
        
        # Parse traction_direction
        direction_elem = loco_elem.find('traction_direction')
        if direction_elem is not None and direction_elem.text:
            loco.direction = int(direction_elem.text) == 1
        
        # Parse functions
        functions_elem = loco_elem.find('functions')
        if functions_elem is not None:
            for func_elem in functions_elem.findall('function_element'):
                func_num_elem = func_elem.find('function')
                func_active = func_elem.find('active')
                image_name_elem = func_elem.find('image_name')
                shortcut_elem = func_elem.find('shortcut')
                position_elem = func_elem.find('position')
                time_elem = func_elem.find('time')
                
                if func_num_elem is not None and func_num_elem.text:
                    func_num = int(func_num_elem.text)
                    # Default to active if not specified
                    is_active = True
                    if func_active is not None and func_active.text:
                        is_active = int(func_active.text) == 1
                    loco.functions[func_num] = is_active
                    
                    # Get button_type from XML (if available)
                    button_type_elem = func_elem.find('button_type')
                    button_type = 0  # Default to momentary
                    if button_type_elem is not None and button_type_elem.text:
                        button_type = int(button_type_elem.text)
                    
                    # Store detailed function information
                    func_info = FunctionInfo(
                        function_number=func_num,
                        image_name=image_name_elem.text if image_name_elem is not None and image_name_elem.text else '',
                        shortcut=shortcut_elem.text if shortcut_elem is not None and shortcut_elem.text else '',
                        position=int(position_elem.text) if position_elem is not None and position_elem.text else 0,
                        time=time_elem.text if time_elem is not None and time_elem.text else '0',
                        button_type=button_type,
                        is_active=is_active
                    )
                    loco.function_details[func_num] = func_info
        
        # Parse CVs (if present)
        # TODO: Identify CV elements in XML structure
        
        return loco
    
    def write(self, z21_file: Z21File, output_path: Optional[Path] = None) -> Path:
        """
        Write Z21File data model back to Z21 file.
        
        Args:
            z21_file: Z21File object containing data to write
            output_path: Optional output path. If None, overwrites original file.
        
        Returns:
            Path to written file
        """
        if output_path is None:
            output_path = self.file_path
        
        output_path = Path(output_path)
        
        # If writing to same file, use temporary file first to avoid corruption
        use_temp = (output_path == self.file_path)
        if use_temp:
            import tempfile
            temp_output = tempfile.NamedTemporaryFile(delete=False, suffix='.z21', dir=output_path.parent)
            temp_output_path = Path(temp_output.name)
            temp_output.close()
        else:
            temp_output_path = output_path
        
        # Read original ZIP to preserve images and other files
        with zipfile.ZipFile(self.file_path, 'r') as input_zip:
            # Detect format
            sqlite_file = None
            for filename in input_zip.namelist():
                if filename.endswith('.sqlite'):
                    sqlite_file = filename
                    break
            
            if sqlite_file:
                # Update SQLite format
                written_path = self._write_sqlite(input_zip, sqlite_file, z21_file, temp_output_path)
                
                # If we used a temp file, replace original with it
                if use_temp:
                    import shutil
                    shutil.move(str(temp_output_path), str(output_path))
                
                return output_path
            else:
                # Update XML format (not yet implemented)
                raise NotImplementedError("Writing XML format not yet implemented")
    
    def _write_sqlite(self, input_zip: zipfile.ZipFile, sqlite_path: str, 
                     z21_file: Z21File, output_path: Path) -> Path:
        """Write SQLite database back to ZIP file."""
        # Extract SQLite database to temporary file
        sqlite_data = input_zip.read(sqlite_path)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.sqlite') as tmp:
            tmp.write(sqlite_data)
            tmp_path = tmp.name
        
        try:
            # Connect to database
            db = sqlite3.connect(tmp_path)
            db.row_factory = sqlite3.Row
            cursor = db.cursor()
            
            # Update locomotives
            for loco in z21_file.locomotives:
                vehicle_id = None
                
                # First try to use stored vehicle ID (most reliable)
                if hasattr(loco, '_vehicle_id') and loco._vehicle_id:
                    vehicle_id = loco._vehicle_id
                    # Verify the vehicle still exists
                    cursor.execute("SELECT id FROM vehicles WHERE id = ? AND type = 0", (vehicle_id,))
                    if not cursor.fetchone():
                        vehicle_id = None  # Vehicle ID invalid, try other methods
                
                # If no vehicle ID, try by current address
                if not vehicle_id:
                    cursor.execute("""
                        SELECT id FROM vehicles 
                        WHERE type = 0 AND address = ?
                    """, (loco.address,))
                    vehicle_row = cursor.fetchone()
                    if vehicle_row:
                        vehicle_id = vehicle_row['id']
                
                # If still not found, try by name (as fallback)
                if not vehicle_id:
                    cursor.execute("""
                        SELECT id FROM vehicles 
                        WHERE type = 0 AND name = ?
                    """, (loco.name,))
                    vehicle_row = cursor.fetchone()
                    if vehicle_row:
                        vehicle_id = vehicle_row['id']
                
                if vehicle_id:
                    # Update vehicle fields
                    cursor.execute("""
                        UPDATE vehicles 
                        SET name = ?, address = ?, max_speed = ?, traction_direction = ?
                        WHERE id = ?
                    """, (
                        loco.name,
                        loco.address,
                        loco.speed,
                        1 if loco.direction else 0,
                        vehicle_id
                    ))
                    # Update stored vehicle ID in case it changed
                    loco._vehicle_id = vehicle_id  # type: ignore
                    
                    # Sync functions for this vehicle
                    # Get existing functions from database
                    cursor.execute("""
                        SELECT function FROM functions WHERE vehicle_id = ?
                    """, (vehicle_id,))
                    existing_func_nums = {row[0] for row in cursor.fetchall()}
                    
                    # Get current functions from locomotive
                    current_func_nums = set(loco.function_details.keys())
                    
                    # Delete functions that no longer exist
                    funcs_to_delete = existing_func_nums - current_func_nums
                    for func_num in funcs_to_delete:
                        cursor.execute("""
                            DELETE FROM functions 
                            WHERE vehicle_id = ? AND function = ?
                        """, (vehicle_id, func_num))
                    
                    # Insert or update functions
                    for func_num, func_info in loco.function_details.items():
                        # Check if function exists
                        cursor.execute("""
                            SELECT function FROM functions 
                            WHERE vehicle_id = ? AND function = ?
                        """, (vehicle_id, func_num))
                        
                        time_value = float(func_info.time) if func_info.time and func_info.time != "0" else None
                        
                        if cursor.fetchone():
                            # Update existing function
                            cursor.execute("""
                                UPDATE functions 
                                SET position = ?, shortcut = ?, time = ?, 
                                    image_name = ?, button_type = ?, 
                                    is_configured = 1, show_function_number = 1
                                WHERE vehicle_id = ? AND function = ?
                            """, (
                                func_info.position,
                                func_info.shortcut or '',
                                time_value,
                                func_info.image_name or '',
                                func_info.button_type,
                                vehicle_id,
                                func_num
                            ))
                        else:
                            # Insert new function
                            cursor.execute("""
                                INSERT INTO functions 
                                (vehicle_id, function, position, shortcut, time, 
                                 image_name, button_type, is_configured, show_function_number)
                                VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1)
                            """, (
                                vehicle_id,
                                func_num,
                                func_info.position,
                                func_info.shortcut or '',
                                time_value,
                                func_info.image_name or '',
                                func_info.button_type
                            ))
                else:
                    # Vehicle not found - might be a new locomotive
                    # For now, skip (could implement INSERT if needed)
                    pass
            
            # Commit changes
            db.commit()
            db.close()
            
            # Read updated database
            with open(tmp_path, 'rb') as f:
                updated_sqlite_data = f.read()
            
            # Create new ZIP file with updated database
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as output_zip:
                # Copy all files from original ZIP, replacing SQLite file
                for item in input_zip.infolist():
                    if item.filename == sqlite_path:
                        # Write updated SQLite file with preserved metadata
                        zip_info = zipfile.ZipInfo(
                            filename=item.filename,
                            date_time=item.date_time
                        )
                        zip_info.compress_type = zipfile.ZIP_DEFLATED
                        zip_info.external_attr = item.external_attr
                        output_zip.writestr(zip_info, updated_sqlite_data)
                    else:
                        # Copy other files as-is with preserved metadata
                        data = input_zip.read(item.filename)
                        zip_info = zipfile.ZipInfo(
                            filename=item.filename,
                            date_time=item.date_time
                        )
                        zip_info.compress_type = item.compress_type
                        zip_info.external_attr = item.external_attr
                        output_zip.writestr(zip_info, data)
            
            return output_path
            
        finally:
            # Clean up temporary file
            Path(tmp_path).unlink()

