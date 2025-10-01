"""
IDMS Database Cleanup Script
Removes all data from the database except the admin user information.

Usage:
    python scripts/clean_database.py

WARNING: This will delete all documents, processing logs, and user data except the admin user!
"""

import sqlite3
import os
import sys
from datetime import datetime

# Add parent directory to path to import from app
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def get_confirmation():
    """Ask user for confirmation before proceeding"""
    print("\n" + "="*70)
    print("⚠️  DATABASE CLEANUP WARNING ⚠️")
    print("="*70)
    print("\nThis script will DELETE all data from the database except:")
    print("  ✓ Admin user (username: 'admin')")
    print("\nThe following data will be PERMANENTLY DELETED:")
    print("  ✗ All non-admin users")
    print("  ✗ All AI document classifications")
    print("  ✗ All GhostLayer documents")
    print("  ✗ All processing logs")
    print("  ✗ All system metrics")
    print("  ✗ All error logs")
    print("  ✗ All user sessions")
    print("  ✗ All configuration settings")
    print("="*70)
    
    response = input("\nAre you sure you want to proceed? (yes/no): ").strip().lower()
    return response == 'yes'

def clean_database(db_path: str):
    """Clean the database while preserving admin user"""
    
    if not os.path.exists(db_path):
        print(f"❌ Error: Database file not found at {db_path}")
        return False
    
    print(f"\n📁 Database location: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Disable foreign key constraints temporarily
        cursor.execute("PRAGMA foreign_keys = OFF")
        
        print("\n🧹 Starting database cleanup...")
        
        # Delete from tables (in order to respect dependencies)
        tables_to_clean = [
            ('processing_logs', 'Processing logs'),
            ('filenet_uploads', 'FileNet uploads'),
            ('system_metrics', 'System metrics'),
            ('error_logs', 'Error logs'),
            ('user_sessions', 'User sessions'),
            ('configuration', 'Configuration settings'),
            ('document_categories', 'Document categories'),
            ('criticality_levels', 'Criticality levels'),
            ('ai_document_classifications', 'AI document classifications'),
            ('user_ghostlayer_documents', 'User GhostLayer documents'),
            ('ghostlayer_documents', 'GhostLayer documents'),
            ('documents', 'Documents')
        ]
        
        deleted_counts = {}
        
        for table_name, display_name in tables_to_clean:
            try:
                # Get count before deletion
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count_before = cursor.fetchone()[0]
                
                # Delete all records
                cursor.execute(f"DELETE FROM {table_name}")
                deleted = cursor.rowcount
                deleted_counts[display_name] = deleted
                
                print(f"  ✓ Cleared {display_name}: {deleted} records deleted")
            except sqlite3.OperationalError as e:
                # Table might not exist
                print(f"  ⚠ Skipped {display_name}: {e}")
        
        # Delete non-admin users (keep only admin user with id=1)
        try:
            cursor.execute("SELECT COUNT(*) FROM users WHERE id != 1")
            non_admin_count = cursor.fetchone()[0]
            
            cursor.execute("DELETE FROM users WHERE id != 1")
            deleted_counts['Non-admin users'] = non_admin_count
            print(f"  ✓ Cleared non-admin users: {non_admin_count} users deleted")
            
            # Reset admin user's last login
            cursor.execute("UPDATE users SET last_login = NULL WHERE id = 1")
            print(f"  ✓ Reset admin user's last login timestamp")
        except sqlite3.OperationalError as e:
            print(f"  ⚠ Error cleaning users table: {e}")
        
        # Reset SQLite sequence numbers
        cursor.execute("DELETE FROM sqlite_sequence WHERE name != 'users'")
        cursor.execute("UPDATE sqlite_sequence SET seq = 1 WHERE name = 'users'")
        
        # Re-enable foreign key constraints
        cursor.execute("PRAGMA foreign_keys = ON")
        
        # Commit changes
        conn.commit()
        
        # Vacuum database to reclaim space
        print("\n🗜️  Optimizing database (VACUUM)...")
        cursor.execute("VACUUM")
        
        conn.close()
        
        # Print summary
        print("\n" + "="*70)
        print("✅ DATABASE CLEANUP COMPLETED SUCCESSFULLY")
        print("="*70)
        print("\nSummary:")
        total_deleted = sum(deleted_counts.values())
        for item, count in deleted_counts.items():
            print(f"  • {item}: {count} records deleted")
        print(f"\n📊 Total records deleted: {total_deleted}")
        print(f"✓ Admin user preserved")
        print(f"⏰ Cleanup completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70 + "\n")
        
        return True
        
    except sqlite3.Error as e:
        print(f"\n❌ Database error: {e}")
        return False
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        return False

def main():
    """Main function"""
    
    # Determine database path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    db_path = os.path.join(project_root, 'app', 'idms.db')
    
    print("\n" + "="*70)
    print("IDMS Database Cleanup Utility")
    print("="*70)
    
    # Check if database exists
    if not os.path.exists(db_path):
        print(f"\n❌ Error: Database not found at {db_path}")
        print("Please ensure the IDMS application has been run at least once to create the database.")
        return
    
    # Get confirmation
    if not get_confirmation():
        print("\n❌ Cleanup cancelled by user.")
        return
    
    # Perform cleanup
    success = clean_database(db_path)
    
    if success:
        print("✅ You can now restart the IDMS application with a clean database.")
        print("   Admin credentials remain: username='admin', password='admin123'\n")
    else:
        print("❌ Cleanup failed. Please check the error messages above.\n")

if __name__ == "__main__":
    main()

