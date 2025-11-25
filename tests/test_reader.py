"""
Tests for binary reader.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytest
from src.binary_reader import BinaryReader


def test_binary_reader_context_manager(tmp_path):
    """Test that BinaryReader works as context manager."""
    # Create a test binary file
    test_file = tmp_path / "test.bin"
    test_file.write_bytes(b'\x01\x02\x03\x04')
    
    with BinaryReader(test_file) as reader:
        assert reader.read_uint8() == 0x01
        assert reader.read_uint8() == 0x02


def test_binary_reader_endianness(tmp_path):
    """Test byte order handling."""
    test_file = tmp_path / "test.bin"
    # Write 0x1234 as little-endian
    test_file.write_bytes(b'\x34\x12')
    
    with BinaryReader(test_file, byte_order='<') as reader:
        assert reader.read_uint16() == 0x1234


def test_peek(tmp_path):
    """Test peek functionality."""
    test_file = tmp_path / "test.bin"
    test_file.write_bytes(b'\x01\x02\x03')
    
    with BinaryReader(test_file) as reader:
        peeked = reader.peek(2)
        assert peeked == b'\x01\x02'
        # Position should not have changed
        assert reader.read_uint8() == 0x01


if __name__ == '__main__':
    pytest.main([__file__])

