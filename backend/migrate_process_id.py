#!/usr/bin/env python3
"""
Migration script to add process_id column to Scan table
"""
import sqlite3
import os
import sys

def migrate_database():
    """Add process_id column to Scan table"""
    db_path = 'instance/sentinelzero.db'
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if process_id column already exists
        cursor.execute("PRAGMA table_info(scan)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'process_id' in columns:
            print("process_id column already exists")
            return True
        
        # Add process_id column
        cursor.execute("ALTER TABLE scan ADD COLUMN process_id INTEGER")
        conn.commit()
        
        print("Successfully added process_id column to Scan table")
        return True
        
    except Exception as e:
        print(f"Error migrating database: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == '__main__':
    success = migrate_database()
    sys.exit(0 if success else 1)
