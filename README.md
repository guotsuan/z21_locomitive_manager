# Z21 Locomotive Manager

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![macOS](https://img.shields.io/badge/macOS-Continuity%20Camera-000000?logo=apple&logoColor=white)](https://www.apple.com/macos/)
[![License: BSD 3-Clause](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](#-license)

A macOS-friendly Python GUI and CLI for managing Roco Z21 locomotive files,
DCC function mappings, icons, OCR scanning, and Z21 App import/export.

Built for Roco Z21, model railway, model train, locomotive, DCC, train control,
macOS, CustomTkinter, OCR, Continuity Camera, and AirDrop workflows.

## About

Roco locomotives can usually be added to the Z21 App from its online database,
but models from other manufacturers often require locomotive details and DCC
function mappings to be entered manually. Z21 Locomotive Manager makes that
work practical on a computer.

The application reads, validates, edits, and writes `.z21` archives while
preserving their SQLite data and unknown archive members. Its graphical browser
supports locomotive details, function icons, OCR-assisted manual scanning, and
individual `.z21loco` import/export. A CLI is included for inspection and data
export. On macOS, completed locomotives can be shared back to the Z21 App with
AirDrop.

## ✨ Features

- **Z21 Management**: Read, edit, validate, and safely write Z21 locomotive
  archives while preserving unknown archive members and SQLite data.
- **GUI Browser**: Search locomotives, edit overview fields, manage function
  cards, and import or export individual locomotives. The main window moves to
  the foreground once startup finishes.
- **iPhone Document Capture**: Import a manual with Continuity Camera by scanning a document, taking a photo, or choosing an existing image.
- **Native OCR**: Apple Vision accurate text recognition with language correction,
  railway terminology, confidence scores, candidates, and page coordinates.
- **AI-assisted Fields**: Review evidence-backed DeepSeek suggestions before
  applying OCR-derived values to locomotive fields.
- **Function Table Scanner**: From the Functions tab, scan a manual table with
  iPhone Continuity Camera, reconstruct F0–F32 rows with DeepSeek, and review
  locally matched Z21 icons before applying them. Every PNG in `icons/` is
  discovered automatically. Function shortcuts are derived primarily from the
  scanned table description (5–8 characters), not the icon name; the icon's
  standard label is only a fallback when the description is missing. When no
  icon matches, the description may be condensed to as many as 10 characters.
- **Controlled Categories**: Prefer `Electrical`, `Steam`, `Diesel`, or
  `Train Bus`; custom types require explicit evidence and manual review.


## Quick Start

The recommended setup uses [uv](https://docs.astral.sh/uv/):

```bash
git clone https://github.com/guotsuan/z21_locomotive_manager.git
cd z21_locomotive_manager
uv sync
uv run python tools/z21lm_gui.py z21_new.z21
```

To inspect the command-line interface:

```bash
uv run z21lm --help
```

## 📋 Requirements

- Python 3.10 or higher
- customtkinter>=5.0.0
- Pillow>=9.0.0  
- pytesseract>=0.3.10
- pdf2image>=1.16.3
- pyobjc-framework-Cocoa>=9.0.0,<12.0.0
- Xcode Command Line Tools (macOS, used to build the Continuity Camera helper)

## 🚀 Usage

Install all locked dependencies with uv:

```bash
uv sync
```

To use a specific Python interpreter:

```bash
uv sync --python /path/to/python3
```

Alternatively, install from `requirements.txt` with pip:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Launch the graphical interface:

```bash
# Open the included example archive
uv run python tools/z21lm_gui.py
uv run python tools/z21lm_gui.py z21_new.z21

# Open another Z21 archive
uv run python tools/z21lm_gui.py /path/to/rocoData.z21
```

Use the command-line parser:

```bash
uv run z21lm --help
uv run z21lm read z21_new.z21
uv run z21lm export z21_new.z21 output.json
```

### GUI Features

- Search locomotives by name or address
- View detailed locomotive information
- Browse function mappings with icons
- Two-tab interface: Overview and Functions
- Import from Photo with iPhone document scan, iPhone photo, and local-file fallback
- Scan a function table directly from the Functions tab

On macOS, **Import from Photo** opens Apple's system-generated Continuity
Camera menu. Select the nearby iPhone and then choose **Scan Documents** or
**Take Photo**. Apple requires this final selection to happen in its system
menu; the captured PDF or image is returned to the locomotive OCR workflow.
On macOS, OCR prefers Apple Vision with automatic language detection and the
priority order German, English, then French. Tesseract remains a fallback on
other platforms or when the native helper is unavailable.

Use the **Settings** button to save a DeepSeek API key in macOS Keychain. After
OCR, choose **Analyze with DeepSeek** to send only the editable OCR text for
field extraction. Suggestions include confidence and source evidence; existing
field values are not selected for replacement by default, and nothing is saved
to the Z21 archive until **Save Changes** is clicked.

### Scanning a function table

1. Select a locomotive and open the **Functions** tab.
2. Click **Scan from iphone** and scan the manual page containing the function
   table. A document scan is preferable to a normal photo because iPhone
   corrects paper edges and perspective.
3. Apple Vision extracts text and bounding boxes locally. DeepSeek receives the
   OCR layout—not the captured image—and reconstructs the F-key rows.
4. Review the detected F number, table description, matched icon, button type,
   and confidence. Existing F keys are unchecked to prevent accidental
   replacement.
5. Click **Apply Selected**, then **Save Changes** to persist the functions.

The scanner sorts and deduplicates rows numerically before applying them, so a
multi-column OCR order such as `F0, F14, F1, F15` becomes `F0, F1, …, F15`.
Internal gaps are highlighted for review but never filled without OCR evidence.
After applying, card positions are normalized into ascending F-number order.

All PNG files under `icons/` are discovered automatically. Icon selection uses
the F number plus multilingual English, German, and French descriptions, with
specific phrases taking precedence over generic words. Repeated Cabin 1/2
light pairs use `light`/`light2` for the first pair and
`cockpit_light_left`/`cockpit_light_right` for the second pair. Shortcuts are
derived from the table description: matched icons use 5–8 characters, while an
unmatched description may use up to 10 characters. The icon name is only a
fallback when the description is missing.

The DeepSeek integration uses JSON Output with `deepseek-v4-flash`. API keys
are stored in macOS Keychain and are never included in prompts. This application
does not perform web enrichment or internet searches for locomotive fields.

The **Categories** field is an editable controlled list. Prefer exactly one of
`Electrical`, `Steam`, `Diesel`, or `Train Bus`. A genuinely different vehicle
type may use a short English Title Case name such as `Battery Electric`; custom
AI suggestions are deliberately low-confidence and require manual selection.


## 📁 Project Structure

```
z21_locomotive_manager/
├── README.md                    # This file
├── pyproject.toml               # uv/Python project configuration
├── uv.lock                      # uv lockfile for reproducible installs
├── requirements.txt             # Python dependencies
├── icon_mapping.json            # Icon name mappings for function icons
├── src/                         # Core source code
│   ├── __init__.py
│   ├── archive.py               # ZIP discovery, validation, and atomic writes
│   ├── binary_reader.py         # Binary file reading utilities
│   ├── ai_extraction.py         # DeepSeek structured proposals and validation
│   ├── cli.py                   # Command-line interface
│   ├── credential_store.py      # macOS Keychain-backed API key storage
│   ├── data_models.py           # Data structure definitions
│   ├── function_extraction.py   # Function-table parsing, icons, shortcuts
│   ├── native/                  # Packaged Swift/AppKit camera helper source
│   ├── native_build.py          # Shared native Swift helper build support
│   ├── ocr.py                   # Structured Apple Vision OCR and fallback
│   ├── parser.py                # Public format-orchestration facade
│   ├── photo_capture.py         # Python bridge for Continuity Camera
│   ├── schema.py                # SQLite column and model mappings
│   └── sqlite_repository.py     # SQLite read/write persistence
├── tools/                       # Utility scripts and GUI
│   ├── __init__.py
│   ├── z21lm_gui.py             # Main GUI browser application (customtkinter)
│   └── z21lm_gui_operations.py  # GUI operations mixin (import, export, etc.)
├── icons/                       # Locomotive function icons (PNG files)
│   └── *.png                    # Function icon images
├── *.z21                        # Z21 database files (ZIP archives)
└── *.z21loco                    # Individual locomotive files
```

### Architecture

The public `Z21Parser` API coordinates three independent layers:

1. `Z21Archive` discovers archive members and performs validated atomic writes.
2. `SQLiteZ21Repository` maps SQLite rows and relationships to domain models.
3. `schema.py` centralizes version-tolerant vehicle column mappings.

The CLI and GUI depend on the parser facade rather than ZIP or SQLite details.

### Format: SQLite (New Format)
- File: `Loco.sqlite` inside ZIP archive
- Example: `z21_new.z21`
- Successfully parsed: 65+ locomotives


## 🤝 Contributing

Contributions are welcome, especially improvements to Z21 format compatibility,
platform support, OCR accuracy, DCC function matching, validation, and tests.

1. Fork the repository and create a focused branch.
2. Install the development environment with `uv sync`.
3. Make the change and add or update tests.
4. Run the test suite:

   ```bash
   uv run pytest tests
   ```

5. Open a pull request describing the problem, the implementation, and the
   validation performed.

Please avoid committing personal `.z21` archives, API keys, generated OCR data,
or other private model-railway data.

## 📄 License

This project is licensed under the BSD 3-Clause License.

**Note**: This project is not affiliated with Roco or Z21. It is an independent
tool for managing Z21 locomotive data files.
