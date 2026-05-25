from app.models.db import get_connection

conn = get_connection()

total = conn.execute('select count(*) as total from user_chat_messages').fetchone()['total']
user_count = conn.execute("select count(*) as total from user_chat_messages where role='user'").fetchone()['total']

print(f'Total messages: {total}')
print(f'User messages: {user_count}')

rows = conn.execute('select role, content_text from user_chat_messages order by id desc limit 5').fetchall()
print('Last 5 messages:')
for r in rows:
    content = r[1][:50] if r[1] else ''
    print(f'  role={r[0]}, content={content}...')
