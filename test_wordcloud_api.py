import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.models.db import get_connection
import re
from collections import Counter

def _extract_keywords_from_text(text: str):
    text = (text or "").strip()
    if not text:
        return []
    tokens = re.findall(r'[\u4e00-\u9fa5]{2,8}|[a-zA-Z]{3,}', text)
    stop_words = {"的是", "一个", "一些", "这个", "那个", "什么", "怎么", "为什么", "可以", "可能", "已经", "没有", "不是", "就是", "还是", "这样", "这样", "我们", "你们", "他们", "自己", "这个", "那个", "这些", "那些", "这里", "那里", "现在", "今天", "明天", "昨天", "已经", "正在", "正在", "进行", "通过", "根据", "关于", "对于", "因为", "所以", "但是", "如果", "虽然", "然而", "因此", "而且", "并且", "或者", "以及", "还有", "包括", "除了", "之外", "以上", "以下", "以下", "之间", "之间", "之后", "之前", "其中", "其他", "其他", "另外", "此外", "同时", "然后", "最后", "首先", "其次", "再次", "最后", "最终", "结果", "表示", "显示", "说明", "认为", "指出", "强调", "表示", "表示", "表示", "表示"}
    return [t for t in tokens if t not in stop_words and len(t) >= 2]

# 模拟API调用
def get_wordcloud(limit=60):
    conn = get_connection()
    
    # 从用户对话内容提取关键词（优先）
    all_keywords = []
    
    # 获取用户对话消息
    rows = conn.execute(
        """
        select content_text
        from user_chat_messages
        where role='user' and content_text is not null and content_text <> ''
        order by id desc
        limit ?
        """,
        (limit * 2,),
    ).fetchall()
    
    print(f"Found {len(rows)} user messages")
    
    for row in rows:
        content = (row["content_text"] or "").strip()
        if content:
            keywords = _extract_keywords_from_text(content)
            all_keywords.extend(keywords)
            if len(all_keywords) >= limit:
                break
    
    print(f"Extracted {len(all_keywords)} keywords from chat")
    
    # 从瞭望采集数据提取关键词
    if len(all_keywords) < limit:
        from app.models.surveillance import SurveillanceRecordRepository
        page = 1
        while len(all_keywords) < limit:
            result = SurveillanceRecordRepository.get_record_list(page=page, page_size=50)
            records = result.get("list", [])
            if not records:
                break
            
            for r in records:
                kw = (r.get("keyword") or "").strip()
                if kw:
                    all_keywords.append(kw)
                
                title = (r.get("title") or "").strip()
                if title:
                    all_keywords.extend(_extract_keywords_from_text(title))
                
                summary = (r.get("summary") or "").strip()
                if summary:
                    all_keywords.extend(_extract_keywords_from_text(summary))
                
                if len(all_keywords) >= limit:
                    break
            
            if len(records) < 50:
                break
            page += 1
        
        print(f"Total keywords after surveillance: {len(all_keywords)}")
    
    # 统计词频
    word_counts = Counter(all_keywords)
    result = [{"word": word, "value": count} for word, count in word_counts.most_common(limit)]
    
    return {"code": 0, "msg": "", "data": result}

# 测试
result = get_wordcloud(60)
print(f"\nAPI Response:")
print(f"Code: {result['code']}")
print(f"Data count: {len(result['data'])}")
print("\nTop 10 keywords:")
for item in result['data'][:10]:
    print(f"  {item['word']}: {item['value']}")
