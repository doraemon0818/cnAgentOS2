import sqlite3
conn = sqlite3.connect(r'd:\Projects\shixun\day4\aiAgentOS\database\app.db')
row = conn.execute("SELECT id, name, code, url FROM functions WHERE code='system_database_config'").fetchone()
if row:
    print(f"Menu added: ID={row[0]}, Name={row[1]}, URL={row[3]}")
else:
    print("Menu not found!")
conn.close()
