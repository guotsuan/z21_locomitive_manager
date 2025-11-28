#!/usr/bin/env python3
"""
GUI application to browse Z21 locomotives and their details.
Migrated to PySide6.
"""

import sys
import os
import json
import uuid
import zipfile
import sqlite3
import tempfile
import platform
import shutil
from pathlib import Path
from typing import Optional, Dict, List, Any

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QListWidget, QListWidgetItem, QLabel, QLineEdit,
    QPushButton, QComboBox, QCheckBox, QTextEdit, QTabWidget,
    QScrollArea, QGridLayout, QFileDialog, QMessageBox, QFrame,
    QFormLayout, QGroupBox, QMenu
)
from PySide6.QtCore import Qt, QSize, QTimer, Slot, Signal
from PySide6.QtGui import QPixmap, QIcon, QAction, QImage

# Try to import PyObjC for macOS sharing
try:
    from AppKit import NSSharingService, NSURL, NSArray
    HAS_PYOBJC = True
except ImportError:
    HAS_PYOBJC = False

# Try to import PaddleOCR
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
DISABLE_PADDLEOCR = os.environ.get('DISABLE_PADDLEOCR', '').lower() in ('1', 'true', 'yes')

try:
    if DISABLE_PADDLEOCR:
        print("PaddleOCR is disabled via DISABLE_PADDLEOCR environment variable")
        HAS_PADDLEOCR = False
    else:
        from paddleocr import PaddleOCR
        HAS_PADDLEOCR = True
except (ImportError, ModuleNotFoundError):
    HAS_PADDLEOCR = False
except Exception as e:
    print(f"Warning: PaddleOCR import failed: {e}")
    HAS_PADDLEOCR = False

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.parser import Z21Parser
from src.data_models import Z21File, Locomotive, FunctionInfo

