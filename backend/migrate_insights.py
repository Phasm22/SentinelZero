#!/usr/bin/env python3
"""
Database migration to add insights_json column to Scan model
"""
import os
import sys
import sqlite3
from datetime import datetime

# Add the backend directory to Python path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

def migrate_database():
    """Add insights_json column to scans table if it doesn't exist"""
    
    # Database path
    instance_dir = os.path.join(backend_dir, 'instance')
    db_path = os.path.join(instance_dir, 'sentinelzero.db')
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        print("Run the app first to create the database.")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if insights_json column exists
        cursor.execute("PRAGMA table_info(scan)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'insights_json' not in columns:
            print("Adding insights_json column to scan table...")
            cursor.execute("ALTER TABLE scan ADD COLUMN insights_json TEXT")
            conn.commit()
            print("✅ Successfully added insights_json column")
        else:
            print("✅ insights_json column already exists")
        
        # Show table structure
        cursor.execute("PRAGMA table_info(scan)")
        columns = cursor.fetchall()
        print("\nCurrent scan table structure:")
        for col in columns:
            print(f"  {col[1]} ({col[2]})")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error migrating database: {e}")
        if 'conn' in locals():
            conn.close()

if __name__ == '__main__':
    print("SentinelZero Database Migration - Adding Insights Support")
    print("=" * 60)
    migrate_database()
    print("Migration complete!")
