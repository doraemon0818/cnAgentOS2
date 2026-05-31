import sqlite3
conn = sqlite3.connect(r'd:\Projects\shixun\day4\aiAgentOS\database\app.db')
cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cursor.fetchall()]
print("Tables:", tables)
if 'users' in tables:
    count = conn.execute("SELECT count(*) FROM users").fetchone()[0]
    print(f"Users: {count}")
else:
    print("users table not found!")
conn.close()
