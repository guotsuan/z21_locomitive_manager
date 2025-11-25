"""
Binary file reader utilities for Z21 files.
"""

import struct
from pathlib import Path
from typing import BinaryIO, Optional, Tuple


class BinaryReader:
    """Utility class for reading binary data from Z21 files."""
    
    def __init__(self, file_path: Path, byte_order: str = '<'):
        """
        Initialize binary reader.
        
        Args:
            file_path: Path to the binary file
            byte_order: '<' for little-endian, '>' for big-endian
        """
        self.file_path = Path(file_path)
        self.byte_order = byte_order
        self.file: Optional[BinaryIO] = None
        
    def __enter__(self):
        """Context manager entry."""
        self.file = open(self.file_path, 'rb')
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if self.file:
            self.file.close()
    
    def read_bytes(self, count: int) -> bytes:
        """Read specified number of bytes."""
        if not self.file:
            raise RuntimeError("File not open. Use as context manager.")
        data = self.file.read(count)
        if len(data) < count:
            raise EOFError(f"Expected {count} bytes, got {len(data)}")
        return data
    
    def read_uint8(self) -> int:
        """Read unsigned 8-bit integer."""
        return struct.unpack(f'{self.byte_order}B', self.read_bytes(1))[0]
    
    def read_uint16(self) -> int:
        """Read unsigned 16-bit integer."""
        return struct.unpack(f'{self.byte_order}H', self.read_bytes(2))[0]
    
    def read_uint32(self) -> int:
        """Read unsigned 32-bit integer."""
        return struct.unpack(f'{self.byte_order}I', self.read_bytes(4))[0]
    
    def read_int8(self) -> int:
        """Read signed 8-bit integer."""
        return struct.unpack(f'{self.byte_order}b', self.read_bytes(1))[0]
    
    def read_int16(self) -> int:
        """Read signed 16-bit integer."""
        return struct.unpack(f'{self.byte_order}h', self.read_bytes(2))[0]
    
    def read_int32(self) -> int:
        """Read signed 32-bit integer."""
        return struct.unpack(f'{self.byte_order}i', self.read_bytes(4))[0]
    
    def read_string(self, length: int, encoding: str = 'utf-8') -> str:
        """Read string of specified length."""
        data = self.read_bytes(length)
        # Remove null terminators
        data = data.rstrip(b'\x00')
        return data.decode(encoding, errors='ignore')
    
    def read_null_terminated_string(self, max_length: int = 256, encoding: str = 'utf-8') -> str:
        """Read null-terminated string."""
        data = bytearray()
        for _ in range(max_length):
            byte = self.read_bytes(1)[0]
            if byte == 0:
                break
            data.append(byte)
        return data.decode(encoding, errors='ignore')
    
    def tell(self) -> int:
        """Get current file position."""
        if not self.file:
            raise RuntimeError("File not open.")
        return self.file.tell()
    
    def seek(self, position: int, whence: int = 0) -> int:
        """Seek to position in file."""
        if not self.file:
            raise RuntimeError("File not open.")
        return self.file.seek(position, whence)
    
    def peek(self, count: int) -> bytes:
        """Peek at next bytes without advancing position."""
        pos = self.tell()
        data = self.read_bytes(count)
        self.seek(pos)
        return data
    
    def get_file_size(self) -> int:
        """Get total file size."""
        if not self.file:
            raise RuntimeError("File not open.")
        pos = self.file.tell()
        self.file.seek(0, 2)  # Seek to end
        size = self.file.tell()
        self.file.seek(pos)  # Restore position
        return size
    
    def remaining_bytes(self) -> int:
        """Get number of remaining bytes."""
        pos = self.tell()
        size = self.get_file_size()
        return size - pos

