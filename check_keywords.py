from app.models.db import get_connection
import json
import re
from collections import Counter

def _extract_keywords_from_text(text: str):
    text = (text or "").strip()
    if not text:
        return []
    tokens = re.findall(r'[\u4e00-\u9fa5]{2,8}|[a-zA-Z]{3,}', text)
    stop_words = {"的是", "一个", "一些", "这个", "那个", "什么", "怎么", "为什么", "可以", "可能", "已经", "没有", "不是", "就是", "还是", "这样", "这样", "我们", "你们", "他们", "自己", "这个", "那个", "这些", "那些", "这里", "那里", "现在", "今天", "明天", "昨天", "已经", "正在", "正在", "进行", "通过", "根据", "关于", "对于", "因为", "所以", "但是", "如果", "虽然", "然而", "因此", "而且", "并且", "或者", "以及", "还有", "包括", "除了", "之外", "以上", "以下", "以下", "之间", "之间", "之后", "之前", "其中", "其他", "其他", "另外", "此外", "同时", "然后", "最后", "首先", "其次", "再次", "最后", "最终", "结果", "表示", "显示", "说明", "认为", "指出", "强调", "表示", "表示", "表示", "表示"}
    return [t for t in tokens if t not in stop_words and len(t) >= 2]

conn = get_connection()

# 获取用户对话消息
rows = conn.execute(
    """
    select content_text
    from user_chat_messages
    where role='user' and content_text is not null and content_text <> ''
    order by id desc
    limit 400
    """
).fetchall()

print(f'Found {len(rows)} user messages')

all_keywords = []
for row in rows:
    content = (row["content_text"] or "").strip()
    if content:
        keywords = _extract_keywords_from_text(content)
        all_keywords.extend(keywords)
        if len(all_keywords) >= 200:
            break

print(f'Extracted {len(all_keywords)} keywords')

word_counts = Counter(all_keywords)
result = [{"word": word, "value": count} for word, count in word_counts.most_common(20)]

print('\nTop 20 keywords:')
for item in result:
    print(f'  {item["word"]}: {item["value"]}')