class FunctionCard(QFrame):
    """Widget to display a single function."""
    def __init__(self, func_num: int, func_info: FunctionInfo, parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        self.func_num = func_num
        self.func_info = func_info
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Header: F# and Active Checkbox
        header_layout = QHBoxLayout()
        self.label_num = QLabel(f"F{func_num}")
        self.label_num.setStyleSheet("font-weight: bold;")
        self.check_active = QCheckBox()
        self.check_active.setChecked(func_info.is_active)
        header_layout.addWidget(self.label_num)
        header_layout.addStretch()
        header_layout.addWidget(self.check_active)
        layout.addLayout(header_layout)
        
        # Icon (Placeholder)
        self.icon_label = QLabel()
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setFixedSize(64, 64)
        self.icon_label.setStyleSheet("background-color: #eee; border: 1px solid #ccc;")
        self.icon_label.setText(func_info.image_name or "?")
        layout.addWidget(self.icon_label, 0, Qt.AlignCenter)
        
        # Type and Time
        type_layout = QHBoxLayout()
        type_str = func_info.button_type_name()
        self.label_type = QLabel(type_str)
        self.label_type.setStyleSheet("font-size: 10px; color: #666;")
        type_layout.addWidget(self.label_type)
        
        if func_info.button_type == 2 and func_info.time != "0":
            self.label_time = QLabel(f"⏱ {func_info.time}s")
            self.label_time.setStyleSheet("font-size: 10px; color: #666;")
            type_layout.addWidget(self.label_time)
            
        layout.addLayout(type_layout)

class Z21GUI(QMainWindow):
    """Main GUI application for browsing Z21 locomotives."""

    def __init__(self, z21_file: Path):
        super().__init__()
        self.z21_file = z21_file
        self.parser: Optional[Z21Parser] = None
        self.z21_data: Optional[Z21File] = None
        self.current_loco: Optional[Locomotive] = None
        self.current_loco_index: Optional[int] = None
        self.original_loco_address: Optional[int] = None
        self.user_selected_loco: Optional[Locomotive] = None
        self.default_icon_path = Path(__file__).parent.parent / "icons" / "neutrals_normal.png"
        self.icon_cache = {}
        self.icon_mapping = self.load_icon_mapping()
        
        self.setup_ui()
        self.load_data()

    def load_icon_mapping(self):
        """Load icon mapping from JSON file."""
        mapping_file = Path(__file__).parent.parent / "icon_mapping.json"
        if mapping_file.exists():
            try:
                with open(mapping_file, 'r') as f:
                    data = json.load(f)
                    return data.get('matches', {})
            except Exception:
                return {}
        return {}

    def setup_ui(self):
        """Set up the user interface."""
        self.setWindowTitle("Z21 Locomotive Manager")
        self.resize(1200, 800)

        # Main central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)

        # Splitter for Left (List) and Right (Details) panels
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        # --- Left Panel: Locomotive List ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # Search
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        self.search_input = QLineEdit()
        self.search_input.textChanged.connect(self.on_search)
        search_layout.addWidget(self.search_input)
        left_layout.addLayout(search_layout)

        # Buttons (Import, Delete, New)
        button_layout = QHBoxLayout()
        self.btn_import = QPushButton("Import")
        self.btn_import.clicked.connect(self.import_z21_loco)
        self.btn_delete = QPushButton("Delete")
        self.btn_delete.clicked.connect(self.delete_selected_locomotive)
        self.btn_new = QPushButton("New")
        self.btn_new.clicked.connect(self.create_new_locomotive)
        
        button_layout.addWidget(self.btn_import)
        button_layout.addWidget(self.btn_delete)
        button_layout.addWidget(self.btn_new)
        left_layout.addLayout(button_layout)

        # List Widget
        left_layout.addWidget(QLabel("Locomotives:"))
        self.loco_list = QListWidget()
        self.loco_list.currentItemChanged.connect(self.on_loco_select)
        left_layout.addWidget(self.loco_list)

        # Status Label
        self.status_label = QLabel("Loading...")
        self.status_label.setFrameStyle(QFrame.Sunken | QFrame.Panel)
        left_layout.addWidget(self.status_label)

        splitter.addWidget(left_panel)

        # --- Right Panel: Details ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()
        right_layout.addWidget(self.tabs)

        # Overview Tab
        self.overview_tab = QWidget()
        self.setup_overview_tab()
        self.tabs.addTab(self.overview_tab, "Overview")

        # Functions Tab
        self.functions_tab = QWidget()
        self.setup_functions_tab()
        self.tabs.addTab(self.functions_tab, "Functions")

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(1, 2) # Right panel gets more space

    def setup_overview_tab(self):
        layout = QVBoxLayout(self.overview_tab)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        
        # Details Group
        details_group = QGroupBox("Locomotive Details")
        details_layout = QGridLayout(details_group)
        
        # Image (Row 0-2, Col 4)
        self.image_label = QLabel("No Image")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setFrameStyle(QFrame.Sunken | QFrame.Panel)
        self.image_label.setFixedSize(200, 150) # Approximate size
        self.image_label.setCursor(Qt.PointingHandCursor)
        self.image_label.mousePressEvent = self.on_image_click
        details_layout.addWidget(self.image_label, 0, 4, 3, 1)

        # Fields
        # Row 0
        details_layout.addWidget(QLabel("Name:"), 0, 0)
        self.name_edit = QLineEdit()
        details_layout.addWidget(self.name_edit, 0, 1)
        
        details_layout.addWidget(QLabel("Address:"), 0, 2)
        self.address_edit = QLineEdit()
        details_layout.addWidget(self.address_edit, 0, 3)

        # Row 1
        details_layout.addWidget(QLabel("Max Speed:"), 1, 0)
        self.speed_edit = QLineEdit()
        details_layout.addWidget(self.speed_edit, 1, 1)

        details_layout.addWidget(QLabel("Direction:"), 1, 2)
        self.direction_combo = QComboBox()
        self.direction_combo.addItems(['Forward', 'Reverse'])
        details_layout.addWidget(self.direction_combo, 1, 3)

        # Row 2
        details_layout.addWidget(QLabel("Full Name:"), 2, 0)
        self.full_name_edit = QLineEdit()
        details_layout.addWidget(self.full_name_edit, 2, 1, 1, 3)

        # Row 3
        details_layout.addWidget(QLabel("Railway:"), 3, 0)
        self.railway_edit = QLineEdit()
        details_layout.addWidget(self.railway_edit, 3, 1)

        details_layout.addWidget(QLabel("Article Number:"), 3, 2)
        self.article_edit = QLineEdit()
        details_layout.addWidget(self.article_edit, 3, 3)

        # Row 4
        details_layout.addWidget(QLabel("Decoder Type:"), 4, 0)
        self.decoder_edit = QLineEdit()
        details_layout.addWidget(self.decoder_edit, 4, 1)

        details_layout.addWidget(QLabel("Build Year:"), 4, 2)
        self.build_year_edit = QLineEdit()
        details_layout.addWidget(self.build_year_edit, 4, 3)

        # Row 5
        details_layout.addWidget(QLabel("Buffer Length:"), 5, 0)
        self.buffer_edit = QLineEdit()
        details_layout.addWidget(self.buffer_edit, 5, 1)

        details_layout.addWidget(QLabel("Service Weight:"), 5, 2)
        self.weight_edit = QLineEdit()
        details_layout.addWidget(self.weight_edit, 5, 3)

        # Row 6
        details_layout.addWidget(QLabel("Model Weight:"), 6, 0)
        self.model_weight_edit = QLineEdit()
        details_layout.addWidget(self.model_weight_edit, 6, 1)

        details_layout.addWidget(QLabel("Min Radius:"), 6, 2)
        self.rmin_edit = QLineEdit()
        details_layout.addWidget(self.rmin_edit, 6, 3)

        # Row 7
        details_layout.addWidget(QLabel("IP Address:"), 7, 0)
        self.ip_edit = QLineEdit()
        details_layout.addWidget(self.ip_edit, 7, 1)

        details_layout.addWidget(QLabel("Driver's Cab:"), 7, 2)
        self.cab_edit = QLineEdit()
        details_layout.addWidget(self.cab_edit, 7, 3)

        # Row 8
        checkbox_layout = QHBoxLayout()
        self.active_check = QCheckBox("Active")
        self.crane_check = QCheckBox("Crane")
        checkbox_layout.addWidget(self.active_check)
        checkbox_layout.addWidget(self.crane_check)
        details_layout.addLayout(checkbox_layout, 8, 1)

        details_layout.addWidget(QLabel("Speed Display:"), 8, 2)
        self.speed_display_combo = QComboBox()
        self.speed_display_combo.addItems(['km/h', 'Regulation Step', 'mph'])
        details_layout.addWidget(self.speed_display_combo, 8, 3)

        # Row 9
        details_layout.addWidget(QLabel("Vehicle Type:"), 9, 0)
        self.vehicle_type_combo = QComboBox()
        self.vehicle_type_combo.addItems(['Loco', 'Wagon', 'Accessory'])
        details_layout.addWidget(self.vehicle_type_combo, 9, 1)

        details_layout.addWidget(QLabel("Reg Step:"), 9, 2)
        self.reg_step_combo = QComboBox()
        self.reg_step_combo.addItems(['128', '28', '14'])
        details_layout.addWidget(self.reg_step_combo, 9, 3)

        # Row 10
        details_layout.addWidget(QLabel("Categories:"), 10, 0)
        self.categories_edit = QLineEdit()
        details_layout.addWidget(self.categories_edit, 10, 1)

        details_layout.addWidget(QLabel("In Stock Since:"), 10, 2)
        self.stock_since_edit = QLineEdit()
        details_layout.addWidget(self.stock_since_edit, 10, 3)

        # Row 11
        details_layout.addWidget(QLabel("Description:"), 11, 0)
        self.desc_edit = QTextEdit()
        self.desc_edit.setMaximumHeight(100)
        details_layout.addWidget(self.desc_edit, 11, 1, 1, 4)

        scroll_layout.addWidget(details_group)

        # Action Buttons
        action_layout = QHBoxLayout()
        self.btn_export = QPushButton("Export Z21 Loco")
        self.btn_export.clicked.connect(self.export_z21_loco)
        self.btn_share = QPushButton("Share with WIFI")
        self.btn_share.clicked.connect(self.share_with_airdrop)
        self.btn_scan = QPushButton("Scan for Details")
        self.btn_scan.clicked.connect(self.scan_for_details)
        self.btn_save = QPushButton("Save Changes")
        self.btn_save.clicked.connect(self.save_locomotive_changes)
        
        action_layout.addWidget(self.btn_export)
        action_layout.addWidget(self.btn_share)
        action_layout.addStretch()
        action_layout.addWidget(self.btn_scan)
        action_layout.addWidget(self.btn_save)
        
        scroll_layout.addLayout(action_layout)

        # Overview Text (CVs etc)
        self.overview_text = QTextEdit()
        self.overview_text.setReadOnly(True)
        self.overview_text.setFontFamily("Courier")
        scroll_layout.addWidget(self.overview_text)

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

    def setup_functions_tab(self):
        layout = QVBoxLayout(self.functions_tab)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.functions_content = QWidget()
        self.functions_grid = QGridLayout(self.functions_content)
        self.functions_grid.setAlignment(Qt.AlignTop)
        
        scroll.setWidget(self.functions_content)
        layout.addWidget(scroll)

    def load_data(self):
        """Load Z21 file data."""
        try:
            self.parser = Z21Parser(self.z21_file)
            self.z21_data = self.parser.parse()
            self.update_status_count()
            self.populate_list(auto_select_first=True)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load file: {e}")
            self.status_label.setText("Error loading file")

    def update_status_count(self):
        if self.z21_data:
            self.status_label.setText(f"Loaded {len(self.z21_data.locomotives)} locomotives")
        else:
            self.status_label.setText("No data loaded")

    def populate_list(self, filter_text: str = "", preserve_selection: bool = False, auto_select_first: bool = False):
        current_row = self.loco_list.currentRow()
        self.loco_list.clear()
        
        if not self.z21_data:
            return

        filter_text = filter_text.lower()
        
        for i, loco in enumerate(self.z21_data.locomotives):
            search_str = f"{loco.name} {loco.address}".lower()
            if not filter_text or filter_text in search_str:
                item = QListWidgetItem(f"{loco.name} (Addr: {loco.address})")
                item.setData(Qt.UserRole, i) # Store index
                self.loco_list.addItem(item)

        if preserve_selection and current_row >= 0 and current_row < self.loco_list.count():
            self.loco_list.setCurrentRow(current_row)
        elif auto_select_first and self.loco_list.count() > 0:
            self.loco_list.setCurrentRow(0)

    def on_search(self, text):
        self.populate_list(filter_text=text, auto_select_first=True)

    def on_loco_select(self, current, previous):
        if not current:
            return
            
        index = current.data(Qt.UserRole)
        self.current_loco_index = index
        self.current_loco = self.z21_data.locomotives[index]
        self.original_loco_address = self.current_loco.address
        
        self.update_details_view()
        self.update_functions_view()

    def update_details_view(self):
        """Update the details display."""
        if not self.current_loco:
            return

        loco = self.current_loco
        
        # Update editable fields
        self.name_edit.setText(loco.name)
        self.address_edit.setText(str(loco.address))
        self.speed_edit.setText(str(loco.speed))
        
        direction_str = 'Forward' if loco.direction else 'Reverse'
        index = self.direction_combo.findText(direction_str)
        if index >= 0: self.direction_combo.setCurrentIndex(index)

        self.full_name_edit.setText(loco.full_name)
        self.railway_edit.setText(loco.railway)
        self.article_edit.setText(loco.article_number)
        self.decoder_edit.setText(loco.decoder_type)
        self.build_year_edit.setText(loco.build_year)
        self.buffer_edit.setText(loco.model_buffer_length)
        self.weight_edit.setText(loco.service_weight)
        self.model_weight_edit.setText(loco.model_weight)
        self.rmin_edit.setText(loco.rmin)
        self.ip_edit.setText(loco.ip)
        self.cab_edit.setText(loco.drivers_cab)
        
        self.active_check.setChecked(loco.active)
        self.crane_check.setChecked(loco.crane)
        
        speed_map = {0: 'km/h', 1: 'Regulation Step', 2: 'mph'}
        self.speed_display_combo.setCurrentText(speed_map.get(loco.speed_display, 'km/h'))
        
        vehicle_map = {0: 'Loco', 1: 'Wagon', 2: 'Accessory'}
        self.vehicle_type_combo.setCurrentText(vehicle_map.get(loco.rail_vehicle_type, 'Loco'))
        
        reg_map = {0: '128', 1: '28', 2: '14'}
        self.reg_step_combo.setCurrentText(reg_map.get(loco.regulation_step, '128'))
        
        self.categories_edit.setText(', '.join(loco.categories) if loco.categories else '')
        self.stock_since_edit.setText(getattr(loco, 'in_stock_since', '') or '')
        
        self.desc_edit.setPlainText(loco.description)
        
        # Image
        if loco.image_name:
            self.image_label.setText(f"Image:\n{loco.image_name}")
            # TODO: Load actual image
        else:
            self.image_label.setText("No Image")

        # Update Overview Text
        text = f"{'='*40}\nFUNCTION SUMMARY\n{'='*40}\n\n"
        text += f"Functions: {len(loco.functions)} configured\n"
        text += f"Details:   {len(loco.function_details)} available\n\n"
        
        if loco.function_details:
            sorted_funcs = sorted(loco.function_details.items(), key=lambda x: x[1].function_number)
            for func_num, func_info in sorted_funcs:
                shortcut = f" [{func_info.shortcut}]" if func_info.shortcut else ""
                time_str = f" (time: {func_info.time}s)" if (func_info.button_type == 2 and func_info.time != "0") else ""
                text += f"F{func_num:<3} - {func_info.image_name:<20} [{func_info.button_type_name()}] {shortcut}{time_str}\n"
        
        self.overview_text.setPlainText(text)

    def update_functions_view(self):
        """Update functions tab."""
        if not self.current_loco:
            return
            
        # Clear grid
        while self.functions_grid.count():
            item = self.functions_grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
                
        loco = self.current_loco
        if not loco.function_details:
            return

        sorted_funcs = sorted(loco.function_details.items(), key=lambda x: x[1].function_number)
        
        # Layout calculation
        # We'll just use a fixed number of columns or let it flow?
        # QGridLayout doesn't flow automatically. We need to calculate row/col.
        cols = 4
        
        for i, (func_num, func_info) in enumerate(sorted_funcs):
            card = FunctionCard(func_num, func_info)
            row = i // cols
            col = i % cols
            self.functions_grid.addWidget(card, row, col)

    def on_image_click(self, event):
        if not self.current_loco: return
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Image", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if file_path:
            # Logic to copy image to z21 file would go here
            QMessageBox.information(self, "Image Selected", f"Selected: {file_path}\n(Image import logic to be implemented)")

    def import_z21_loco(self):
        QMessageBox.information(self, "Import", "Import logic to be implemented")

    def delete_selected_locomotive(self):
        if not self.current_loco: return
        reply = QMessageBox.question(self, "Confirm Delete", f"Delete {self.current_loco.name}?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            # Delete logic
            pass

    def create_new_locomotive(self):
        # Create new logic
        pass

    def export_z21_loco(self):
        if not self.current_loco: return
        QMessageBox.information(self, "Export", "Export logic to be implemented")

    def share_with_airdrop(self):
        if not self.current_loco: return
        if not HAS_PYOBJC:
            QMessageBox.warning(self, "Error", "PyObjC not available")
            return
        # Share logic
        pass

    def scan_for_details(self):
        if not self.current_loco: return
        # Scan logic
        pass

    def save_locomotive_changes(self):
        if not self.current_loco: return
        
        loco = self.current_loco
        loco.name = self.name_edit.text()
        try:
            loco.address = int(self.address_edit.text())
            loco.speed = int(self.speed_edit.text())
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Address and Speed must be numbers")
            return
            
        loco.direction = (self.direction_combo.currentText() == 'Forward')
        loco.full_name = self.full_name_edit.text()
        loco.railway = self.railway_edit.text()
        loco.article_number = self.article_edit.text()
        loco.decoder_type = self.decoder_edit.text()
        loco.build_year = self.build_year_edit.text()
        loco.model_buffer_length = self.buffer_edit.text()
        loco.service_weight = self.weight_edit.text()
        loco.model_weight = self.model_weight_edit.text()
        loco.rmin = self.rmin_edit.text()
        loco.ip = self.ip_edit.text()
        loco.drivers_cab = self.cab_edit.text()
        loco.active = self.active_check.isChecked()
        loco.crane = self.crane_check.isChecked()
        
        speed_map_inv = {'km/h': 0, 'Regulation Step': 1, 'mph': 2}
        loco.speed_display = speed_map_inv.get(self.speed_display_combo.currentText(), 0)
        
        vehicle_map_inv = {'Loco': 0, 'Wagon': 1, 'Accessory': 2}
        loco.rail_vehicle_type = vehicle_map_inv.get(self.vehicle_type_combo.currentText(), 0)
        
        reg_map_inv = {'128': 0, '28': 1, '14': 2}
        loco.regulation_step = reg_map_inv.get(self.reg_step_combo.currentText(), 0)
        
        loco.categories = [c.strip() for c in self.categories_edit.text().split(',') if c.strip()]
        loco.in_stock_since = self.stock_since_edit.text()
        loco.description = self.desc_edit.toPlainText()
        
        # Save to file (needs implementation of save logic in parser or here)
        # For now just update the list item
        if self.current_loco_index is not None:
            item = self.loco_list.item(self.loco_list.currentRow())
            item.setText(f"{loco.name} (Addr: {loco.address})")
            
        QMessageBox.information(self, "Saved", "Changes saved to memory (File save not fully implemented)")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Argument parsing
    import argparse
    parser = argparse.ArgumentParser(description='Z21 Locomotive Browser GUI')
    parser.add_argument('file', type=Path, nargs='?', default=Path('z21_new.z21'), help='Z21 file to open')
    args = parser.parse_args()

    if not args.file.exists():
        print(f"Error: File not found: {args.file}")
        sys.exit(1)

    window = Z21GUI(args.file)
    window.show()
    sys.exit(app.exec())
