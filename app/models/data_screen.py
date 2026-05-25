import json
from typing import Dict, List, Optional
from collections import Counter

from app.models.db import get_connection


def _safe_json_loads(value, default):
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


class DataScreenNodeRepository:
    @staticmethod
    def get_all_nodes():
        with get_connection() as conn:
            rows = conn.execute(
                """
                select id,name,code,lat,lng,category,value,extra_json,status,create_at,update_at
                from data_screen_nodes
                where status=1
                order by category, value desc
                """
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["extra"] = _safe_json_loads(item.get("extra_json"), {})
            result.append(item)
        return result

    @staticmethod
    def get_node_list(page=1, page_size=20, keyword="", category=""):
        offset = (page - 1) * page_size
        conditions = []
        params = []
        if keyword:
            like_value = f"%{keyword}%"
            conditions.append("(name like ? or code like ?)")
            params.extend([like_value, like_value])
        if category:
            conditions.append("category=?")
            params.append(category)

        where_sql = f"where {' and '.join(conditions)}" if conditions else ""
        sql = f"""
            select id,name,code,lat,lng,category,value,extra_json,status,create_at,update_at
            from data_screen_nodes
            {where_sql}
            order by value desc, id desc
            limit ? offset ?
        """
        count_sql = f"select count(*) as total from data_screen_nodes {where_sql}"

        with get_connection() as conn:
            rows = conn.execute(sql, tuple(params + [page_size, offset])).fetchall()
            total = conn.execute(count_sql, tuple(params)).fetchone()["total"]
        return {"list": [dict(row) for row in rows], "total": total}

    @staticmethod
    def save_node(data: Dict, node_id: Optional[int] = None):
        name = (data.get("name") or "").strip()
        code = (data.get("code") or "").strip()
        lat = float(data.get("lat") or 0)
        lng = float(data.get("lng") or 0)
        category = (data.get("category") or "default").strip()
        value = float(data.get("value") or 0)
        status = int(data.get("status") or 1)
        extra = data.get("extra") or {}

        if not name or not code:
            return False, "节点名称和编码不能为空"

        with get_connection() as conn:
            duplicate_sql = "select id from data_screen_nodes where code=?"
            duplicate_params = [code]
            if node_id:
                duplicate_sql += " and id<>?"
                duplicate_params.append(node_id)
            duplicate = conn.execute(duplicate_sql, tuple(duplicate_params)).fetchone()
            if duplicate:
                return False, "节点编码已存在"

            payload = (name, code, lat, lng, category, value, json.dumps(extra, ensure_ascii=False), status)

            if node_id:
                conn.execute(
                    """
                    update data_screen_nodes
                    set name=?,code=?,lat=?,lng=?,category=?,value=?,extra_json=?,status=?,update_at=datetime('now')
                    where id=?
                    """,
                    payload + (node_id,),
                )
            else:
                conn.execute(
                    """
                    insert into data_screen_nodes(
                        name,code,lat,lng,category,value,extra_json,status,create_at,update_at
                    ) values(?,?,?,?,?,?,?,?,datetime('now'),datetime('now'))
                    """,
                    payload,
                )
        return True, "保存成功"

    @staticmethod
    def delete_node(node_id: int):
        with get_connection() as conn:
            conn.execute("delete from data_screen_nodes where id=?", (node_id,))
        return True, "删除成功"


class DataScreenWordCloudRepository:
    @staticmethod
    def get_wordcloud(limit=80, source_type=""):
        conditions = []
        params = []
        if source_type:
            conditions.append("source_type=?")
            params.append(source_type)

        where_sql = f"where {' and '.join(conditions)}" if conditions else ""
        sql = f"""
            select word, sum(frequency) as total_frequency
            from data_screen_wordcloud
            {where_sql}
            group by word
            order by total_frequency desc
            limit ?
        """
        with get_connection() as conn:
            rows = conn.execute(sql, tuple(params + [limit])).fetchall()
        return [{"word": row["word"], "value": row["total_frequency"]} for row in rows]

    @staticmethod
    def add_word(word: str, frequency: int = 1, source_type: str = "chat", source_id: Optional[int] = None):
        word = (word or "").strip()
        if not word or len(word) < 2:
            return
        with get_connection() as conn:
            exists = conn.execute(
                "select id from data_screen_wordcloud where word=?", (word,)
            ).fetchone()
            if exists:
                conn.execute(
                    "update data_screen_wordcloud set frequency=frequency+? where id=?",
                    (frequency, exists["id"]),
                )
            else:
                conn.execute(
                    """
                    insert into data_screen_wordcloud(word,frequency,source_type,source_id,create_at)
                    values(?,?,?,?,datetime('now'))
                    """,
                    (word, frequency, source_type, source_id),
                )

    @staticmethod
    def batch_add_words(words: List[str], source_type: str = "chat", source_id: Optional[int] = None):
        word_counts = Counter(w.strip() for w in words if w and len(w.strip()) >= 2)
        with get_connection() as conn:
            for word, count in word_counts.items():
                exists = conn.execute(
                    "select id from data_screen_wordcloud where word=?", (word,)
                ).fetchone()
                if exists:
                    conn.execute(
                        "update data_screen_wordcloud set frequency=frequency+? where id=?",
                        (count, exists["id"]),
                    )
                else:
                    conn.execute(
                        """
                        insert into data_screen_wordcloud(word,frequency,source_type,source_id,create_at)
                        values(?,?,?,?,datetime('now'))
                        """,
                        (word, count, source_type, source_id),
                    )


class DataScreenStatsRepository:
    @staticmethod
    def get_dashboard_stats():
        with get_connection() as conn:
            user_count = conn.execute("select count(*) as total from users").fetchone()["total"]
            chat_session_count = conn.execute("select count(*) as total from user_chat_sessions").fetchone()["total"]
            chat_message_count = conn.execute("select count(*) as total from user_chat_messages").fetchone()["total"]
            surveillance_record_count = conn.execute("select count(*) as total from surveillance_records").fetchone()["total"]
            surveillance_source_count = conn.execute("select count(*) as total from surveillance_sources where status=1").fetchone()["total"]
            deep_detail_count = conn.execute("select count(*) as total from surveillance_record_details").fetchone()["total"]
            employee_count = conn.execute("select count(*) as total from digital_employees where status=1").fetchone()["total"]
            model_usage = conn.execute(
                "select coalesce(sum(total_tokens),0) as total_tokens, count(*) as total_calls from model_usage_logs"
            ).fetchone()
            im_message_count = conn.execute(
                "select (select count(*) from im_private_messages) + (select count(*) from im_group_messages) as total"
            ).fetchone()["total"]

        return {
            "user_count": user_count,
            "chat_session_count": chat_session_count,
            "chat_message_count": chat_message_count,
            "surveillance_record_count": surveillance_record_count,
            "surveillance_source_count": surveillance_source_count,
            "deep_detail_count": deep_detail_count,
            "employee_count": employee_count,
            "model_total_tokens": model_usage["total_tokens"],
            "model_total_calls": model_usage["total_calls"],
            "im_message_count": im_message_count,
        }

    @staticmethod
    def get_trend_data(days=7):
        with get_connection() as conn:
            rows = conn.execute(
                """
                select date(create_at) as stat_date, count(*) as cnt
                from surveillance_records
                where create_at >= date('now', ?)
                group by date(create_at)
                order by stat_date asc
                """,
                (f"-{days} days",),
            ).fetchall()

            chat_rows = conn.execute(
                """
                select date(create_at) as stat_date, count(*) as cnt
                from user_chat_messages
                where role='user' and create_at >= date('now', ?)
                group by date(create_at)
                order by stat_date asc
                """,
                (f"-{days} days",),
            ).fetchall()

        trend_map = {}
        for row in rows:
            trend_map[row["stat_date"]] = trend_map.get(row["stat_date"], {})
            trend_map[row["stat_date"]]["surveillance"] = row["cnt"]

        for row in chat_rows:
            if row["stat_date"] not in trend_map:
                trend_map[row["stat_date"]] = {}
            trend_map[row["stat_date"]]["chat"] = row["cnt"]

        result = []
        for i in range(days - 1, -1, -1):
            from datetime import date, timedelta
            d = (date.today() - timedelta(days=i)).isoformat()
            item = trend_map.get(d, {})
            result.append({
                "date": d,
                "surveillance": item.get("surveillance", 0),
                "chat": item.get("chat", 0),
            })
        return result

    @staticmethod
    def get_source_distribution():
        with get_connection() as conn:
            rows = conn.execute(
                """
                select source_name, count(*) as cnt
                from surveillance_records
                group by source_id, source_name
                order by cnt desc
                limit 10
                """
            ).fetchall()
        return [{"name": row["source_name"], "value": row["cnt"]} for row in rows]

    @staticmethod
    def get_keyword_top(limit=20):
        with get_connection() as conn:
            rows = conn.execute(
                """
                select keyword, count(*) as cnt
                from surveillance_records
                where keyword <> ''
                group by keyword
                order by cnt desc
                limit ?
                """,
                (limit,),
            ).fetchall()
        return [{"keyword": row["keyword"], "count": row["cnt"]} for row in rows]

    @staticmethod
    def get_sentiment_distribution():
        with get_connection() as conn:
            rows = conn.execute(
                """
                select ai_sentiment, count(*) as cnt
                from surveillance_record_details
                where ai_sentiment <> ''
                group by ai_sentiment
                order by cnt desc
                """
            ).fetchall()
        return [{"sentiment": row["ai_sentiment"], "count": row["cnt"]} for row in rows]
