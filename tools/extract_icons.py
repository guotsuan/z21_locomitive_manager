#!/usr/bin/env python3
"""
Extract icons from Z21 file and organize them by icon name.

This script:
1. Finds all unique icon names from the database
2. Attempts to match PNG files to icon names
3. Extracts and organizes icons into a directory structure
"""

import sys
import zipfile
import sqlite3
import tempfile
import shutil
from pathlib import Path
try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("Warning: PIL/Pillow not installed. Install with: pip install Pillow")
import re

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def get_all_icon_names(z21_file: Path):
    """Get all unique icon names from the database."""
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


def extract_all_png_files(z21_file: Path, output_dir: Path):
    """Extract all PNG files from ZIP to output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    extracted_files = []
    
    with zipfile.ZipFile(z21_file, 'r') as zf:
        png_files = [f for f in zf.namelist() if f.lower().endswith('.png')]
        
        print(f"Found {len(png_files)} PNG files in ZIP")
        
        for png_file in png_files:
            # Extract with relative path
            zf.extract(png_file, output_dir)
            extracted_path = output_dir / png_file
            extracted_files.append(extracted_path)
            
            # Also copy to a flat structure with a sanitized name
            safe_name = png_file.replace('/', '_').replace('\\', '_')
            flat_path = output_dir / "all_pngs" / safe_name
            flat_path.parent.mkdir(exist_ok=True)
            shutil.copy2(extracted_path, flat_path)
    
    return extracted_files


def create_icon_mapping(icon_names, extracted_files):
    """Attempt to create a mapping between icon names and PNG files."""
    mapping = {}
    
    # First, try direct filename matches
    for icon_name in icon_names:
        # Try various patterns
        patterns = [
            icon_name.lower(),
            icon_name.replace('_', '-').lower(),
            icon_name.replace('_', '').lower(),
            f"{icon_name.lower()}.png",
            f"icon_{icon_name.lower()}",
        ]
        
        for png_file in extracted_files:
            file_name = png_file.name.lower()
            for pattern in patterns:
                if pattern in file_name:
                    mapping[icon_name] = png_file
                    break
            if icon_name in mapping:
                break
    
    return mapping


def analyze_png_structure(png_file: Path):
    """Analyze PNG file to see if it contains multiple icons."""
    try:
        img = Image.open(png_file)
        width, height = img.size
        print(f"  {png_file.name}: {width}x{height} pixels, mode: {img.mode}")
        return width, height, img.mode
    except Exception as e:
        print(f"  Error reading {png_file.name}: {e}")
        return None, None, None


def create_icon_directories(icon_names, output_dir: Path):
    """Create directories for each icon name for organization."""
    icons_dir = output_dir / "icons_by_name"
    icons_dir.mkdir(exist_ok=True)
    
    # Create subdirectory for each icon
    for icon_name in icon_names:
        icon_dir = icons_dir / icon_name
        icon_dir.mkdir(exist_ok=True)
        # Create a README in each directory
        readme = icon_dir / "README.txt"
        with open(readme, 'w') as f:
            f.write(f"Icon name: {icon_name}\n")
            f.write("Place the corresponding icon PNG file here.\n")
            f.write("Rename it to: {icon_name}.png\n")
    
    print(f"Created {len(icon_names)} icon directories in: {icons_dir}")


def extract_icons(z21_file: Path, output_dir: Path = None, analyze: bool = False):
    """Main function to extract and organize icons."""
    if output_dir is None:
        output_dir = Path(z21_file).parent / "extracted_icons"
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Extracting icons from: {z21_file}")
    print(f"Output directory: {output_dir}")
    print("=" * 70)
    
    # Get all icon names from database
    icon_names = get_all_icon_names(z21_file)
    print(f"\nFound {len(icon_names)} unique icon names in database")
    
    # Extract all PNG files
    print("\nExtracting PNG files from ZIP...")
    extracted_files = extract_all_png_files(z21_file, output_dir / "raw_extracted")
    
    if analyze:
        print("\nAnalyzing PNG file structure:")
        for png_file in extracted_files[:20]:  # Analyze first 20
            analyze_png_structure(png_file)
    
    # Try to create mapping
    print("\nAttempting to map icon names to PNG files...")
    mapping = create_icon_mapping(icon_names, extracted_files)
    
    # Create organized structure with directories for each icon
    create_icon_directories(icon_names, output_dir)
    
    icons_dir = output_dir / "icons_by_name"
    
    # List all icon names that need icons
    icon_list_file = icons_dir / "all_icon_names.txt"
    with open(icon_list_file, 'w') as f:
        f.write("All Icon Names from Database:\n")
        f.write("=" * 50 + "\n")
        f.write(f"Total icons: {len(icon_names)}\n")
        f.write(f"Matched from filenames: {len(mapping)}\n\n")
        for icon_name in sorted(icon_names):
            status = "✓ FOUND" if icon_name in mapping else "✗ NEEDS MAPPING"
            f.write(f"{icon_name:<35} {status}\n")
    
    print(f"\nCreated icon name list: {icon_list_file}")
    print(f"\nMatched {len(mapping)} icons to PNG files by filename")
    print(f"Missing {len(icon_names) - len(mapping)} icon mappings")
    
    # Copy matched files to their directories
    for icon_name, png_file in mapping.items():
        icon_dir = icons_dir / icon_name
        dest = icon_dir / f"{icon_name}.png"
        shutil.copy2(png_file, dest)
    
    if mapping:
        print(f"Copied {len(mapping)} matched icons to their directories")
    
    # Create a mapping helper file
    mapping_file = output_dir / "icon_mapping_guide.txt"
    with open(mapping_file, 'w') as f:
        f.write("Icon Mapping Guide\n")
        f.write("=" * 70 + "\n\n")
        f.write("To map PNG files to icon names:\n")
        f.write("1. Review the extracted PNG files in: raw_extracted/\n")
        f.write("2. Copy the appropriate PNG to: icons_by_name/<icon_name>/<icon_name>.png\n")
        f.write("3. The icon names from the database are listed in: all_icon_names.txt\n\n")
        f.write(f"All {len(extracted_files)} extracted PNG files:\n")
        f.write("-" * 70 + "\n")
        for png_file in sorted(extracted_files):
            f.write(f"{png_file.name}\n")
    
    print(f"Created mapping guide: {mapping_file}")
    
    return {
        'icon_names': icon_names,
        'extracted_files': extracted_files,
        'mapping': mapping,
        'output_dir': output_dir
    }


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Extract and organize icons from Z21 file',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Extract all icons
  %(prog)s z21_new.z21
  
  # Extract to specific directory
  %(prog)s z21_new.z21 -o ./my_icons
  
  # Analyze PNG structure
  %(prog)s z21_new.z21 --analyze
        """
    )
    parser.add_argument('file', type=Path, help='Z21 file to extract icons from')
    parser.add_argument('-o', '--output', type=Path, 
                       help='Output directory for extracted icons')
    parser.add_argument('--analyze', action='store_true',
                       help='Analyze PNG file structure')
    
    args = parser.parse_args()
    
    if not args.file.exists():
        print(f"Error: File not found: {args.file}")
        sys.exit(1)
    
    try:
        extract_icons(args.file, args.output, args.analyze)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

