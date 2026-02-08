"""
Database Initialization Script
Run this once to set up the MySQL database
"""

import os
import sys
from pathlib import Path
from urllib.parse import urlparse, unquote

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app import app
from database import db, init_db
from dotenv import load_dotenv
import pymysql

# Load environment variables
load_dotenv()

def create_database_if_not_exists():
    """Create the database if it doesn't exist"""
    db_url = os.getenv('DATABASE_URL')
    parsed = urlparse(db_url)
    
    # Extract connection details
    user = parsed.username
    password = unquote(parsed.password) if parsed.password else ''
    host = parsed.hostname
    port = parsed.port or 3306
    db_name = parsed.path.lstrip('/')
    
    try:
        # Connect to MySQL without specifying database
        conn = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password
        )
        cursor = conn.cursor()
        
        # Create database if not exists
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"[CHECK] Database '{db_name}' ready")
        return True
    except Exception as e:
        print(f"[ERROR] Error creating database: {e}")
        return False

def setup_database():
    """Initialize and set up the database"""
    print("="*70)
    print("GESTURE-EASE DATABASE SETUP")
    print("="*70)
    
    # Check environment variables
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        print("[ERROR] DATABASE_URL not found in .env file")
        print("\n[MEMO] Setup Instructions:")
        print("1. Copy .env.example to .env")
        print("2. Update database credentials in .env")
        print("3. Make sure MySQL is running")
        print("4. Run this script again")
        return False
    
    print(f"\n[CHECK] Database URL: {db_url}")
    
    # Create database if it doesn't exist
    if not create_database_if_not_exists():
        return False
    
    # Initialize database
    try:
        print("\n🔄 Creating database tables...")
        init_db(app)
        print("[CHECK] Database tables created successfully!")
        
        print("\n[BAR_CHART] Database Schema:")
        print("   - users: User accounts and authentication")
        print("   - user_progress: Word-level progress tracking")
        print("   - gesture_attempts: Individual attempt logs")
        print("   - leaderboard: Pre-calculated rankings")
        
        print("\n" + "="*70)
        print("[CHECK] DATABASE SETUP COMPLETE!")
        print("="*70)
        print("\nYou can now start the Flask server with:")
        print("   python app.py")
        
        return True
        
    except Exception as e:
        print(f"\n[ERROR] Error setting up database: {e}")
        print("\n[TOOLS] Troubleshooting:")
        print("   - Ensure MySQL server is running")
        print("   - Check database credentials in .env")
        print("   - Verify the database connection URL")
        return False

if __name__ == '__main__':
    success = setup_database()
    sys.exit(0 if success else 1)
