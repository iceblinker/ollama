import sqlite3
import sys

db_path = '/app/temp_catalog_unlocked.db'
print(f"Inspecting {db_path}...")

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print("TABLES_FOUND:", tables)
except Exception as e:
    print(e)
