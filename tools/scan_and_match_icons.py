#!/usr/bin/env python3
"""
Scan icons directory and match icon files to function icon names from database.
Creates/updates a mapping file for icon matching.
"""

import sys
import zipfile
import sqlite3
import tempfile
import json
from pathlib import Path
from collections import defaultdict

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.parser import Z21Parser


def get_icon_names_from_db(z21_file: Path):
    """Get all icon names from database."""
    with zipfile.ZipFile(z21_file, 'r') as zf:
        sqlite_files = [f for f in zf.namelist() if f.endswith('.sqlite')]
        if not sqlite_files:
            return set()
        
        sqlite_file = sqlite_files[0]
        sqlite_data = zf.read(sqlite_file)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.sqlite') as tmp:
            tmp.write(sqlite_data)
            tmp_path = tmp.name
        
        try:
            db = sqlite3.connect(tmp_path)
            cursor = db.cursor()
            cursor.execute("""
                SELECT DISTINCT image_name 
                FROM functions 
                WHERE image_name IS NOT NULL AND image_name != ''
                ORDER BY image_name
            """)
            icon_names = {row[0] for row in cursor.fetchall()}
            db.close()
            return icon_names
        finally:
            Path(tmp_path).unlink()


def scan_icon_files(icons_dir: Path):
    """Scan icons directory for PNG files."""
    icon_files = {}
    
    if not icons_dir.exists():
        return icon_files
    
    # Find all PNG files
    for png_file in icons_dir.glob("*.png"):
        name = png_file.stem  # filename without extension
        
        # Normalize name (remove _Normal, _normal suffixes)
        normalized = name.replace('_Normal', '').replace('_normal', '').lower()
        
        if normalized not in icon_files:
            icon_files[normalized] = []
        icon_files[normalized].append({
            'path': str(png_file),
            'filename': png_file.name,
            'original_name': name
        })
    
    return icon_files


def match_icons(icon_names, icon_files):
    """Match icon names to icon files."""
    matches = {}
    unmatched_names = []
    unmatched_files = set()
    
    # Create lookup for icon files by normalized name
    file_lookup = {}
    for normalized, files in icon_files.items():
        file_lookup[normalized] = files[0]  # Use first match
    
    # Try to match each icon name
    for icon_name in icon_names:
        icon_lower = icon_name.lower()
        
        # Try exact match
        if icon_lower in file_lookup:
            matches[icon_name] = file_lookup[icon_lower]
            continue
        
        # Try with _normal suffix
        if f"{icon_lower}_normal" in file_lookup:
            matches[icon_name] = file_lookup[f"{icon_lower}_normal"]
            continue
        
        # Try with _Normal suffix
        if f"{icon_lower}_normal" in file_lookup:
            matches[icon_name] = file_lookup[f"{icon_lower}_normal"]
            continue
        
        # Try partial matches (icon_name contains file name or vice versa)
        found = False
        for normalized, file_info in file_lookup.items():
            if icon_lower in normalized or normalized in icon_lower:
                matches[icon_name] = file_info
                found = True
                break
        
        if not found:
            unmatched_names.append(icon_name)
    
    # Find unmatched files
    matched_file_paths = {info['path'] for info in matches.values()}
    for normalized, files in icon_files.items():
        for file_info in files:
            if file_info['path'] not in matched_file_paths:
                unmatched_files.add(file_info['filename'])
    
    return matches, unmatched_names, unmatched_files


def save_mapping(matches, output_file: Path):
    """Save icon mapping to JSON file."""
    mapping_data = {
        'version': '1.0',
        'matches': {}
    }
    
    for icon_name, file_info in matches.items():
        mapping_data['matches'][icon_name] = {
            'path': file_info['path'],
            'filename': file_info['filename']
        }
    
    with open(output_file, 'w') as f:
        json.dump(mapping_data, f, indent=2)
    
    print(f"Saved mapping to: {output_file}")


