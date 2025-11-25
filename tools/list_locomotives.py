#!/usr/bin/env python3
"""
List locomotives from Z21 file with detailed information.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.parser import Z21Parser


def show_locomotive_details(loco, index: int = None):
    """Display detailed information about a locomotive."""
    if index is not None:
        print(f"\n#{index}. {loco.name}")
    else:
        print(f"\n{loco.name}")
    print("=" * 70)
    print(f"Address:           {loco.address}")
    print(f"Name:              {loco.name}")
    print(f"Max Speed:         {loco.speed}")
    print(f"Direction:         {'Forward' if loco.direction else 'Reverse'}")
    print(f"Functions:         {len(loco.functions)} configured")
    
    if loco.function_details:
        print("\nFunction Details:")
        print("-" * 85)
        print(f"{'Func':<6} {'Position':<8} {'Icon/Image':<20} {'Button':<10} {'Shortcut':<10} {'Time':<8}")
        print("-" * 85)
        # Sort by position, then by function number
        sorted_funcs = sorted(loco.function_details.items(), 
                            key=lambda x: (x[1].position, x[1].function_number))
        for func_num, func_info in sorted_funcs:
            icon_name = func_info.image_name if func_info.image_name else '(none)'
            shortcut = func_info.shortcut if func_info.shortcut else '-'
            time_str = func_info.time if func_info.time else '0'
            button_type_name = func_info.button_type_name()
            print(f"F{func_num:<5} {func_info.position:<8} {icon_name:<20} {button_type_name:<10} {shortcut:<10} {time_str:<8}")
        print("-" * 85)
        print(f"\nTotal Functions: {len(loco.function_details)}")
    elif loco.functions:
        func_list = sorted(loco.functions.keys())
        print(f"Function Numbers:  {func_list}")
        # Show function states
        active_funcs = [f for f, state in loco.functions.items() if state]
        if active_funcs:
            print(f"Active Functions:  {sorted(active_funcs)}")
    else:
        print("Function Numbers:  None")
    
    if loco.cvs:
        print(f"\nCVs:               {len(loco.cvs)} configured")
        for cv_num, cv_value in sorted(loco.cvs.items()):
            print(f"  CV{cv_num:3d} = {cv_value}")
    else:
        print("\nCVs:               None configured")
    print("=" * 70)


def find_locomotive(z21_data, address: int = None, name: str = None, search: str = None):
    """Find locomotive(s) by address, name, or search term."""
    results = []
    
    for loco in z21_data.locomotives:
        match = False
        
        if address is not None and loco.address == address:
            match = True
        elif name is not None and loco.name.lower() == name.lower():
            match = True
        elif search is not None and search.lower() in loco.name.lower():
            match = True
        
        if match:
            results.append(loco)
    
    return results


def list_locomotives(z21_file: Path, detailed: bool = False, address: int = None, 
                     name: str = None, search: str = None):
    """List all locomotives from Z21 file."""
    parser = Z21Parser(z21_file)
    z21_data = parser.parse()
    
    # If searching for specific locomotive(s)
    if address is not None or name is not None or search is not None:
        results = find_locomotive(z21_data, address=address, name=name, search=search)
        
        if not results:
            if address is not None:
                print(f"No locomotive found with address: {address}")
            elif name is not None:
                print(f"No locomotive found with name: '{name}'")
            elif search is not None:
                print(f"No locomotives found matching: '{search}'")
            return
        
        print(f"Z21 File: {z21_file}")
        print(f"Found {len(results)} matching locomotive(s)\n")
        
        for i, loco in enumerate(results, 1):
            show_locomotive_details(loco, i)
        
        return
    
    # Show all locomotives
    print(f"Z21 File: {z21_file}")
    print(f"Version: {z21_data.version}")
    print(f"Total Locomotives: {len(z21_data.locomotives)}")
    print(f"Layouts: {len(z21_data.layouts)}")
    print("=" * 70)
    
    if detailed:
        # Detailed view
        for i, loco in enumerate(z21_data.locomotives, 1):
            show_locomotive_details(loco, i)
    else:
        # Simple list view
        print("\nLocomotives:")
        print("-" * 70)
        for i, loco in enumerate(z21_data.locomotives, 1):
            func_count = len(loco.functions) if loco.functions else 0
            print(f"{i:3d}. Address: {loco.address:4d} | {loco.name:40s} | "
                  f"Speed: {loco.speed:3d} | Functions: {func_count:2d}")
    
    if z21_data.layouts:
        print("\n" + "=" * 70)
        print("Layouts:")
        for layout in z21_data.layouts:
            print(f"  - {layout.name}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='List locomotives from Z21 file',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all locomotives
  %(prog)s z21_new.z21
  
  # Show detailed view of all
  %(prog)s z21_new.z21 --detailed
  
  # Show specific locomotive by address
  %(prog)s z21_new.z21 --address 5
  
  # Show specific locomotive by exact name
  %(prog)s z21_new.z21 --name "BR 218"
  
  # Search for locomotives matching text
  %(prog)s z21_new.z21 --search "BR"
        """
    )
    parser.add_argument('file', type=Path, help='Z21 file to read')
    parser.add_argument('-d', '--detailed', action='store_true', 
                       help='Show detailed information for each locomotive')
    parser.add_argument('-a', '--address', type=int, 
                       help='Show details of locomotive with specific address')
    parser.add_argument('-n', '--name', type=str,
                       help='Show details of locomotive with exact name')
    parser.add_argument('-s', '--search', type=str,
                       help='Search for locomotives matching text (case-insensitive)')
    
    args = parser.parse_args()
    
    if not args.file.exists():
        print(f"Error: File not found: {args.file}")
        sys.exit(1)
    
    # Validate that only one filter is used
    filters = [args.address, args.name, args.search]
    if sum(1 for f in filters if f is not None) > 1:
        print("Error: Use only one of --address, --name, or --search")
        sys.exit(1)
    
    list_locomotives(args.file, args.detailed, 
                     address=args.address, name=args.name, search=args.search)


if __name__ == '__main__':
    main()

