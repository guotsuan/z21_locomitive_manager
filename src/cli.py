#!/usr/bin/env python3
"""
Command-line interface for Z21 file reader/writer.
"""

import argparse
import json
import sys
from pathlib import Path

# Handle imports for both module and direct execution
try:
    from .parser import Z21Parser
    from .data_models import Z21File
except ImportError:
    # If relative import fails, add parent to path and use absolute import
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from src.parser import Z21Parser
    from src.data_models import Z21File


def export_to_json(z21_file: Z21File, output_path: Path):
    """Export Z21 file data to JSON format."""
    data = {
        'version': z21_file.version,
        'locomotives': [
            {
                'address': loco.address,
                'name': loco.name,
                'functions': loco.functions,
                'cvs': loco.cvs,
                'speed': loco.speed,
                'direction': loco.direction,
            }
            for loco in z21_file.locomotives
        ],
        'accessories': [
            {
                'address': acc.address,
                'name': acc.name,
                'type': acc.accessory_type,
                'state': acc.state,
            }
            for acc in z21_file.accessories
        ],
        'layouts': [
            {
                'name': layout.name,
                'track_type': layout.track_type,
                'blocks': layout.blocks,
            }
            for layout in z21_file.layouts
        ],
        'unknown_blocks': [
            {
                'offset': block.offset,
                'length': block.length,
                'data': block.data.hex(),  # Convert bytes to hex string
            }
            for block in z21_file.unknown_blocks
        ],
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"Exported to {output_path}")


def main():
    parser = argparse.ArgumentParser(description='Z21 file reader/writer')
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Read command
    read_parser = subparsers.add_parser('read', help='Read and display Z21 file')
    read_parser.add_argument('file', type=Path, help='Z21 file to read')
    
    # Export command
    export_parser = subparsers.add_parser('export', help='Export Z21 file to JSON')
    export_parser.add_argument('file', type=Path, help='Z21 file to export')
    export_parser.add_argument('output', type=Path, help='Output JSON file')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    if not args.file.exists():
        print(f"Error: File not found: {args.file}")
        return
    
    # Parse file
    z21_parser = Z21Parser(args.file)
    z21_file = z21_parser.parse()
    
    if args.command == 'read':
        print(z21_file)
        print(f"\nLocomotives: {len(z21_file.locomotives)}")
        for loco in z21_file.locomotives:
            print(f"  - {loco}")
        print(f"\nAccessories: {len(z21_file.accessories)}")
        for acc in z21_file.accessories:
            print(f"  - {acc}")
        print(f"\nUnknown blocks: {len(z21_file.unknown_blocks)}")
        for block in z21_file.unknown_blocks:
            print(f"  - {block}")
    
    elif args.command == 'export':
        export_to_json(z21_file, args.output)


if __name__ == '__main__':
    main()

