# Quick Start Guide

## First Steps: Analyzing Your File

### 1. View Hex Dump

Start by examining the binary structure of your file:

```bash
# View first 512 bytes
python tools/hex_dump.py rocoData.z21 -l 512

# View entire file
python tools/hex_dump.py rocoData.z21

# View specific offset (e.g., skip first 100 bytes, view next 256)
python tools/hex_dump.py rocoData.z21 -o 100 -l 256
```

### 2. Read File with CLI

```bash
# Read and display file structure
python -m src.cli read rocoData.z21

# Export to JSON for inspection
python -m src.cli export rocoData.z21 output.json
```

### 3. Analyze Patterns

Look for:
- **Magic bytes**: Common file signatures at the start (e.g., `Z21`, `ROCO`)
- **Repeated patterns**: Structures that repeat (e.g., locomotive entries)
- **Length fields**: Numbers that might indicate section sizes
- **Text strings**: Locomotive names, addresses embedded in binary
- **Null terminators**: `00` bytes separating strings or sections

### 4. Compare with Known Data

If you have multiple files or know what locomotives are in the file:
- Search for locomotive addresses (usually 1-9999 for DCC)
- Look for ASCII strings matching locomotive names
- Find function mappings (F0-F28)

## Development Workflow

1. **Analyze**: Use hex dump to understand structure
2. **Hypothesize**: Create theory about data layout
3. **Implement**: Update parser in `src/parser.py`
4. **Test**: Verify parsed data matches expectations
5. **Refine**: Adjust based on findings

## Example: Finding Locomotive Addresses

If you know your file contains locomotive address 1234, search for it:

```python
# In Python
with open('rocoData.z21', 'rb') as f:
    data = f.read()
    # Search for address 1234 as little-endian (D4 04)
    # and big-endian (04 D4)
    index = data.find(b'\xD4\x04')
    if index >= 0:
        print(f"Found at offset: {index:08x}")
        # Examine surrounding bytes
```

## Next Steps

Once you've identified the file structure:
1. Update `Z21Parser._parse_header()` with header format
2. Update `Z21Parser._parse_locomotives()` with locomotive format
3. Implement writer in `src/binary_writer.py`
4. Test write/read cycle with Z21 app

