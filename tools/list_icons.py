#!/usr/bin/env python3
"""
List all available icons/images in Z21 file configuration.
Shows both used and unused icons.
"""

import sys
import zipfile
import sqlite3
import tempfile
from pathlib import Path
from collections import defaultdict

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.parser import Z21Parser


def get_all_icons_from_db(z21_file: Path):
    """Extract all icon names from SQLite database."""
    with zipfile.ZipFile(z21_file, 'r') as zf:
        sqlite_files = [f for f in zf.namelist() if f.endswith('.sqlite')]
        if not sqlite_files:
            return set(), {}
        
        sqlite_file = sqlite_files[0]
        sqlite_data = zf.read(sqlite_file)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.sqlite') as tmp:
            tmp.write(sqlite_data)
            tmp_path = tmp.name
        
        try:
            db = sqlite3.connect(tmp_path)
            cursor = db.cursor()
            
            # Get all unique icon names
            cursor.execute("""
                SELECT DISTINCT image_name 
                FROM functions 
                WHERE image_name IS NOT NULL AND image_name != ''
                ORDER BY image_name
            """)
            all_icons = {row[0] for row in cursor.fetchall()}
            
            # Get usage count for each icon
            cursor.execute("""
                SELECT image_name, COUNT(*) as usage_count
                FROM functions
                WHERE image_name IS NOT NULL AND image_name != ''
                GROUP BY image_name
                ORDER BY usage_count DESC, image_name
            """)
            usage_counts = {row[0]: row[1] for row in cursor.fetchall()}
            
            db.close()
            return all_icons, usage_counts
        finally:
            Path(tmp_path).unlink()


def get_used_icons(z21_file: Path):
    """Get icons that are actually used by locomotives."""
    parser = Z21Parser(z21_file)
    z21_data = parser.parse()
    
    used_icons = set()
    icon_usage = defaultdict(list)  # icon_name -> list of locomotives using it
    
    for loco in z21_data.locomotives:
        for func_num, func_info in loco.function_details.items():
            if func_info.image_name:
                used_icons.add(func_info.image_name)
                icon_usage[func_info.image_name].append(f"{loco.name} (F{func_num})")
    
    return used_icons, icon_usage


def list_all_icons(z21_file: Path, show_unused: bool = True, show_usage: bool = True):
    """List all available icons and their usage status."""
    print(f"Z21 File: {z21_file}")
    print("=" * 70)
    
    # Get all icons from database
    all_icons_db, usage_counts = get_all_icons_from_db(z21_file)
    
    if not all_icons_db:
        print("No icons found in database (might be XML format)")
        return
    
    # Get actually used icons from parsed data
    used_icons, icon_usage = get_used_icons(z21_file)
    
    unused_icons = all_icons_db - used_icons
    
    print(f"\n📋 Summary:")
    print(f"   Total icons available in configuration: {len(all_icons_db)}")
    print(f"   Icons currently assigned to locomotives: {len(used_icons)}")
    print(f"   Icons in DB but not assigned: {len(unused_icons)}")
    print("=" * 70)
    
    if show_usage:
        print("\n📊 Complete Icon List (All Available in Configuration):")
        print("-" * 70)
        print(f"{'Icon Name':<35} {'Assigned':<12} {'Times Used':<12}")
        print("-" * 70)
        
        # Sort by usage count (descending), then by name
        sorted_icons = sorted(all_icons_db, 
                            key=lambda x: (-usage_counts.get(x, 0), x))
        
        for icon_name in sorted_icons:
            count = usage_counts.get(icon_name, 0)
            is_assigned = "Yes" if icon_name in used_icons else "No (unused)"
            print(f"{icon_name:<35} {is_assigned:<12} {count:<12}")
    
    if show_unused and unused_icons:
        print("\n" + "=" * 70)
        print("🚫 Unused Icons (Available but not used by any locomotive):")
        print("-" * 70)
        for icon in sorted(unused_icons):
            count = usage_counts.get(icon, 0)
            print(f"  {icon:<30} (in DB: {count} times, but not in any loco)")
    
    if show_usage and used_icons:
        print("\n" + "=" * 70)
        print("✅ Most Used Icons:")
        print("-" * 70)
        sorted_by_usage = sorted(usage_counts.items(), 
                                key=lambda x: -x[1])[:10]
        for icon_name, count in sorted_by_usage:
            if icon_name in used_icons:
                locos = icon_usage[icon_name][:3]  # Show first 3 examples
                examples = ", ".join(locos)
                if len(icon_usage[icon_name]) > 3:
                    examples += f", ... ({len(icon_usage[icon_name])-3} more)"
                print(f"  {icon_name:<25} ({count:2d} uses) - Examples: {examples}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='List all available icons/images in Z21 file',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all icons with usage statistics
  %(prog)s z21_new.z21
  
  # Show only unused icons
  %(prog)s z21_new.z21 --unused-only
  
  # Show only used icons with details
  %(prog)s z21_new.z21 --used-only
        """
    )
    parser.add_argument('file', type=Path, help='Z21 file to analyze')
    parser.add_argument('--unused-only', action='store_true',
                       help='Show only unused icons')
    parser.add_argument('--used-only', action='store_true',
                       help='Show only used icons')
    parser.add_argument('--no-usage', action='store_true',
                       help='Hide usage statistics')
    
    args = parser.parse_args()
    
    if not args.file.exists():
        print(f"Error: File not found: {args.file}")
        sys.exit(1)
    
    show_unused = not args.used_only
    show_used = not args.unused_only
    show_usage = not args.no_usage
    
    if args.unused_only:
        list_all_icons(args.file, show_unused=True, show_usage=False)
        # Re-run to get unused icons
        all_icons_db, _ = get_all_icons_from_db(args.file)
        used_icons, _ = get_used_icons(args.file)
        unused_icons = sorted(all_icons_db - used_icons)
        print(f"\n📋 List of {len(unused_icons)} unused icons:")
        for icon in unused_icons:
            print(f"  {icon}")
    elif args.used_only:
        used_icons, icon_usage = get_used_icons(args.file)
        print(f"\n✅ Used Icons ({len(used_icons)}):")
        for icon in sorted(used_icons):
            locos = icon_usage.get(icon, [])
            print(f"  {icon:<30} ({len(locos)} locomotives)")
    else:
        list_all_icons(args.file, show_unused=show_unused, show_usage=show_usage)


if __name__ == '__main__':
    main()

