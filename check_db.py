import sqlite3, datetime
conn = sqlite3.connect('database/app.db')
conn.row_factory = sqlite3.Row

# Check current SQLite time vs actual time
r = conn.execute("select datetime('now') as utc_now, datetime('now','localtime') as local_now").fetchone()
print(f"UTC now (SQLite):  {r['utc_now']}")
print(f"Local now (SQLite): {r['local_now']}")
print(f"Python now (local): {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Python now (UTC):   {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")

# Check a recent record
r2 = conn.execute("select id, create_at, update_at from api_endpoints order by id desc limit 1").fetchone()
if r2:
    print(f"\nLatest api_endpoint: create_at={r2['create_at']}, update_at={r2['update_at']}")

r3 = conn.execute("select id, create_at, update_at from digital_employees order by id desc limit 1").fetchone()
if r3:
    print(f"Latest employee: create_at={r3['create_at']}, update_at={r3['update_at']}")