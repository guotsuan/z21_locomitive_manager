# Z21 Data File Reader/Writer Application Plan

## Overview
Application to read, parse, modify, and write `rocoData.z21` files - binary configuration files used by Roco's Z21 model train control system.

## File Format Analysis
- **Format**: ZIP archive containing XML and image files ✅ **DISCOVERED**
- **Structure**: 
  - `loco_data.xml`: XML file with locomotive and accessory data
  - Image files: PNG/JPG files for locomotives (`lok_*.png/jpg`), wagons (`wagon_*.jpg`), backgrounds
- **XML Schema**: 
  - Root: `<roco>` element
  - `<exportmeta>`: Source (iOS/Android) and version
  - `<locos>`: Container for locomotive elements
  - `<loco>`: Individual locomotive with address, name, functions, CVs, etc.
- **Status**: ✅ Parser implemented and working (23 locomotives successfully parsed)

## Application Architecture

### 1. Core Components

#### 1.1 Binary File Handler
- **Purpose**: Low-level binary I/O operations
- **Responsibilities**:
  - Read/write raw binary data
  - Handle byte order (little/big endian)
  - Memory-mapped file access for large files
  - Checksum/CRC validation

#### 1.2 File Parser
- **Purpose**: Interpret binary structure
- **Responsibilities**:
  - Identify file header/signature
  - Parse sections/chunks
  - Extract structured data (locomotives, accessories, etc.)
  - Handle unknown/unidentified data blocks

#### 1.3 Data Model
- **Purpose**: Represent Z21 data in memory
- **Components**:
  - `Z21File`: Root container
  - `Locomotive`: Locomotive data (address, name, functions, CVs)
  - `Accessory`: Turnout/signal/light data
  - `Layout`: Track layout configuration
  - `Settings`: System settings
  - `UnknownBlock`: Preserve unidentified data

#### 1.4 File Writer
- **Purpose**: Serialize data model back to binary
- **Responsibilities**:
  - Convert data model to binary format
  - Maintain original structure where possible
  - Preserve unknown blocks
  - Generate checksums/validation

### 2. Technology Stack Options

#### Option A: Python
- **Pros**: Good binary handling (`struct`, `bytearray`), rich libraries, easy to prototype
- **Libraries**: `struct`, `pathlib`, `argparse`/`click`, `dataclasses`
- **Good for**: Analysis, scripting, cross-platform

#### Option B: JavaScript/Node.js
- **Pros**: Web-friendly, can build browser-based viewer
- **Libraries**: `Buffer`, `fs`, `express` (if web app)
- **Good for**: Web application, browser-based tools

#### Option C: C/C++
- **Pros**: Direct binary manipulation, performance
- **Good for**: Native applications, performance-critical

#### Option D: Java
- **Pros**: Cross-platform, strong typing
- **Libraries**: `ByteBuffer`, `NIO`
- **Good for**: Enterprise applications

### 3. Development Phases

#### Phase 1: File Analysis
- [ ] Hex dump analysis of existing file
- [ ] Identify file signature/magic bytes
- [ ] Detect patterns (repeated structures, offsets)
- [ ] Identify endianness
- [ ] Find data length indicators
- [ ] Document structure hypothesis

#### Phase 2: Basic Reader
- [ ] Implement binary file reader
- [ ] Read file header
- [ ] Parse known structures
- [ ] Store unknown data separately
- [ ] Export to JSON/YAML for inspection

#### Phase 3: Data Model
- [ ] Define data classes/models
- [ ] Map binary data to models
- [ ] Handle edge cases (missing data, invalid entries)
- [ ] Validation logic

#### Phase 4: Basic Writer
- [ ] Serialize data models to binary
- [ ] Preserve original format
- [ ] Handle unknown blocks
- [ ] Verify written files open in Z21 app

#### Phase 5: Editor Features
- [ ] Command-line interface or GUI
- [ ] List locomotives
- [ ] Edit locomotive data (name, address, functions)
- [ ] Modify CV values
- [ ] Edit accessories
- [ ] Backup/restore functionality

#### Phase 6: Advanced Features
- [ ] Merge files
- [ ] Validate data integrity
- [ ] Undo/redo
- [ ] Search and replace
- [ ] Import/export to other formats

### 4. File Structure Hypothesis

```
[File Header] (0x?? bytes)
  - Magic number/signature
  - Version number
  - File size
  - Checksum

[Section 1: Locomotives] (variable length)
  - Count
  - Entry 1: Address, Name, Functions, CVs...
  - Entry 2: ...
  
[Section 2: Accessories] (variable length)
  - Count
  - Entry 1: Address, Type, State...
  
[Section 3: Layout] (variable length)
  - Track configuration
  - Block occupancy
  
[Section 4: Settings] (variable length)
  - System settings
  - User preferences
  
[Footer/Checksum] (0x?? bytes)
```

### 5. Safety Features

- **Backup**: Always create backup before writing
- **Validation**: Verify file integrity after write
- **Read-only mode**: Option to prevent accidental writes
- **Checksum verification**: Detect corruption
- **Unknown data preservation**: Don't lose unidentified blocks

### 6. User Interface Options

#### Option A: Command-Line Tool
- Simple, scriptable
- Commands: `read`, `write`, `list`, `edit`, `export`

#### Option B: GUI Application
- Visual editor
- Drag-and-drop
- Real-time preview
- Better for non-technical users

#### Option C: Web Application
- Browser-based
- No installation needed
- Can run locally or on server

### 7. Testing Strategy

- Create test files with known data
- Compare before/after file hashes (with careful modification)
- Verify compatibility with Z21 app
- Test edge cases (empty files, corrupted files, large files)

### 8. Documentation Needs

- File format specification (as discovered)
- API documentation
- User manual
- Examples and tutorials

## Recommended Starting Approach

1. **Use Python** for rapid prototyping and analysis
2. **Start with Phase 1**: Create hex dump viewer and analysis tools
3. **Build incrementally**: Read → Parse → Model → Write
4. **Test carefully**: Always verify Z21 app compatibility

## Next Steps

1. Create hex dump utility to analyze file structure
2. Build basic binary reader framework
3. Identify file header and initial patterns
4. Implement iterative parsing as structure becomes clearer

