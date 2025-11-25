#!/usr/bin/env python3
"""
Match PNG files to locomotive function icons and get user confirmation.

This tool:
1. Analyzes extracted PNG files
2. Attempts to match them to icon names from the database
3. Shows matches for user confirmation
4. Copies confirmed matches to icon directories
"""

import sys
import zipfile
import sqlite3
import tempfile
import shutil
from pathlib import Path
from collections import defaultdict
import hashlib

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("Warning: PIL/Pillow not installed. Install with: pip install Pillow")

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


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


def analyze_png_file(png_file: Path):
    """Analyze a PNG file and return metadata."""
    info = {
        'path': png_file,
        'name': png_file.name,
        'size': png_file.stat().st_size,
        'width': None,
        'height': None,
        'mode': None,
        'hash': None,
    }
    
    if HAS_PIL:
        try:
            img = Image.open(png_file)
            info['width'] = img.width
            info['height'] = img.height
            info['mode'] = img.mode
            
            # Create a simple hash based on image properties
            img_hash = hashlib.md5(f"{img.width}x{img.height}x{img.mode}".encode()).hexdigest()[:8]
            info['hash'] = img_hash
        except Exception as e:
            info['error'] = str(e)
    
    return info


def find_png_files(extracted_dir: Path):
    """Find all PNG files in extracted directory."""
    png_files = []
    if extracted_dir.exists():
        png_files = list(extracted_dir.rglob("*.png"))
    return png_files


def get_icon_usage_stats(z21_file: Path):
    """Get usage statistics for each icon."""
    with zipfile.ZipFile(z21_file, 'r') as zf:
        sqlite_files = [f for f in zf.namelist() if f.endswith('.sqlite')]
        if not sqlite_files:
            return {}
        
        sqlite_file = sqlite_files[0]
        sqlite_data = zf.read(sqlite_file)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.sqlite') as tmp:
            tmp.write(sqlite_data)
            tmp_path = tmp.name
        
        try:
            db = sqlite3.connect(tmp_path)
            cursor = db.cursor()
            cursor.execute("""
                SELECT image_name, COUNT(*) as count
                FROM functions
                WHERE image_name IS NOT NULL AND image_name != ''
                GROUP BY image_name
            """)
            stats = {row[0]: row[1] for row in cursor.fetchall()}
            db.close()
            return stats
        finally:
            Path(tmp_path).unlink()


def suggest_matches(png_files, icon_names):
    """Suggest potential matches based on various heuristics."""
    suggestions = defaultdict(list)
    
    # Group PNGs by size (icons are likely similar sizes)
    size_groups = defaultdict(list)
    for png_info in png_files:
        if png_info['width'] and png_info['height']:
            size_key = f"{png_info['width']}x{png_info['height']}"
            size_groups[size_key].append(png_info)
    
    # Common icon sizes (from analysis, most are 500x200 or similar)
    icon_sizes = [size for size, files in size_groups.items() if len(files) > 1]
    
    print(f"\nFound {len(png_files)} PNG files")
    print(f"Grouped into {len(size_groups)} size groups")
    print(f"Most common sizes: {sorted(icon_sizes, key=lambda x: len(size_groups[x]), reverse=True)[:5]}")
    
    return suggestions


