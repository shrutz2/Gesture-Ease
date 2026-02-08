import os
import pymysql
from urllib.parse import urlparse, unquote
from dotenv import load_dotenv

load_dotenv()

db_url = os.getenv('DATABASE_URL')
parsed = urlparse(db_url)

user = parsed.username
password = unquote(parsed.password) if parsed.password else ''
host = parsed.hostname
port = parsed.port or 3306
db_name = parsed.path.lstrip('/')

try:
    conn = pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=db_name
    )
    cursor = conn.cursor()
    
    print(f"\n[CHECK] Connected to database: {db_name}\n")
    
    # Get all tables
    cursor.execute("SHOW TABLES")
    tables = cursor.fetchall()
    
    print("[BAR_CHART] Tables in database:")
    for table in tables:
        table_name = table[0]
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        print(f"   - {table_name}: {count} rows")
    
    # Show table structures
    print("\n[CLIPBOARD] Table Structures:")
    for table in tables:
        table_name = table[0]
        cursor.execute(f"DESCRIBE {table_name}")
        columns = cursor.fetchall()
        print(f"\n   {table_name}:")
        for col in columns:
            print(f"      - {col[0]}: {col[1]}")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"[ERROR] Error: {e}")
