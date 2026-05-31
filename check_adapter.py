from app.models.db import get_connection
conn = get_connection()
cursor = conn.execute("SELECT count(*) FROM users")
print("Users via adapter:", cursor.fetchone()[0])
if hasattr(conn, 'close'):
    conn.close()