def load_mapping(mapping_file: Path):
    """Load icon mapping from JSON file."""
    if not mapping_file.exists():
        return {}
    
    with open(mapping_file, 'r') as f:
        data = json.load(f)
        return data.get('matches', {})


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Scan icons directory and match to function icon names',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scan and create mapping
  %(prog)s z21_new.z21
  
  # Use custom icons directory
  %(prog)s z21_new.z21 -i ./custom_icons
  
  # Update existing mapping
  %(prog)s z21_new.z21 --update
        """
    )
    parser.add_argument('file', type=Path, help='Z21 file')
    parser.add_argument('-i', '--icons-dir', type=Path, 
                       default=project_root / 'icons',
                       help='Icons directory (default: ./icons)')
    parser.add_argument('-o', '--output', type=Path,
                       default=project_root / 'icon_mapping.json',
                       help='Output mapping file (default: icon_mapping.json)')
    parser.add_argument('--update', action='store_true',
                       help='Update existing mapping instead of overwriting')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Show detailed matching information')
    
    args = parser.parse_args()
    
    if not args.file.exists():
        print(f"Error: Z21 file not found: {args.file}")
        sys.exit(1)
    
    print("=" * 70)
    print("Icon Scanning and Matching Tool")
    print("=" * 70)
    print(f"Z21 File: {args.file}")
    print(f"Icons Directory: {args.icons_dir}")
    print(f"Output Mapping: {args.output}")
    print()
    
    # Get icon names from database
    print("Loading icon names from database...")
    icon_names = get_icon_names_from_db(args.file)
    print(f"Found {len(icon_names)} icon names in database")
    
    # Scan icon files
    print(f"\nScanning icon files in {args.icons_dir}...")
    icon_files = scan_icon_files(args.icons_dir)
    print(f"Found {len(icon_files)} unique icon files")
    
    if args.verbose:
        print("\nIcon files found:")
        for normalized, files in sorted(icon_files.items()):
            print(f"  {normalized}: {len(files)} file(s)")
            for f in files:
                print(f"    - {f['filename']}")
    
    # Match icons
    print("\nMatching icons...")
    matches, unmatched_names, unmatched_files = match_icons(icon_names, icon_files)
    
    # Load existing mapping if updating
    if args.update and args.output.exists():
        existing = load_mapping(args.output)
        print(f"Loaded {len(existing)} existing mappings")
        # Merge: keep existing, add new matches
        for icon_name, file_info in matches.items():
            if icon_name not in existing:
                existing[icon_name] = file_info
        matches = existing
    
    # Display results
    print("\n" + "=" * 70)
    print("Matching Results")
    print("=" * 70)
    print(f"Matched: {len(matches)}")
    print(f"Unmatched icon names: {len(unmatched_names)}")
    print(f"Unmatched icon files: {len(unmatched_files)}")
    
    if args.verbose:
        print("\nMatched icons:")
        for icon_name in sorted(matches.keys()):
            file_info = matches[icon_name]
            print(f"  {icon_name:<30} -> {file_info['filename']}")
        
        if unmatched_names:
            print("\nUnmatched icon names:")
            for name in sorted(unmatched_names):
                print(f"  {name}")
        
        if unmatched_files:
            print("\nUnmatched icon files:")
            for filename in sorted(unmatched_files):
                print(f"  {filename}")
    
    # Save mapping
    if matches:
        save_mapping(matches, args.output)
        print(f"\n✓ Successfully created mapping with {len(matches)} matches")
    else:
        print("\n⚠ No matches found. Check icon file naming conventions.")
    
    # Create summary report
    report_file = args.output.parent / f"{args.output.stem}_report.txt"
    with open(report_file, 'w') as f:
        f.write("Icon Matching Report\n")
        f.write("=" * 70 + "\n\n")
        f.write(f"Total icon names in database: {len(icon_names)}\n")
        f.write(f"Total icon files found: {sum(len(files) for files in icon_files.values())}\n")
        f.write(f"Matched: {len(matches)}\n")
        f.write(f"Unmatched names: {len(unmatched_names)}\n")
        f.write(f"Unmatched files: {len(unmatched_files)}\n\n")
        
        f.write("Matches:\n")
        f.write("-" * 70 + "\n")
        for icon_name in sorted(matches.keys()):
            file_info = matches[icon_name]
            f.write(f"{icon_name:<30} -> {file_info['filename']}\n")
        
        if unmatched_names:
            f.write("\nUnmatched Icon Names:\n")
            f.write("-" * 70 + "\n")
            for name in sorted(unmatched_names):
                f.write(f"{name}\n")
        
        if unmatched_files:
            f.write("\nUnmatched Icon Files:\n")
            f.write("-" * 70 + "\n")
            for filename in sorted(unmatched_files):
                f.write(f"{filename}\n")
    
    print(f"Report saved to: {report_file}")


if __name__ == '__main__':
    main()

