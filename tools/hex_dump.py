#!/usr/bin/env python3
"""
Hex dump utility for analyzing Z21 binary files.
"""

import argparse
from pathlib import Path


def hex_dump(file_path: Path, start_offset: int = 0, length: int = None, width: int = 16):
    """
    Print hex dump of binary file.
    
    Args:
        file_path: Path to binary file
        start_offset: Starting byte offset
        length: Number of bytes to dump (None = entire file)
        width: Bytes per line
    """
    file_path = Path(file_path)
    
    if not file_path.exists():
        print(f"Error: File not found: {file_path}")
        return
    
    with open(file_path, 'rb') as f:
        # Seek to start offset
        if start_offset > 0:
            f.seek(start_offset)
        
        # Determine length
        if length is None:
            f.seek(0, 2)  # Seek to end
            file_size = f.tell()
            f.seek(start_offset)
            length = file_size - start_offset
        
        offset = start_offset
        bytes_read = 0
        
        print(f"Hex dump of {file_path.name}")
        print(f"Offset: {start_offset}, Length: {length}")
        print("-" * 70)
        print(f"{'Offset':<10} {'Hex':<48} {'ASCII'}")
        print("-" * 70)
        
        while bytes_read < length:
            chunk = f.read(min(width, length - bytes_read))
            if not chunk:
                break
            
            # Format hex
            hex_str = ' '.join(f'{b:02x}' for b in chunk)
            hex_str += ' ' * (width * 3 - len(hex_str))  # Pad to width
            
            # Format ASCII
            ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
            
            print(f"{offset:08x}   {hex_str}   {ascii_str}")
            
            offset += len(chunk)
            bytes_read += len(chunk)


def main():
    parser = argparse.ArgumentParser(description='Hex dump utility for Z21 files')
    parser.add_argument('file', type=Path, help='Binary file to dump')
    parser.add_argument('-o', '--offset', type=int, default=0, help='Starting offset (default: 0)')
    parser.add_argument('-l', '--length', type=int, default=None, help='Number of bytes to dump (default: entire file)')
    parser.add_argument('-w', '--width', type=int, default=16, help='Bytes per line (default: 16)')
    
    args = parser.parse_args()
    hex_dump(args.file, args.offset, args.length, args.width)


if __name__ == '__main__':
    main()

