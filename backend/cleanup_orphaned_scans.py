#!/usr/bin/env python3
"""
Cleanup script to remove orphaned XML files that don't correspond to database records
"""
import os
import sqlite3
import glob

def cleanup_orphaned_scans():
    """Remove XML files that don't have corresponding database records"""
    db_path = 'instance/sentinelzero.db'
    scans_dir = 'scans'
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return False
    
    try:
        # Get all XML files in scans directory
        xml_files = glob.glob(os.path.join(scans_dir, '*.xml'))
        print(f"Found {len(xml_files)} XML files in {scans_dir}")
        
        # Get all XML paths from database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT raw_xml_path FROM scan WHERE raw_xml_path IS NOT NULL")
        db_xml_paths = {row[0] for row in cursor.fetchall()}
        conn.close()
        
        print(f"Found {len(db_xml_paths)} XML paths in database")
        
        # Find orphaned files
        orphaned_files = []
        for xml_file in xml_files:
            # Normalize path for comparison
            normalized_path = xml_file.replace('\\', '/')
            if normalized_path not in db_xml_paths:
                # Also check if it's a small/incomplete file
                try:
                    file_size = os.path.getsize(xml_file)
                    if file_size < 1000:  # Less than 1KB indicates incomplete scan
                        orphaned_files.append((xml_file, file_size))
                        print(f"Orphaned incomplete file: {xml_file} ({file_size} bytes)")
                    else:
                        print(f"Orphaned complete file: {xml_file} ({file_size} bytes)")
                        orphaned_files.append((xml_file, file_size))
                except Exception as e:
                    print(f"Error checking file {xml_file}: {e}")
        
        if not orphaned_files:
            print("No orphaned files found")
            return True
        
        print(f"\nFound {len(orphaned_files)} orphaned files:")
        for file_path, file_size in orphaned_files:
            print(f"  - {file_path} ({file_size} bytes)")
        
        # Ask for confirmation
        response = input(f"\nRemove {len(orphaned_files)} orphaned files? (y/N): ")
        if response.lower() in ['y', 'yes']:
            removed_count = 0
            for file_path, file_size in orphaned_files:
                try:
                    os.remove(file_path)
                    print(f"Removed: {file_path}")
                    removed_count += 1
                except Exception as e:
                    print(f"Error removing {file_path}: {e}")
            
            print(f"Successfully removed {removed_count} orphaned files")
            return True
        else:
            print("Cleanup cancelled")
            return False
            
    except Exception as e:
        print(f"Error during cleanup: {e}")
        return False

if __name__ == '__main__':
    success = cleanup_orphaned_scans()
    exit(0 if success else 1)
