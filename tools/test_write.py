#!/usr/bin/env python3
"""
Test script to verify write functionality for Z21 files.
"""

import sys
import shutil
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.parser import Z21Parser
from src.data_models import Z21File


def test_write_functionality(z21_file: Path):
    """Test writing changes back to Z21 file."""
    print("=" * 70)
    print("Testing Z21 Write Functionality")
    print("=" * 70)
    
    # Create backup
    backup_file = z21_file.with_suffix('.z21.backup')
    print(f"\n1. Creating backup: {backup_file}")
    shutil.copy2(z21_file, backup_file)
    
    try:
        # Parse original file
        print(f"\n2. Parsing original file: {z21_file}")
        parser = Z21Parser(z21_file)
        z21_data = parser.parse()
        
        if not z21_data.locomotives:
            print("ERROR: No locomotives found in file!")
            return False
        
        # Show original data
        loco = z21_data.locomotives[0]
        print(f"\n3. Original locomotive data:")
        print(f"   Name: {loco.name}")
        print(f"   Address: {loco.address}")
        print(f"   Max Speed: {loco.speed}")
        print(f"   Direction: {'Forward' if loco.direction else 'Reverse'}")
        
        # Make a test change
        original_name = loco.name
        test_name = f"{original_name}_TEST"
        loco.name = test_name
        
        print(f"\n4. Making test change:")
        print(f"   Changing name from '{original_name}' to '{test_name}'")
        
        # Write changes
        print(f"\n5. Writing changes to file...")
        try:
            output_path = parser.write(z21_data, z21_file)
            print(f"   ✓ Successfully wrote to: {output_path}")
        except Exception as e:
            print(f"   ✗ Error writing file: {e}")
            return False
        
        # Verify changes by re-parsing
        print(f"\n6. Verifying changes by re-parsing file...")
        parser2 = Z21Parser(z21_file)
        z21_data2 = parser2.parse()
        
        if not z21_data2.locomotives:
            print("   ✗ ERROR: No locomotives found after write!")
            return False
        
        loco2 = z21_data2.locomotives[0]
        print(f"\n7. Verifying locomotive data after write:")
        print(f"   Name: {loco2.name} (expected: {test_name})")
        print(f"   Address: {loco2.address} (expected: {loco.address})")
        print(f"   Max Speed: {loco2.speed} (expected: {loco.speed})")
        print(f"   Direction: {'Forward' if loco2.direction else 'Reverse'} (expected: {'Forward' if loco.direction else 'Reverse'})")
        
        # Check if changes were saved
        success = True
        if loco2.name != test_name:
            print(f"   ✗ Name mismatch!")
            success = False
        if loco2.address != loco.address:
            print(f"   ✗ Address mismatch!")
            success = False
        if loco2.speed != loco.speed:
            print(f"   ✗ Speed mismatch!")
            success = False
        if loco2.direction != loco.direction:
            print(f"   ✗ Direction mismatch!")
            success = False
        
        if success:
            print(f"\n✓ All changes verified successfully!")
        else:
            print(f"\n✗ Some changes were not saved correctly!")
        
        return success
        
    except Exception as e:
        print(f"\n✗ ERROR during test: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Restore backup
        print(f"\n8. Restoring original file from backup...")
        shutil.copy2(backup_file, z21_file)
        backup_file.unlink()
        print(f"   ✓ Original file restored")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <z21_file>")
        sys.exit(1)
    
    z21_file = Path(sys.argv[1])
    if not z21_file.exists():
        print(f"Error: File not found: {z21_file}")
        sys.exit(1)
    
    success = test_write_functionality(z21_file)
    sys.exit(0 if success else 1)