def interactive_match(png_files, icon_names, icon_stats, output_dir: Path):
    """Interactively match PNG files to icon names."""
    icons_dir = output_dir / "icons_by_name"
    icons_dir.mkdir(parents=True, exist_ok=True)
    
    # Group PNGs by size
    size_groups = defaultdict(list)
    for png_info in png_files:
        if png_info['width'] and png_info['height']:
            size_key = f"{png_info['width']}x{png_info['height']}"
            size_groups[size_key].append(png_info)
    
    # Sort icon names by usage (most used first)
    sorted_icons = sorted(icon_names, key=lambda x: icon_stats.get(x, 0), reverse=True)
    
    matches = {}
    skipped = []
    
    print("\n" + "=" * 70)
    print("Interactive Icon Matching")
    print("=" * 70)
    print("\nFor each icon name, you'll see PNG files that might match.")
    print("Type 'y' to confirm, 'n' to skip, or a number to select a specific PNG.")
    print("Type 'q' to quit and save current matches.\n")
    
    for icon_name in sorted_icons:
        print(f"\n{'='*70}")
        print(f"Icon: {icon_name} (used {icon_stats.get(icon_name, 0)} times)")
        print(f"{'='*70}")
        
        # Show potential matches (PNGs of similar size)
        candidates = []
        for size_key, png_list in size_groups.items():
            # Icons are typically square-ish or rectangular
            for png_info in png_list:
                if png_info['path'] not in matches.values():
                    candidates.append(png_info)
        
        if not candidates:
            print("No more PNG files available for matching.")
            response = input(f"Skip {icon_name}? (y/n): ").strip().lower()
            if response == 'y':
                skipped.append(icon_name)
            continue
        
        # Show first few candidates
        print(f"\nAvailable PNG files ({len(candidates)} total):")
        for i, png_info in enumerate(candidates[:10], 1):
            size_str = f"{png_info['width']}x{png_info['height']}" if png_info['width'] else "unknown"
            size_kb = png_info['size'] / 1024
            print(f"  {i}. {png_info['name']:<40} {size_str:<15} {size_kb:.1f}KB")
        
        if len(candidates) > 10:
            print(f"  ... and {len(candidates) - 10} more")
        
        # Get user input
        while True:
            response = input(f"\nMatch '{icon_name}' to PNG? (y/n/1-{min(10, len(candidates))}/q): ").strip().lower()
            
            if response == 'q':
                print("\nSaving current matches and exiting...")
                break
            elif response == 'y':
                # Use first candidate
                selected = candidates[0]
                matches[icon_name] = selected['path']
                print(f"✓ Matched {icon_name} -> {selected['name']}")
                break
            elif response == 'n':
                skipped.append(icon_name)
                print(f"⊘ Skipped {icon_name}")
                break
            elif response.isdigit():
                idx = int(response) - 1
                if 0 <= idx < len(candidates):
                    selected = candidates[idx]
                    matches[icon_name] = selected['path']
                    print(f"✓ Matched {icon_name} -> {selected['name']}")
                    break
                else:
                    print(f"Invalid number. Please enter 1-{len(candidates)}")
            else:
                print("Invalid input. Please enter 'y', 'n', a number, or 'q'")
        
        if response == 'q':
            break
    
    # Copy matched files
    print(f"\n{'='*70}")
    print("Copying matched icons...")
    print(f"{'='*70}")
    
    for icon_name, png_path in matches.items():
        icon_dir = icons_dir / icon_name
        icon_dir.mkdir(exist_ok=True)
        dest = icon_dir / f"{icon_name}.png"
        shutil.copy2(png_path, dest)
        print(f"✓ Copied {icon_name}.png")
    
    # Save match report
    report_file = output_dir / "icon_matches.txt"
    with open(report_file, 'w') as f:
        f.write("Icon Matching Report\n")
        f.write("=" * 70 + "\n\n")
        f.write(f"Matched: {len(matches)}\n")
        f.write(f"Skipped: {len(skipped)}\n\n")
        f.write("Matches:\n")
        f.write("-" * 70 + "\n")
        for icon_name, png_path in sorted(matches.items()):
            f.write(f"{icon_name:<35} -> {png_path.name}\n")
        
        if skipped:
            f.write("\nSkipped:\n")
            f.write("-" * 70 + "\n")
            for icon_name in skipped:
                f.write(f"{icon_name}\n")
    
    print(f"\n✓ Saved match report: {report_file}")
    print(f"\nSummary: {len(matches)} matched, {len(skipped)} skipped")
    
    return matches, skipped


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Match PNG files to locomotive function icons',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Match icons interactively
  %(prog)s z21_new.z21
  
  # Use specific extracted directory
  %(prog)s z21_new.z21 -d ./extracted_icons/raw_extracted
        """
    )
    parser.add_argument('file', type=Path, help='Z21 file')
    parser.add_argument('-d', '--extracted-dir', type=Path,
                       help='Directory with extracted PNG files')
    parser.add_argument('-o', '--output', type=Path,
                       help='Output directory for matched icons')
    
    args = parser.parse_args()
    
    if not args.file.exists():
        print(f"Error: File not found: {args.file}")
        sys.exit(1)
    
    # Determine extracted directory
    if args.extracted_dir:
        extracted_dir = args.extracted_dir
    else:
        extracted_dir = args.file.parent / "extracted_icons" / "raw_extracted"
    
    if not extracted_dir.exists():
        print(f"Error: Extracted directory not found: {extracted_dir}")
        print("Please run extract_icons.py first or specify -d option")
        sys.exit(1)
    
    # Determine output directory
    output_dir = args.output or (args.file.parent / "extracted_icons")
    
    print("=" * 70)
    print("Icon Matching Tool")
    print("=" * 70)
    print(f"Z21 File: {args.file}")
    print(f"Extracted PNGs: {extracted_dir}")
    print(f"Output: {output_dir}")
    
    # Get icon names
    print("\nLoading icon names from database...")
    icon_names = get_icon_names_from_db(args.file)
    print(f"Found {len(icon_names)} icon names")
    
    # Get usage stats
    print("Loading icon usage statistics...")
    icon_stats = get_icon_usage_stats(args.file)
    
    # Find PNG files
    print(f"\nScanning for PNG files in {extracted_dir}...")
    png_paths = find_png_files(extracted_dir)
    print(f"Found {len(png_paths)} PNG files")
    
    if not png_paths:
        print("No PNG files found!")
        sys.exit(1)
    
    # Analyze PNG files
    print("\nAnalyzing PNG files...")
    png_files = []
    for png_path in png_paths:
        info = analyze_png_file(png_path)
        png_files.append(info)
    
    # Interactive matching
    matches, skipped = interactive_match(png_files, icon_names, icon_stats, output_dir)
    
    print("\nDone!")


if __name__ == '__main__':
    main()

