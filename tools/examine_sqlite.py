#!/usr/bin/env python3
"""Examine SQLite database in Z21 file."""

import zipfile
import sqlite3
import sys
from pathlib import Path


def examine_z21_sqlite(z21_file: Path):
    """Extract and examine SQLite database from Z21 file."""
    with zipfile.ZipFile(z21_file, 'r') as zf:
        # Find SQLite file
        sqlite_files = [f for f in zf.namelist() if f.endswith('.sqlite')]
        if not sqlite_files:
            print("No SQLite database found in ZIP file")
            return
        
        sqlite_file = sqlite_files[0]
        print(f"Found SQLite database: {sqlite_file}")
        
        # Extract to temporary location
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix='.sqlite') as tmp:
            tmp.write(zf.read(sqlite_file))
            tmp_path = tmp.name
        
        try:
            # Connect to database
            db = sqlite3.connect(tmp_path)
            cursor = db.cursor()
            
            # List tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            print(f"\nTables: {tables}")
            
            # Show schema for each table
            for table in tables:
                print(f"\n--- Table: {table} ---")
                cursor.execute(f"PRAGMA table_info({table})")
                columns = cursor.fetchall()
                print("Columns:")
                for col in columns:
                    print(f"  {col[1]} ({col[2]})")
                
                # Show row count
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                print(f"Row count: {count}")
                
                # Show sample data
                if count > 0:
                    cursor.execute(f"SELECT * FROM {table} LIMIT 3")
                    rows = cursor.fetchall()
                    print("Sample rows:")
                    for row in rows:
                        print(f"  {row}")
            
            db.close()
        finally:
            # Clean up
            Path(tmp_path).unlink()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <z21_file>")
        sys.exit(1)
    
    examine_z21_sqlite(Path(sys.argv[1]))

