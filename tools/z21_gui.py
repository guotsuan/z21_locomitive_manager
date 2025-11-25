#!/usr/bin/env python3
"""
GUI application to browse Z21 locomotives and their details.
"""

import sys
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from pathlib import Path
from typing import Optional
import json

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.parser import Z21Parser
from src.data_models import Z21File, Locomotive, FunctionInfo


class Z21GUI:
    """Main GUI application for browsing Z21 locomotives."""

    def __init__(self, root, z21_file: Path):
        self.root = root
        self.z21_file = z21_file
        self.parser: Optional[Z21Parser] = None
        self.z21_data: Optional[Z21File] = None
        self.current_loco: Optional[Locomotive] = None
        self.current_loco_index: Optional[
            int] = None  # Index in z21_data.locomotives
        self.original_loco_address: Optional[
            int] = None  # Store original address for database lookup
        self.default_icon_path = Path(
            __file__).parent.parent / "icons" / "neutrals_normal.png"
        self.icon_cache = {}  # Cache for loaded icons
        self.icon_mapping = self.load_icon_mapping()  # Load icon mapping

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
        self.root.title(f"Z21 Locomotive Browser - {self.z21_file.name}")
        self.root.geometry("1200x800")

        # Configure ttk styles for better visibility
        style = ttk.Style()
        # Configure Notebook tab colors for better visibility
        style.configure('TNotebook.Tab',
                        foreground='#000000',
                        background='#F0F0F0',
                        padding=[10, 5])
        style.map('TNotebook.Tab',
                  background=[('selected', '#E0E0E0')],
                  foreground=[('selected', '#000000')])

        # Create main paned window
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left panel: Locomotive list
        left_frame = ttk.Frame(main_paned)
        main_paned.add(left_frame, weight=1)

        # Search box
        search_frame = ttk.Frame(left_frame)
        search_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT, padx=5)
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.on_search)
        search_entry = ttk.Entry(search_frame,
                                 textvariable=self.search_var,
                                 width=20)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # Locomotive list
        list_frame = ttk.Frame(left_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        ttk.Label(list_frame, text="Locomotives:",
                  font=('Arial', 10, 'bold')).pack(anchor=tk.W)

        # Listbox with scrollbar
        listbox_frame = ttk.Frame(list_frame)
        listbox_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        scrollbar = ttk.Scrollbar(listbox_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.loco_listbox = tk.Listbox(listbox_frame,
                                       yscrollcommand=scrollbar.set,
                                       font=('Arial', 10))
        self.loco_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.loco_listbox.bind('<<ListboxSelect>>', self.on_loco_select)
        scrollbar.config(command=self.loco_listbox.yview)

        # Status label
        self.status_label = ttk.Label(left_frame,
                                      text="Loading...",
                                      relief=tk.SUNKEN)
        self.status_label.pack(fill=tk.X, padx=5, pady=5)

        # Right panel: Details
        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=2)

        # Details notebook (tabs)
        self.notebook = ttk.Notebook(right_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Overview tab
        self.overview_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.overview_frame, text="Overview")
        self.setup_overview_tab()

        # Functions tab
        self.functions_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.functions_frame, text="Functions")
        self.setup_functions_tab()

    def setup_overview_tab(self):
        """Set up the overview tab."""
        # Top frame for editable locomotive details
        details_frame = ttk.LabelFrame(self.overview_frame,
                                       text="Locomotive Details",
                                       padding=10)
        details_frame.pack(fill=tk.X, padx=5, pady=5)

        # Name field
        ttk.Label(details_frame, text="Name:", width=15,
                  anchor='e').grid(row=0, column=0, padx=5, pady=5, sticky='e')
        self.name_var = tk.StringVar()
        self.name_entry = ttk.Entry(details_frame,
                                    textvariable=self.name_var,
                                    width=40)
        self.name_entry.grid(row=0, column=1, padx=5, pady=5, sticky='ew')

        # Address field
        ttk.Label(details_frame, text="Address:", width=15,
                  anchor='e').grid(row=1, column=0, padx=5, pady=5, sticky='e')
        self.address_var = tk.StringVar()
        self.address_entry = ttk.Entry(details_frame,
                                       textvariable=self.address_var,
                                       width=40)
        self.address_entry.grid(row=1, column=1, padx=5, pady=5, sticky='ew')

        # Max Speed field
        ttk.Label(details_frame, text="Max Speed:", width=15,
                  anchor='e').grid(row=2, column=0, padx=5, pady=5, sticky='e')
        self.speed_var = tk.StringVar()
        self.speed_entry = ttk.Entry(details_frame,
                                     textvariable=self.speed_var,
                                     width=40)
        self.speed_entry.grid(row=2, column=1, padx=5, pady=5, sticky='ew')

        # Direction field (dropdown)
        ttk.Label(details_frame, text="Direction:", width=15,
                  anchor='e').grid(row=3, column=0, padx=5, pady=5, sticky='e')
        self.direction_var = tk.StringVar()
        self.direction_combo = ttk.Combobox(details_frame,
                                            textvariable=self.direction_var,
                                            values=['Forward', 'Reverse'],
                                            state='readonly',
                                            width=37)
        self.direction_combo.grid(row=3, column=1, padx=5, pady=5, sticky='ew')

        # Configure column weights
        details_frame.grid_columnconfigure(1, weight=1)

        # Save button
        button_frame = ttk.Frame(self.overview_frame)
        button_frame.pack(fill=tk.X, padx=5, pady=5)
        self.save_button = ttk.Button(button_frame,
                                      text="Save Changes",
                                      command=self.save_locomotive_changes)
        self.save_button.pack(side=tk.RIGHT, padx=5)

        # Scrollable text area for function summary and CV values
        text_frame = ttk.Frame(self.overview_frame)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.overview_text = scrolledtext.ScrolledText(text_frame,
                                                       wrap=tk.WORD,
                                                       font=('Courier', 10),
                                                       state=tk.DISABLED)
        self.overview_text.pack(fill=tk.BOTH, expand=True)

    def setup_functions_tab(self):
        """Set up the functions tab."""
        # Scrollable frame for functions with grid layout
        canvas = tk.Canvas(self.functions_frame, bg='#F0F0F0')
        scrollbar = ttk.Scrollbar(self.functions_frame,
                                  orient="vertical",
                                  command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#F0F0F0')

        def on_frame_configure(event):
            """Update scroll region when frame size changes."""
            canvas.configure(scrollregion=canvas.bbox("all"))

        def on_canvas_configure(event):
            """Update frame width to match canvas."""
            canvas_width = event.width
            canvas.itemconfig(canvas_window, width=canvas_width)

        def on_mousewheel(event):
            """Handle mouse wheel scrolling (two-finger scroll on trackpad)."""
            # Check if we're in the functions tab
            try:
                if self.notebook.index(self.notebook.select()) != 1:
                    return
            except:
                pass

            # Handle different platforms and event types
            scroll_amount = 0

            # macOS/Linux Button-4/5 (two-finger scroll)
            if event.num == 4:
                scroll_amount = -5
            elif event.num == 5:
                scroll_amount = 5
            # Windows/Linux with delta attribute
            elif hasattr(event, 'delta'):
                scroll_amount = -1 * (event.delta // 120)
                if scroll_amount == 0:
                    scroll_amount = -1 if event.delta > 0 else 1
            # macOS with deltaY attribute (newer tkinter)
            elif hasattr(event, 'deltaY'):
                scroll_amount = -1 * (event.deltaY // 120)
                if scroll_amount == 0:
                    scroll_amount = -1 if event.deltaY > 0 else 1

            if scroll_amount != 0:
                canvas.yview_scroll(int(scroll_amount), "units")

            return "break"  # Prevent event propagation

        def bind_mousewheel(widget):
            """Bind mouse wheel events to a widget."""
            widget.bind("<MouseWheel>", on_mousewheel)
            widget.bind("<Button-4>", on_mousewheel)
            widget.bind("<Button-5>", on_mousewheel)
            # Also try binding to children
            for child in widget.winfo_children():
                try:
                    bind_mousewheel(child)
                except:
                    pass

        scrollable_frame.bind("<Configure>", on_frame_configure)
        canvas.bind("<Configure>", on_canvas_configure)

        # Bind mouse wheel events for scrolling (two-finger scroll support)
        # Use add='+' to avoid overwriting existing bindings
        # Bind to canvas
        canvas.bind("<MouseWheel>", on_mousewheel, add='+')
        canvas.bind("<Button-4>", on_mousewheel, add='+')
        canvas.bind("<Button-5>", on_mousewheel, add='+')

        # Bind to scrollable frame
        scrollable_frame.bind("<MouseWheel>", on_mousewheel, add='+')
        scrollable_frame.bind("<Button-4>", on_mousewheel, add='+')
        scrollable_frame.bind("<Button-5>", on_mousewheel, add='+')

        # Bind to parent frame
        self.functions_frame.bind("<MouseWheel>", on_mousewheel, add='+')
        self.functions_frame.bind("<Button-4>", on_mousewheel, add='+')
        self.functions_frame.bind("<Button-5>", on_mousewheel, add='+')

        # Bind to notebook (only when functions tab is selected)
        def notebook_mousewheel(event):
            if self.notebook.index(self.notebook.select()) == 1:
                return on_mousewheel(event)

        self.notebook.bind("<MouseWheel>", notebook_mousewheel, add='+')
        self.notebook.bind("<Button-4>", notebook_mousewheel, add='+')
        self.notebook.bind("<Button-5>", notebook_mousewheel, add='+')

        # Bind to root window for comprehensive trackpad support (macOS)
        root = self.root
        root.bind_all(
            "<MouseWheel>",
            lambda e: on_mousewheel(e)
            if self.notebook.index(self.notebook.select()) == 1 else None,
            add='+')
        root.bind_all(
            "<Button-4>",
            lambda e: on_mousewheel(e)
            if self.notebook.index(self.notebook.select()) == 1 else None,
            add='+')
        root.bind_all(
            "<Button-5>",
            lambda e: on_mousewheel(e)
            if self.notebook.index(self.notebook.select()) == 1 else None,
            add='+')

        canvas_window = canvas.create_window((0, 0),
                                             window=scrollable_frame,
                                             anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Enable focus for keyboard scrolling
        canvas.focus_set()

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.functions_frame_inner = scrollable_frame
        self.functions_canvas = canvas

        # Update bindings when frame is updated
        def update_bindings():
            """Update mouse wheel bindings for all widgets in scrollable frame."""
            bind_mousewheel(scrollable_frame)

        # Store update function for later use
        self.update_scroll_bindings = update_bindings

    def load_data(self):
        """Load Z21 file data."""
        self.status_label.config(text="Loading data...")
        self.root.update()

        try:
            self.parser = Z21Parser(self.z21_file)
            self.z21_data = self.parser.parse()

            self.populate_list()
            self.status_label.config(
                text=f"Loaded {len(self.z21_data.locomotives)} locomotives")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load file:\n{e}")
            self.status_label.config(text="Error loading file")

    def populate_list(self, filter_text: str = ""):
        """Populate the locomotive list."""
        if not self.z21_data:
            return

        self.loco_listbox.delete(0, tk.END)
        self.filtered_locos = []

        filter_lower = filter_text.lower()

        for loco in self.z21_data.locomotives:
            display_text = f"Address {loco.address:4d} - {loco.name}"

            if not filter_text or filter_lower in display_text.lower():
                self.loco_listbox.insert(tk.END, display_text)
                self.filtered_locos.append(loco)

    def on_search(self, *args):
        """Handle search text change."""
        filter_text = self.search_var.get()
        self.populate_list(filter_text)

    def on_loco_select(self, event):
        """Handle locomotive selection."""
        selection = self.loco_listbox.curselection()
        if not selection:
            return

        index = selection[0]
        if index < len(self.filtered_locos):
            self.current_loco = self.filtered_locos[index]
            # Store original address for database lookup (in case user changes it)
            self.original_loco_address = self.current_loco.address
            # Find the locomotive index in z21_data.locomotives
            self.current_loco_index = None
            if self.z21_data:
                for i, loco in enumerate(self.z21_data.locomotives):
                    if loco.address == self.current_loco.address and loco.name == self.current_loco.name:
                        self.current_loco_index = i
                        break
            self.update_details()

    def update_details(self):
        """Update the details display."""
        if not self.current_loco:
            return

        self.update_overview()
        self.update_functions()

    def update_overview(self):
        """Update overview tab."""
        loco = self.current_loco

        # Update editable fields
        self.name_var.set(loco.name)
        self.address_var.set(str(loco.address))
        self.speed_var.set(str(loco.speed))
        self.direction_var.set('Forward' if loco.direction else 'Reverse')

        # Update scrollable text area with function summary and CV values
        self.overview_text.config(state=tk.NORMAL)
        self.overview_text.delete(1.0, tk.END)

        text = f"""
{'='*70}
FUNCTION SUMMARY
{'='*70}

Functions:         {len(loco.functions)} configured
Function Details:  {len(loco.function_details)} available

"""

        if loco.function_details:
            # List functions by function number order
            sorted_funcs = sorted(loco.function_details.items(),
                                  key=lambda x: x[1].function_number)

            text += "\n"
            for func_num, func_info in sorted_funcs:
                shortcut = f" [{func_info.shortcut}]" if func_info.shortcut else ""
                time_str = f" (time: {func_info.time}s)" if func_info.time != "0" else ""
                btn_type = func_info.button_type_name()
                text += f"  F{func_num:<3} - {func_info.image_name:<25} [{btn_type}] {shortcut}{time_str}\n"
            text += "\n"
        elif loco.functions:
            func_nums = sorted(loco.functions.keys())
            text += f"Function numbers: {', '.join(f'F{f}' for f in func_nums)}\n"

        if loco.cvs:
            text += f"\n{'='*70}\nCV VALUES\n{'='*70}\n"
            for cv_num, cv_value in sorted(loco.cvs.items()):
                text += f"CV{cv_num:3d} = {cv_value}\n"
        else:
            text += "\nNo CV values configured.\n"

        self.overview_text.insert(1.0, text)
        self.overview_text.config(state=tk.DISABLED)

    def save_locomotive_changes(self):
        """Save changes to locomotive details."""
        if not self.current_loco or not self.z21_data or not self.parser:
            messagebox.showerror("Error",
                                 "No locomotive selected or data not loaded.")
            return

        try:
            # Update locomotive object with new values
            new_name = self.name_var.get()
            new_address = int(self.address_var.get())
            new_speed = int(self.speed_var.get())
            new_direction = (self.direction_var.get() == 'Forward')

            # Update the locomotive in z21_data
            if self.current_loco_index is not None:
                loco = self.z21_data.locomotives[self.current_loco_index]
                loco.name = new_name
                loco.address = new_address
                loco.speed = new_speed
                loco.direction = new_direction

                # Also update current_loco reference
                self.current_loco.name = new_name
                self.current_loco.address = new_address
                self.current_loco.speed = new_speed
                self.current_loco.direction = new_direction
            else:
                messagebox.showerror(
                    "Error", "Could not find locomotive in data structure.")
                return

            # Write changes back to file
            try:
                self.parser.write(self.z21_data, self.z21_file)
                messagebox.showinfo(
                    "Success",
                    "Locomotive details saved successfully to file!")
            except Exception as write_error:
                messagebox.showerror(
                    "Write Error",
                    f"Failed to write changes to file: {write_error}\n\n"
                    f"Changes have been saved in memory but not written to disk."
                )

            # Update the listbox to reflect name change
            self.populate_list(
                self.search_var.get() if hasattr(self, 'search_var') else "")

        except ValueError as e:
            messagebox.showerror(
                "Error",
                f"Invalid input: {e}\n\nPlease enter valid numbers for Address and Max Speed."
            )
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save changes: {e}")

    def update_functions(self):
        """Update functions tab."""
        loco = self.current_loco

        # Clear existing widgets
        for widget in self.functions_frame_inner.winfo_children():
            widget.destroy()

        if not loco.function_details:
            ttk.Label(self.functions_frame_inner,
                      text="No function details available",
                      font=('Arial', 12)).pack(pady=20)
            return

        # Rebind mouse wheel events after clearing widgets
        if hasattr(self, 'update_scroll_bindings'):
            self.update_scroll_bindings()

        # Ensure canvas has focus for scrolling
        self.functions_canvas.focus_set()

        # Sort functions by function number
        sorted_funcs = sorted(loco.function_details.items(),
                              key=lambda x: x[1].function_number)

        # Calculate grid layout based on available width
        # Each card is approximately 100 pixels wide (80 icon + padding)
        # Calculate columns based on canvas width
        self.functions_canvas.update_idletasks()  # Update to get actual width
        canvas_width = self.functions_canvas.winfo_width()
        if canvas_width < 100:
            canvas_width = 800  # Default width if not yet rendered

        card_width = 100  # Fixed card width (matches CARD_WIDTH in create_function_card)
        cols = max(1, (canvas_width - 40) //
                   card_width)  # Account for scrollbar and padding

        # Row 0: Title
        header_label = ttk.Label(self.functions_frame_inner,
                                 text=f"Functions for {loco.name}",
                                 font=('Arial', 14, 'bold'))
        header_label.grid(row=0,
                          column=0,
                          columnspan=cols,
                          sticky='ew',
                          padx=5,
                          pady=(10, 5))

        # Row 1: "Add New Function" and "Save Changes" buttons
        button_frame = ttk.Frame(self.functions_frame_inner)
        button_frame.grid(row=1,
                          column=0,
                          columnspan=cols,
                          sticky='ew',
                          padx=5,
                          pady=(0, 10))

        add_button = ttk.Button(button_frame,
                                text="+ Add New Function",
                                command=self.add_new_function)
        add_button.pack(side=tk.LEFT, padx=(0, 10))

        save_button = ttk.Button(button_frame,
                                 text="💾 Save Changes",
                                 command=self.save_function_changes)
        save_button.pack(side=tk.LEFT)

        # Create function cards in a grid layout
        row = 2  # Start after title and button
        col = 0

        for func_num, func_info in sorted_funcs:
            card_frame = self.create_function_card(func_num, func_info)

            # Make card and all children clickable to edit function
            def make_clickable(widget, fn, fi):
                widget.bind("<Button-1>",
                            lambda e, fnum=fn, finfo=fi: self.edit_function(
                                fnum, finfo))
                widget.bind("<Enter>",
                            lambda e: e.widget.config(cursor="hand2"))
                widget.bind("<Leave>", lambda e: e.widget.config(cursor=""))
                for child in widget.winfo_children():
                    make_clickable(child, fn, fi)

            make_clickable(card_frame, func_num, func_info)

            # Place in grid
            card_frame.grid(row=row, column=col, padx=5, pady=5, sticky='nw')

            col += 1
            if col >= cols:
                col = 0
                row += 1

        # Configure grid columns to be equal width
        for i in range(cols):
            self.functions_frame_inner.grid_columnconfigure(i,
                                                            weight=0,
                                                            uniform='card')

    def save_function_changes(self):
        """Save all function changes to the Z21 file."""
        if not self.current_loco or not self.z21_data or not self.parser:
            messagebox.showerror("Error",
                                 "No locomotive selected or data not loaded.")
            return

        try:
            # Ensure locomotive is updated in z21_data
            if self.current_loco_index is not None:
                self.z21_data.locomotives[
                    self.current_loco_index] = self.current_loco

            # Write changes back to file
            self.parser.write(self.z21_data, self.z21_file)
            messagebox.showinfo(
                "Success", "All function changes saved successfully to file!")
        except Exception as write_error:
            messagebox.showerror(
                "Write Error",
                f"Failed to write changes to file: {write_error}\n\n"
                f"Changes have been saved in memory but not written to disk.")

    def get_next_unused_function_number(self):
        """Get the next unused function number for the current locomotive."""
        if not self.current_loco:
            return 0

        used_numbers = set(self.current_loco.function_details.keys())
        # Start from 0 and find first unused
        for i in range(128):  # DCC functions typically go up to F127
            if i not in used_numbers:
                return i
        return 128  # Fallback if all are used

    def get_available_icons(self):
        """Get list of available icon names from icon mapping."""
        icon_names = sorted(self.icon_mapping.keys())
        # Also add common icon names that might not be in mapping
        common_icons = [
            'light', 'bell', 'horn_two_sound', 'steam', 'whistle_long',
            'whistle_short', 'neutral', 'sound1', 'sound2', 'sound3', 'sound4'
        ]
        for icon in common_icons:
            if icon not in icon_names:
                icon_names.append(icon)
        return sorted(set(icon_names))

    def add_new_function(self):
        """Open dialog to add a new function."""
        if not self.current_loco:
            messagebox.showwarning("No Locomotive",
                                   "Please select a locomotive first.")
            return

        # Create dialog window
        dialog = tk.Toplevel(self.root)
        dialog.title("Add New Function")
        dialog.transient(self.root)
        dialog.grab_set()

        # Variables
        icon_var = tk.StringVar()
        func_num_var = tk.StringVar(
            value=str(self.get_next_unused_function_number()))
        shortcut_var = tk.StringVar()
        button_type_var = tk.StringVar(value="switch")
        time_var = tk.StringVar(value="1.0")

        # Main container with padding
        main_frame = ttk.Frame(dialog, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Top section: Icon preview (larger, centered)
        preview_frame = ttk.Frame(main_frame)
        preview_frame.pack(fill=tk.X, pady=(0, 15))

        icon_preview_label = ttk.Label(preview_frame,
                                       background='white',
                                       relief=tk.SUNKEN,
                                       borderwidth=2)
        icon_preview_label.pack()

        def update_icon_preview(*args):
            """Update icon preview when selection changes."""
            icon_name = icon_var.get()
            if icon_name:
                preview_image = self.load_icon_image(icon_name, (80, 80))
                if preview_image:
                    icon_preview_label.config(image=preview_image)
                    icon_preview_label.image = preview_image  # Keep a reference
                else:
                    # Clear preview if icon not found
                    icon_preview_label.config(image='', width=80, height=80)
            else:
                icon_preview_label.config(image='', width=80, height=80)

        icon_var.trace('w', update_icon_preview)

        # Form fields in two columns for better space usage
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        # Left column
        left_col = ttk.Frame(form_frame)
        left_col.grid(row=0, column=0, padx=(0, 10), sticky='nsew')

        # Right column
        right_col = ttk.Frame(form_frame)
        right_col.grid(row=0, column=1, padx=(10, 0), sticky='nsew')

        form_frame.grid_columnconfigure(0, weight=1)
        form_frame.grid_columnconfigure(1, weight=1)
        form_frame.grid_rowconfigure(0, weight=1)

        # Left column fields
        row = 0

        # Icon selection
        ttk.Label(left_col, text="Icon:", width=12,
                  anchor='e').grid(row=row,
                                   column=0,
                                   padx=3,
                                   pady=4,
                                   sticky='e')
        icon_combo = ttk.Combobox(left_col,
                                  textvariable=icon_var,
                                  width=20,
                                  state='readonly')
        icon_combo['values'] = self.get_available_icons()
        if icon_combo['values']:
            icon_combo.current(0)
            update_icon_preview()  # Initial preview
        icon_combo.grid(row=row, column=1, padx=3, pady=4, sticky='ew')
        row += 1

        # Function number
        ttk.Label(left_col, text="Function #:", width=12,
                  anchor='e').grid(row=row,
                                   column=0,
                                   padx=3,
                                   pady=4,
                                   sticky='e')
        func_num_entry = ttk.Entry(left_col,
                                   textvariable=func_num_var,
                                   width=20)
        func_num_entry.grid(row=row, column=1, padx=3, pady=4, sticky='ew')
        row += 1

        # Right column fields
        row_right = 0

        # Shortcut
        ttk.Label(right_col, text="Shortcut:", width=12,
                  anchor='e').grid(row=row_right,
                                   column=0,
                                   padx=3,
                                   pady=4,
                                   sticky='e')
        shortcut_entry = ttk.Entry(right_col,
                                   textvariable=shortcut_var,
                                   width=20)
        shortcut_entry.grid(row=row_right,
                            column=1,
                            padx=3,
                            pady=4,
                            sticky='ew')
        row_right += 1

        # Button type
        ttk.Label(right_col, text="Button Type:", width=12,
                  anchor='e').grid(row=row_right,
                                   column=0,
                                   padx=3,
                                   pady=4,
                                   sticky='e')
        button_type_combo = ttk.Combobox(
            right_col,
            textvariable=button_type_var,
            values=['switch', 'push-button', 'time button'],
            state='readonly',
            width=17)
        button_type_combo.current(0)
        button_type_combo.grid(row=row_right,
                               column=1,
                               padx=3,
                               pady=4,
                               sticky='ew')
        row_right += 1

        # Time duration (only show for time button) - in right column
        time_label = ttk.Label(right_col,
                               text="Time (s):",
                               width=12,
                               anchor='e')
        time_entry = ttk.Entry(right_col, textvariable=time_var, width=20)

        def update_time_visibility(*args):
            """Show/hide time duration field based on button type."""
            if button_type_var.get() == 'time button':
                time_label.grid(row=row_right,
                                column=0,
                                padx=3,
                                pady=4,
                                sticky='e')
                time_entry.grid(row=row_right,
                                column=1,
                                padx=3,
                                pady=4,
                                sticky='ew')
            else:
                time_label.grid_remove()
                time_entry.grid_remove()

        button_type_var.trace('w', update_time_visibility)
        update_time_visibility()

        # Configure column weights
        left_col.grid_columnconfigure(1, weight=1)
        right_col.grid_columnconfigure(1, weight=1)

        # Buttons
        button_frame = ttk.Frame(main_frame, padding=(10, 15, 10, 10))
        button_frame.pack(fill=tk.X)

        # Calculate optimal window size
        dialog.update_idletasks()
        # Get natural size
        width = dialog.winfo_reqwidth()
        height = dialog.winfo_reqheight()
        # Set minimum size with some padding
        dialog.geometry(f"{max(480, width)}x{max(320, height)}")
        dialog.minsize(480, 320)

        def save_function():
            """Save the new function."""
            try:
                # Validate inputs
                icon_name = icon_var.get()
                if not icon_name:
                    messagebox.showerror("Error", "Please select an icon.")
                    return

                func_num = int(func_num_var.get())
                if func_num < 0 or func_num > 127:
                    messagebox.showerror(
                        "Error", "Function number must be between 0 and 127.")
                    return

                # Check if function number already exists
                if func_num in self.current_loco.function_details:
                    if not messagebox.askyesno(
                            "Overwrite?",
                            f"Function F{func_num} already exists. Overwrite it?"
                    ):
                        return

                shortcut = shortcut_var.get().strip()
                button_type_name = button_type_var.get()

                # Map button type name to integer
                button_type_map = {
                    'switch': 0,
                    'push-button': 1,
                    'time button': 2
                }
                button_type = button_type_map.get(button_type_name, 0)

                # Get time duration (only for time button, otherwise "0")
                if button_type == 2:  # time button
                    try:
                        time_value = float(time_var.get())
                        time_str = str(time_value)
                    except ValueError:
                        messagebox.showerror(
                            "Error", "Time duration must be a valid number.")
                        return
                else:
                    time_str = "0"

                # Find max position for ordering
                max_position = 0
                if self.current_loco.function_details:
                    max_position = max(
                        f.position
                        for f in self.current_loco.function_details.values())

                # Create new function info
                func_info = FunctionInfo(function_number=func_num,
                                         image_name=icon_name,
                                         shortcut=shortcut,
                                         position=max_position + 1,
                                         time=time_str,
                                         button_type=button_type,
                                         is_active=True)

                # Add to locomotive
                self.current_loco.function_details[func_num] = func_info
                self.current_loco.functions[func_num] = True

                # Update locomotive in z21_data
                if self.current_loco_index is not None:
                    self.z21_data.locomotives[
                        self.current_loco_index] = self.current_loco

                # Update display
                self.update_functions()

                # Close dialog
                dialog.destroy()

                messagebox.showinfo(
                    "Success", f"Function F{func_num} added successfully!")

            except ValueError as e:
                messagebox.showerror("Error", f"Invalid input: {e}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add function: {e}")

        ttk.Button(button_frame, text="Cancel",
                   command=dialog.destroy).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Add Function",
                   command=save_function).pack(side=tk.RIGHT, padx=5)

    def edit_function(self, func_num: int, func_info: FunctionInfo):
        """Open dialog to edit an existing function."""
        if not self.current_loco:
            messagebox.showwarning("No Locomotive",
                                   "Please select a locomotive first.")
            return

        # Create dialog window
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Edit Function F{func_num}")
        dialog.transient(self.root)
        dialog.grab_set()

        # Variables - pre-populate with existing values
        icon_var = tk.StringVar(value=func_info.image_name)
        func_num_var = tk.StringVar(value=str(func_num))
        shortcut_var = tk.StringVar(value=func_info.shortcut or "")
        button_type_map = {0: "switch", 1: "push-button", 2: "time button"}
        button_type_var = tk.StringVar(
            value=button_type_map.get(func_info.button_type, "switch"))
        time_var = tk.StringVar(
            value=func_info.time if func_info.time != "0" else "1.0")

        # Main container with padding
        main_frame = ttk.Frame(dialog, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Top section: Icon preview (larger, centered)
        preview_frame = ttk.Frame(main_frame)
        preview_frame.pack(fill=tk.X, pady=(0, 15))

        icon_preview_label = ttk.Label(preview_frame,
                                       background='white',
                                       relief=tk.SUNKEN,
                                       borderwidth=2)
        icon_preview_label.pack()

        def update_icon_preview(*args):
            """Update icon preview when selection changes."""
            icon_name = icon_var.get()
            if icon_name:
                preview_image = self.load_icon_image(icon_name, (80, 80))
                if preview_image:
                    icon_preview_label.config(image=preview_image)
                    icon_preview_label.image = preview_image  # Keep a reference
                else:
                    # Clear preview if icon not found
                    icon_preview_label.config(image='', width=80, height=80)
            else:
                icon_preview_label.config(image='', width=80, height=80)

        icon_var.trace('w', update_icon_preview)
        update_icon_preview()  # Initial preview

        # Form fields in two columns for better space usage
        form_frame = ttk.Frame(main_frame)
        form_frame.pack(fill=tk.BOTH, expand=True)

        # Left column
        left_col = ttk.Frame(form_frame)
        left_col.grid(row=0, column=0, padx=(0, 10), sticky='nsew')

        # Right column
        right_col = ttk.Frame(form_frame)
        right_col.grid(row=0, column=1, padx=(10, 0), sticky='nsew')

        form_frame.grid_columnconfigure(0, weight=1)
        form_frame.grid_columnconfigure(1, weight=1)
        form_frame.grid_rowconfigure(0, weight=1)

        # Left column fields
        row = 0

        # Icon selection
        ttk.Label(left_col, text="Icon:", width=12,
                  anchor='e').grid(row=row,
                                   column=0,
                                   padx=3,
                                   pady=4,
                                   sticky='e')
        icon_combo = ttk.Combobox(left_col,
                                  textvariable=icon_var,
                                  width=20,
                                  state='readonly')
        icon_combo['values'] = self.get_available_icons()
        # Set current selection
        available_icons = self.get_available_icons()
        if func_info.image_name in available_icons:
            icon_combo.current(available_icons.index(func_info.image_name))
        elif available_icons:
            icon_combo.current(0)
        icon_combo.grid(row=row, column=1, padx=3, pady=4, sticky='ew')
        row += 1

        # Function number
        ttk.Label(left_col, text="Function #:", width=12,
                  anchor='e').grid(row=row,
                                   column=0,
                                   padx=3,
                                   pady=4,
                                   sticky='e')
        func_num_entry = ttk.Entry(left_col,
                                   textvariable=func_num_var,
                                   width=20)
        func_num_entry.grid(row=row, column=1, padx=3, pady=4, sticky='ew')
        row += 1

        # Right column fields
        row_right = 0

        # Shortcut
        ttk.Label(right_col, text="Shortcut:", width=12,
                  anchor='e').grid(row=row_right,
                                   column=0,
                                   padx=3,
                                   pady=4,
                                   sticky='e')
        shortcut_entry = ttk.Entry(right_col,
                                   textvariable=shortcut_var,
                                   width=20)
        shortcut_entry.grid(row=row_right,
                            column=1,
                            padx=3,
                            pady=4,
                            sticky='ew')
        row_right += 1

        # Button type
        ttk.Label(right_col, text="Button Type:", width=12,
                  anchor='e').grid(row=row_right,
                                   column=0,
                                   padx=3,
                                   pady=4,
                                   sticky='e')
        button_type_combo = ttk.Combobox(
            right_col,
            textvariable=button_type_var,
            values=['switch', 'push-button', 'time button'],
            state='readonly',
            width=17)
        button_type_combo.current(['switch', 'push-button',
                                   'time button'].index(button_type_var.get()))
        button_type_combo.grid(row=row_right,
                               column=1,
                               padx=3,
                               pady=4,
                               sticky='ew')
        row_right += 1

        # Time duration (only show for time button) - in right column
        time_label = ttk.Label(right_col,
                               text="Time (s):",
                               width=12,
                               anchor='e')
        time_entry = ttk.Entry(right_col, textvariable=time_var, width=20)

        def update_time_visibility(*args):
            """Show/hide time duration field based on button type."""
            if button_type_var.get() == 'time button':
                time_label.grid(row=row_right,
                                column=0,
                                padx=3,
                                pady=4,
                                sticky='e')
                time_entry.grid(row=row_right,
                                column=1,
                                padx=3,
                                pady=4,
                                sticky='ew')
            else:
                time_label.grid_remove()
                time_entry.grid_remove()

        button_type_var.trace('w', update_time_visibility)
        update_time_visibility()

        # Configure column weights
        left_col.grid_columnconfigure(1, weight=1)
        right_col.grid_columnconfigure(1, weight=1)

        # Buttons
        button_frame = ttk.Frame(main_frame, padding=(10, 15, 10, 10))
        button_frame.pack(fill=tk.X)

        def save_changes():
            """Save the edited function."""
            try:
                # Validate inputs
                icon_name = icon_var.get()
                if not icon_name:
                    messagebox.showerror("Error", "Please select an icon.")
                    return

                new_func_num = int(func_num_var.get())
                if new_func_num < 0 or new_func_num > 127:
                    messagebox.showerror(
                        "Error", "Function number must be between 0 and 127.")
                    return

                shortcut = shortcut_var.get().strip()
                button_type_name = button_type_var.get()

                # Map button type name to integer
                button_type_map = {
                    'switch': 0,
                    'push-button': 1,
                    'time button': 2
                }
                button_type = button_type_map.get(button_type_name, 0)

                # Get time duration (only for time button, otherwise "0")
                if button_type == 2:  # time button
                    try:
                        time_value = float(time_var.get())
                        time_str = str(time_value)
                    except ValueError:
                        messagebox.showerror(
                            "Error", "Time duration must be a valid number.")
                        return
                else:
                    time_str = "0"

                # If function number changed, check for conflicts
                if new_func_num != func_num and new_func_num in self.current_loco.function_details:
                    if not messagebox.askyesno(
                            "Overwrite?",
                            f"Function F{new_func_num} already exists. Overwrite it?"
                    ):
                        return
                    # Remove old function number entry
                    if new_func_num != func_num:
                        del self.current_loco.function_details[func_num]
                        del self.current_loco.functions[func_num]

                # Update function info
                func_info.image_name = icon_name
                func_info.function_number = new_func_num
                func_info.shortcut = shortcut
                func_info.button_type = button_type
                func_info.time = time_str

                # Update locomotive dictionaries
                if new_func_num != func_num:
                    # Function number changed, need to update dictionaries
                    self.current_loco.function_details[
                        new_func_num] = func_info
                    self.current_loco.functions[new_func_num] = True
                else:
                    # Same function number, just update the existing entry
                    self.current_loco.function_details[func_num] = func_info

                # Update locomotive in z21_data
                if self.current_loco_index is not None:
                    self.z21_data.locomotives[
                        self.current_loco_index] = self.current_loco

                # Update display
                self.update_functions()

                # Close dialog
                dialog.destroy()

                messagebox.showinfo(
                    "Success",
                    f"Function F{new_func_num} updated successfully!")

            except ValueError as e:
                messagebox.showerror("Error", f"Invalid input: {e}")
            except Exception as e:
                messagebox.showerror("Error",
                                     f"Failed to update function: {e}")

        ttk.Button(button_frame, text="Cancel",
                   command=dialog.destroy).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Save Changes",
                   command=save_changes).pack(side=tk.RIGHT, padx=5)

        # Calculate optimal window size
        dialog.update_idletasks()
        # Get natural size
        width = dialog.winfo_reqwidth()
        height = dialog.winfo_reqheight()
        # Set minimum size with some padding
        dialog.geometry(f"{max(480, width)}x{max(320, height)}")
        dialog.minsize(480, 320)

    def load_icon_image(self, icon_name: str = None, size: tuple = (80, 80)):
        """Load icon image with black foreground and white background."""
        project_root = Path(__file__).parent.parent
        icons_dir = project_root / "icons"

        def convert_to_black(img):
            """Convert icon to deep blue color on white background.
            White foreground icons become deep blue, dark foreground icons become black.
            """
            if not HAS_PIL:
                return img

            # Convert to RGBA if needed
            if img.mode != 'RGBA':
                img = img.convert('RGBA')

            original_pixels = img.load()

            # Convert to grayscale to detect foreground vs background
            gray = img.convert('L')
            gray_pixels = gray.load()

            # Detect if icon is white foreground by checking average intensity
            total_intensity = 0
            pixel_count = 0
            for x in range(img.size[0]):
                for y in range(img.size[1]):
                    alpha = original_pixels[x, y][3]
                    if alpha >= 30:  # Any visible pixel
                        total_intensity += gray_pixels[x, y]
                        pixel_count += 1

            # If average intensity > 140, likely white foreground - convert to deep blue
            avg_intensity = total_intensity / pixel_count if pixel_count > 0 else 128
            is_white_foreground = avg_intensity > 140

            # Deep blue color: RGB(0, 82, 204) or similar
            DEEP_BLUE = (0, 82, 204)

            # Create colored version
            colored_img = Image.new('RGBA', img.size)
            colored_pixels = colored_img.load()

            # Convert: preserve shape (alpha), convert color
            for x in range(img.size[0]):
                for y in range(img.size[1]):
                    r, g, b, alpha = original_pixels[x, y]
                    intensity = gray_pixels[x, y]

                    # Skip fully transparent pixels
                    if alpha < 5:
                        colored_pixels[x, y] = (0, 0, 0, 0)
                        continue

                    if is_white_foreground:
                        # White foreground icon: bright areas are the icon shape
                        # Convert to deep blue with high opacity
                        # Use intensity to determine opacity (bright = more opaque)
                        opacity = int(255 * (intensity / 255.0))
                        # Ensure minimum opacity for visibility
                        if opacity > 20:  # Any visible brightness
                            opacity = max(200, opacity)  # Make it very opaque
                            colored_pixels[x, y] = (*DEEP_BLUE, opacity)
                        else:
                            colored_pixels[x, y] = (0, 0, 0, 0)
                    else:
                        # Dark foreground icon: dark areas are the icon shape
                        # Convert to black with opacity based on how dark
                        opacity = int(255 * ((255 - intensity) / 255.0))
                        # Ensure minimum opacity for visibility
                        if opacity > 20:  # Any visible darkness
                            opacity = max(200, opacity)  # Make it very opaque
                            colored_pixels[x, y] = (0, 0, 0, opacity)
                        else:
                            colored_pixels[x, y] = (0, 0, 0, 0)

            return colored_img

        if icon_name:
            # First, try to use mapping file
            if icon_name in self.icon_mapping:
                mapped_file = self.icon_mapping[icon_name]
                icon_path = Path(mapped_file.get('path', ''))
                if icon_path.exists():
                    try:
                        if HAS_PIL:
                            img = Image.open(icon_path)
                            if img.mode != 'RGBA':
                                img = img.convert('RGBA')

                            # Convert to black color
                            img = convert_to_black(img)

                            # Create white background
                            white_bg = Image.new('RGB', size, color='white')

                            # Resize icon
                            icon_resized = img.resize(size, Image.LANCZOS)

                            # Paste icon on white background
                            if icon_resized.mode == 'RGBA':
                                white_bg.paste(icon_resized, (0, 0),
                                               icon_resized)
                            else:
                                white_bg.paste(icon_resized, (0, 0))

                            return ImageTk.PhotoImage(white_bg)
                    except Exception as e:
                        # Debug: print error (can be removed later)
                        print(
                            f"Error loading icon from mapping ({icon_name}): {e}"
                        )
                        pass

            # Fallback: Try multiple naming patterns for icons directory
            icon_patterns = [
                f"{icon_name}_normal.png",  # light_normal.png
                f"{icon_name}_Normal.png",  # light_Normal.png (actual pattern)
                f"{icon_name}.png",  # light.png
            ]

            for pattern in icon_patterns:
                icon_path = icons_dir / pattern
                if icon_path.exists():
                    try:
                        if HAS_PIL:
                            img = Image.open(icon_path)
                            # Convert to RGBA if needed
                            if img.mode != 'RGBA':
                                img = img.convert('RGBA')

                            # Convert to black color
                            img = convert_to_black(img)

                            # Create white background
                            white_bg = Image.new('RGB', size, color='white')

                            # Resize icon
                            icon_resized = img.resize(size, Image.LANCZOS)

                            # Paste icon on white background
                            if icon_resized.mode == 'RGBA':
                                white_bg.paste(icon_resized, (0, 0),
                                               icon_resized)
                            else:
                                white_bg.paste(icon_resized, (0, 0))

                            return ImageTk.PhotoImage(white_bg)
                    except Exception as e:
                        # Debug: print error (can be removed later)
                        print(
                            f"Error loading icon pattern {pattern} ({icon_name}): {e}"
                        )
                        continue

            # Try to load specific icon from extracted icons
            icon_path = project_root / "extracted_icons" / "icons_by_name" / icon_name / f"{icon_name}.png"
            if icon_path.exists():
                try:
                    if HAS_PIL:
                        img = Image.open(icon_path)
                        if img.mode != 'RGBA':
                            img = img.convert('RGBA')

                        # Convert to black color
                        img = convert_to_black(img)

                        white_bg = Image.new('RGB', size, color='white')
                        icon_resized = img.resize(size, Image.LANCZOS)

                        if icon_resized.mode == 'RGBA':
                            white_bg.paste(icon_resized, (0, 0), icon_resized)
                        else:
                            white_bg.paste(icon_resized, (0, 0))

                        return ImageTk.PhotoImage(white_bg)
                except Exception as e:
                    # Debug: print error (can be removed later)
                    print(
                        f"Error loading icon from extracted_icons ({icon_name}): {e}"
                    )
                    pass

        # Use default icon (neutrals_normal.png) with black color
        if self.default_icon_path.exists():
            try:
                if HAS_PIL:
                    img = Image.open(self.default_icon_path)
                    if img.mode != 'RGBA':
                        img = img.convert('RGBA')

                    # Convert to black color
                    img = convert_to_black(img)

                    white_bg = Image.new('RGB', size, color='white')
                    icon_resized = img.resize(size, Image.LANCZOS)

                    if icon_resized.mode == 'RGBA':
                        white_bg.paste(icon_resized, (0, 0), icon_resized)
                    else:
                        white_bg.paste(icon_resized, (0, 0))

                    return ImageTk.PhotoImage(white_bg)
            except Exception as e:
                # Debug: print error (can be removed later)
                print(f"Error loading default icon ({icon_name}): {e}")
                pass

        # Fallback: create a white square with black border
        if HAS_PIL:
            img = Image.new('RGB', size, color='white')
            return ImageTk.PhotoImage(img)

        return None

    def create_function_card(self, func_num: int, func_info):
        """Create a card widget for a function with consistent sizing and alignment."""
        # Fixed card dimensions for consistent alignment
        CARD_WIDTH = 100
        ICON_SIZE = 80
        CARD_PADDING = 5

        # Create card frame with fixed width
        card_frame = tk.Frame(self.functions_frame_inner,
                              relief=tk.RAISED,
                              borderwidth=2,
                              bg='white',
                              width=CARD_WIDTH)
        card_frame.pack_propagate(False)  # Prevent frame from resizing
        # Note: Don't pack here, will be placed in grid by caller

        # Use grid layout for precise alignment
        # Row 0: Icon (centered)
        icon_frame = tk.Frame(card_frame,
                              width=ICON_SIZE,
                              height=ICON_SIZE,
                              bg='white')
        icon_frame.grid(row=0,
                        column=0,
                        padx=CARD_PADDING,
                        pady=(CARD_PADDING, 2),
                        sticky='')
        icon_frame.pack_propagate(False)

        # Load and display icon with black color on white background
        icon_image = self.load_icon_image(func_info.image_name,
                                          (ICON_SIZE, ICON_SIZE))
        if icon_image:
            icon_label = tk.Label(icon_frame, image=icon_image, bg='white')
            icon_label.image = icon_image  # Keep a reference
            icon_label.pack(expand=True)
        else:
            # Fallback: show a visible placeholder with icon name
            # Create a canvas to draw a border and text
            fallback_canvas = tk.Canvas(icon_frame,
                                        width=ICON_SIZE,
                                        height=ICON_SIZE,
                                        bg='white',
                                        highlightthickness=0)
            fallback_canvas.pack(fill=tk.BOTH, expand=True)
            # Draw a black border rectangle
            fallback_canvas.create_rectangle(5,
                                             5,
                                             ICON_SIZE - 5,
                                             ICON_SIZE - 5,
                                             outline='#000000',
                                             width=2)
            # Draw icon name text (truncated if too long)
            icon_name_short = func_info.image_name[:
                                                   8] if func_info.image_name else "?"
            fallback_canvas.create_text(ICON_SIZE // 2,
                                        ICON_SIZE // 2,
                                        text=icon_name_short,
                                        fill='#666666',
                                        font=('Arial', 8))

        # Row 1: Function number (always present, centered)
        func_num_label = tk.Label(
            card_frame,
            text=f"F{func_num}",
            font=('Arial', 11, 'bold'),
            bg='white',
            fg='#333333'  # Dark gray
        )
        func_num_label.grid(row=1, column=0, pady=(0, 2), sticky='')

        # Row 2: Shortcut (always present, show placeholder if empty, centered)
        shortcut_text = func_info.shortcut if func_info.shortcut else "—"
        shortcut_label = tk.Label(
            card_frame,
            text=shortcut_text,
            font=('Arial', 9, 'bold'),
            bg='white',
            fg='#0066CC' if func_info.shortcut else '#CCCCCC')
        shortcut_label.grid(row=2, column=0, pady=(0, 2), sticky='')

        # Row 3: Button type and duration on the same line (always present, centered)
        button_type_colors = {
            'switch': '#4CAF50',
            'push-button': '#FF9800',
            'time button': '#2196F3'
        }
        btn_color = button_type_colors.get(func_info.button_type_name(),
                                           '#666666')

        # Create a frame to hold button type and time on the same line
        type_time_frame = tk.Frame(card_frame, bg='white')
        type_time_frame.grid(row=3,
                             column=0,
                             pady=(0, CARD_PADDING),
                             sticky='')

        # Button type
        button_type_label = tk.Label(type_time_frame,
                                     text=func_info.button_type_name(),
                                     font=('Arial', 8),
                                     bg='white',
                                     fg=btn_color)
        button_type_label.pack(side=tk.LEFT)

        # Time indicator (if available)
        if func_info.time and func_info.time != "0":
            time_label = tk.Label(type_time_frame,
                                  text=f" ⏱ {func_info.time}s",
                                  font=('Arial', 7),
                                  bg='white',
                                  fg='#666666')
            time_label.pack(side=tk.LEFT)

        # Configure column to center all elements
        card_frame.grid_columnconfigure(0, weight=1)

        return card_frame  # Return card frame for grid placement


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Z21 Locomotive Browser GUI')
    parser.add_argument('file',
                        type=Path,
                        nargs='?',
                        default=Path('z21_new.z21'),
                        help='Z21 file to open (default: z21_new.z21)')

    args = parser.parse_args()

    if not args.file.exists():
        print(f"Error: File not found: {args.file}")
        print(f"Usage: {sys.argv[0]} <z21_file>")
        sys.exit(1)

    # Suppress macOS TSM warning messages
    import os
    os.environ['PYTHONUNBUFFERED'] = '1'
    # Redirect stderr to suppress TSM messages on macOS
    if sys.platform == 'darwin':
        # Save original stderr
        original_stderr = sys.stderr

        # Create a filter that removes TSM messages
        class TSMFilter:

            def __init__(self, original):
                self.original = original

            def write(self, text):
                if 'TSM AdjustCapsLockLED' not in text and 'TSM' not in text:
                    self.original.write(text)

            def flush(self):
                self.original.flush()

        sys.stderr = TSMFilter(original_stderr)

    root = tk.Tk()
    app = Z21GUI(root, args.file)
    root.mainloop()


if __name__ == '__main__':
    main()
