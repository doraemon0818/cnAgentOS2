import json
import re
from collections import Counter

import tornado.web

from app.controllers.admin import AdminBaseHandler
from app.models.data_screen import (
    DataScreenNodeRepository,
    DataScreenStatsRepository,
    DataScreenWordCloudRepository,
)
from app.models.model_engine import ModelEngineClient, ModelEngineRepository
from app.models.surveillance import SurveillanceRecordRepository
from app.models.im import IMRepository
from app.models.user_chat import UserChatSessionRepository


class AdminDataScreenHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        self.render("admin/data_screen.html", title="数智大屏", username=self.current_user)


class AdminDataScreenApiHandler(AdminBaseHandler):
    def _write_json(self, data):
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(data, ensure_ascii=False))

    @tornado.web.authenticated
    def get(self):
        action = self.get_argument("action", "")

        if action == "stats":
            self._write_json({"code": 0, "msg": "", "data": DataScreenStatsRepository.get_dashboard_stats()})
            return

        if action == "trend":
            days = int(self.get_argument("days", 7))
            self._write_json({"code": 0, "msg": "", "data": DataScreenStatsRepository.get_trend_data(days=days)})
            return

        if action == "source_distribution":
            self._write_json({"code": 0, "msg": "", "data": DataScreenStatsRepository.get_source_distribution()})
            return

        if action == "keyword_top":
            limit = int(self.get_argument("limit", 20))
            self._write_json({"code": 0, "msg": "", "data": DataScreenStatsRepository.get_keyword_top(limit=limit)})
            return

        if action == "sentiment_distribution":
            self._write_json({"code": 0, "msg": "", "data": DataScreenStatsRepository.get_sentiment_distribution()})
            return

        if action == "wordcloud":
            limit = int(self.get_argument("limit", 80))
            source_type = self.get_argument("source_type", "")
            
            # 实时从用户对话和瞭望数据提取关键词生成词云
            all_keywords = []
            
            # 从用户对话内容提取关键词（优先）
            chat_keywords = self._get_chat_keywords(limit=200)
            all_keywords.extend(chat_keywords)
            
            # 从瞭望采集数据提取关键词
            if len(all_keywords) < limit:
                surveillance_keywords = self._get_surveillance_keywords(limit=200)
                all_keywords.extend(surveillance_keywords)
            
            # 统计词频
            word_counts = Counter(all_keywords)
            result = [{"word": word, "value": count} for word, count in word_counts.most_common(limit)]
            
            self._write_json({"code": 0, "msg": "", "data": result})
            return

        if action == "nodes":
            self._write_json({"code": 0, "msg": "", "data": DataScreenNodeRepository.get_all_nodes()})
            return

        if action == "node_list":
            page = int(self.get_argument("page", 1))
            limit = int(self.get_argument("limit", 20))
            keyword = (self.get_argument("keyword", "") or "").strip()
            category = self.get_argument("category", "")
            result = DataScreenNodeRepository.get_node_list(page=page, page_size=limit, keyword=keyword, category=category)
            self._write_json({"code": 0, "msg": "", "count": result["total"], "data": result["list"]})
            return

        self._write_json({"code": 1, "msg": "未知操作"})

    @tornado.web.authenticated
    def post(self):
        action = self.get_argument("action", "")

        if action == "node_add":
            payload = {
                "name": self.get_body_argument("name", ""),
                "code": self.get_body_argument("code", ""),
                "lat": self.get_body_argument("lat", "0"),
                "lng": self.get_body_argument("lng", "0"),
                "category": self.get_body_argument("category", "default"),
                "value": self.get_body_argument("value", "0"),
                "status": self.get_body_argument("status", "1"),
                "extra": {},
            }
            success, message = DataScreenNodeRepository.save_node(payload)
            self._write_json({"code": 0 if success else 1, "msg": message})
            return

        if action == "node_update":
            node_id = int(self.get_body_argument("id", 0))
            payload = {
                "name": self.get_body_argument("name", ""),
                "code": self.get_body_argument("code", ""),
                "lat": self.get_body_argument("lat", "0"),
                "lng": self.get_body_argument("lng", "0"),
                "category": self.get_body_argument("category", "default"),
                "value": self.get_body_argument("value", "0"),
                "status": self.get_body_argument("status", "1"),
                "extra": {},
            }
            success, message = DataScreenNodeRepository.save_node(payload, node_id=node_id)
            self._write_json({"code": 0 if success else 1, "msg": message})
            return

        if action == "node_delete":
            node_id = int(self.get_body_argument("id", 0))
            success, message = DataScreenNodeRepository.delete_node(node_id)
            self._write_json({"code": 0 if success else 1, "msg": message})
            return

        if action == "refresh_wordcloud":
            self._refresh_wordcloud_from_data()
            self._write_json({"code": 0, "msg": "词云数据已刷新"})
            return

        self._write_json({"code": 1, "msg": "未知操作"})

    def _refresh_wordcloud_from_data(self):
        all_keywords = []
        # 从瞭望采集数据提取关键词
        with_limit = 300
        page = 1
        while len(all_keywords) < with_limit:
            result = SurveillanceRecordRepository.get_record_list(page=page, page_size=100)
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
            if len(records) < 100:
                break
            page += 1

        DataScreenWordCloudRepository.batch_add_words(all_keywords[:with_limit], source_type="surveillance")

        # 从用户对话内容提取关键词
        chat_keywords = []
        chat_limit = 300
        chat_page = 1
        while len(chat_keywords) < chat_limit:
            result = self._get_chat_messages(page=chat_page, page_size=100)
            messages = result.get("list", [])
            if not messages:
                break
            for m in messages:
                content = (m.get("content_text") or "").strip()
                if content:
                    chat_keywords.extend(_extract_keywords_from_text(content))
            if len(messages) < 100:
                break
            chat_page += 1

        DataScreenWordCloudRepository.batch_add_words(chat_keywords[:chat_limit], source_type="chat")

    def _get_chat_keywords(self, limit=200):
        """从用户对话内容实时提取关键词"""
        from app.models.db import get_connection
        keywords = []
        
        # 获取最近的用户对话消息
        with get_connection() as conn:
            rows = conn.execute(
                """
                select content_text
                from user_chat_messages
                where role='user' and content_text is not null and content_text <> ''
                order by id desc
                limit ?
                """,
                (limit * 2,),  # 获取更多消息以确保有足够的关键词
            ).fetchall()
        
        for row in rows:
            content = (row["content_text"] or "").strip()
            if content:
                keywords.extend(_extract_keywords_from_text(content))
            if len(keywords) >= limit:
                break
        
        return keywords[:limit]

    def _get_surveillance_keywords(self, limit=200):
        """从瞭望采集数据实时提取关键词"""
        keywords = []
        page = 1
        
        while len(keywords) < limit:
            result = SurveillanceRecordRepository.get_record_list(page=page, page_size=50)
            records = result.get("list", [])
            if not records:
                break
            
            for r in records:
                # 直接使用已有关键词
                kw = (r.get("keyword") or "").strip()
                if kw:
                    keywords.append(kw)
                
                # 从标题提取
                title = (r.get("title") or "").strip()
                if title:
                    keywords.extend(_extract_keywords_from_text(title))
                
                # 从摘要提取
                summary = (r.get("summary") or "").strip()
                if summary:
                    keywords.extend(_extract_keywords_from_text(summary))
                
                if len(keywords) >= limit:
                    break
            
            if len(records) < 50:
                break
            page += 1
        
        return keywords[:limit]

    def _get_chat_messages(self, page=1, page_size=100):
        from app.models.db import get_connection
        offset = (page - 1) * page_size
        with get_connection() as conn:
            rows = conn.execute(
                """
                select id,session_id,role,content_text,content_markdown,create_at
                from user_chat_messages
                where role='user'
                order by id desc
                limit ? offset ?
                """,
                (page_size, offset),
            ).fetchall()
            total = conn.execute(
                "select count(*) as total from user_chat_messages where role='user'"
            ).fetchone()["total"]
        return {"list": [dict(row) for row in rows], "total": total}


def _extract_keywords_from_text(text: str):
    text = (text or "").strip()
    if not text:
        return []
    tokens = re.findall(r'[\u4e00-\u9fa5]{2,8}|[a-zA-Z]{3,}', text)
    stop_words = {"的是", "一个", "一些", "这个", "那个", "什么", "怎么", "为什么", "可以", "可能", "已经", "没有", "不是", "就是", "还是", "这样", "这样", "我们", "你们", "他们", "自己", "这个", "那个", "这些", "那些", "这里", "那里", "现在", "今天", "明天", "昨天", "已经", "正在", "正在", "进行", "通过", "根据", "关于", "对于", "因为", "所以", "但是", "如果", "虽然", "然而", "因此", "而且", "并且", "或者", "以及", "还有", "包括", "除了", "之外", "以上", "以下", "以下", "之间", "之间", "之后", "之前", "其中", "其他", "其他", "另外", "此外", "同时", "然后", "最后", "首先", "其次", "再次", "最后", "最终", "结果", "表示", "显示", "说明", "认为", "指出", "强调", "表示", "表示", "表示", "表示"}
    return [t for t in tokens if t not in stop_words and len(t) >= 2]


class AdminOpinionListHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        self.render("admin/opinion/list.html", title="智能舆情", username=self.current_user)


class AdminOpinionApiHandler(AdminBaseHandler):
    def _write_json(self, data):
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(data, ensure_ascii=False))

    @tornado.web.authenticated
    def get(self):
        action = self.get_argument("action", "")

        if action == "list":
            page = int(self.get_argument("page", 1))
            limit = int(self.get_argument("limit", 20))
            keyword = (self.get_argument("keyword", "") or "").strip()
            sentiment = self.get_argument("sentiment", "")
            result = self._get_opinion_list(page=page, page_size=limit, keyword=keyword, sentiment=sentiment)
            self._write_json({"code": 0, "msg": "", "count": result["total"], "data": result["list"]})
            return

        if action == "detail":
            opinion_id = int(self.get_argument("id", 0))
            data = self._get_opinion_by_id(opinion_id)
            if not data:
                self._write_json({"code": 1, "msg": "舆情分析不存在"})
                return
            self._write_json({"code": 0, "msg": "", "data": data})
            return

        if action == "stats":
            self._write_json({"code": 0, "msg": "", "data": self._get_opinion_stats()})
            return

        self._write_json({"code": 1, "msg": "未知操作"})

    @tornado.web.authenticated
    def post(self):
        action = self.get_argument("action", "")

        if action == "analyze":
            self._write_json({"code": 1, "msg": "请使用 analyze_stream 接口"})
            return

        if action == "delete":
            opinion_id = int(self.get_body_argument("id", 0))
            self._delete_opinion(opinion_id)
            self._write_json({"code": 0, "msg": "删除成功"})
            return

        self._write_json({"code": 1, "msg": "未知操作"})

    def _get_opinion_list(self, page=1, page_size=20, keyword="", sentiment=""):
        from app.models.db import get_connection
        offset = (page - 1) * page_size
        conditions = []
        params = []
        if keyword:
            like_value = f"%{keyword}%"
            conditions.append("(title like ? or content like ?)")
            params.extend([like_value, like_value])
        if sentiment:
            conditions.append("sentiment=?")
            params.append(sentiment)

        where_sql = f"where {' and '.join(conditions)}" if conditions else ""
        sql = f"""
            select id,title,content,sentiment,score,keywords_json,source_type,source_ids_json,model_name,status,create_at,update_at
            from public_opinion_analysis
            {where_sql}
            order by create_at desc
            limit ? offset ?
        """
        count_sql = f"select count(*) as total from public_opinion_analysis {where_sql}"

        with get_connection() as conn:
            rows = conn.execute(sql, tuple(params + [page_size, offset])).fetchall()
            total = conn.execute(count_sql, tuple(params)).fetchone()["total"]

        result = []
        for row in rows:
            item = dict(row)
            item["keywords"] = _safe_json_loads(item.get("keywords_json"), [])
            item["source_ids"] = _safe_json_loads(item.get("source_ids_json"), [])
            result.append(item)
        return {"list": result, "total": total}

    def _get_opinion_by_id(self, opinion_id: int):
        from app.models.db import get_connection
        with get_connection() as conn:
            row = conn.execute(
                "select * from public_opinion_analysis where id=?", (opinion_id,)
            ).fetchone()
        if not row:
            return None
        item = dict(row)
        item["keywords"] = _safe_json_loads(item.get("keywords_json"), [])
        item["source_ids"] = _safe_json_loads(item.get("source_ids_json"), [])
        return item

    def _get_opinion_stats(self):
        from app.models.db import get_connection
        with get_connection() as conn:
            total = conn.execute("select count(*) as total from public_opinion_analysis").fetchone()["total"]
            positive = conn.execute(
                "select count(*) as cnt from public_opinion_analysis where sentiment='正向'"
            ).fetchone()["cnt"]
            negative = conn.execute(
                "select count(*) as cnt from public_opinion_analysis where sentiment='负向'"
            ).fetchone()["cnt"]
            neutral = conn.execute(
                "select count(*) as cnt from public_opinion_analysis where sentiment='中性'"
            ).fetchone()["cnt"]
            avg_score = conn.execute(
                "select coalesce(avg(score),0) as avg_score from public_opinion_analysis"
            ).fetchone()["avg_score"]
        return {
            "total": total,
            "positive": positive or 0,
            "negative": negative or 0,
            "neutral": neutral or 0,
            "avg_score": round(avg_score or 0, 2),
        }

    def _delete_opinion(self, opinion_id: int):
        from app.models.db import get_connection
        with get_connection() as conn:
            conn.execute("delete from public_opinion_analysis where id=?", (opinion_id,))


class AdminOpinionAnalyzeStreamHandler(AdminBaseHandler):
    @tornado.web.authenticated
    async def get(self):
        self.set_header("Content-Type", "text/event-stream; charset=utf-8")
        self.set_header("Cache-Control", "no-cache")
        self.set_header("Connection", "keep-alive")
        await self.flush()

        try:
            async for item in OpinionAnalysisService.stream_analyze():
                self.write("data: " + json.dumps(item, ensure_ascii=False) + "\n\n")
                await self.flush()
        except Exception as exc:
            self.write("data: " + json.dumps({"type": "error", "message": str(exc)}, ensure_ascii=False) + "\n\n")
            await self.flush()


def _safe_json_loads(value, default):
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


class OpinionAnalysisService:
    @staticmethod
    def _collect_data_for_analysis():
        """从智能问数聊天和子系统聊天中提取内容进行分析"""
        from app.models.db import get_connection
        records = []
        
        # 1. 从智能问数页面聊天内容提取（user_chat_messages）
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    """
                    select id, content_text, session_id, create_at
                    from user_chat_messages
                    where role='user' and content_text is not null and content_text <> ''
                    order by id desc
                    limit 50
                    """
                ).fetchall()
                
                for row in rows:
                    content = (row["content_text"] or "").strip()
                    if content:
                        records.append({
                            "id": f"chat_{row['id']}",
                            "title": content[:50],
                            "summary": content[:200],
                            "keyword": "",
                            "source_name": "智能问数",
                        })
        except Exception as e:
            print(f"获取智能问数聊天数据失败: {e}")
        
        # 2. 从子系统聊天内容提取（im_private_messages + im_group_messages）
        try:
            with get_connection() as conn:
                # 私聊消息
                try:
                    private_rows = conn.execute(
                        """
                        select id, content_text, sender_user_id, create_at
                        from im_private_messages
                        where content_type='text' and content_text is not null and content_text <> ''
                        order by id desc
                        limit 30
                        """
                    ).fetchall()
                    
                    for row in private_rows:
                        content = (row["content_text"] or "").strip()
                        if content:
                            records.append({
                                "id": f"private_{row['id']}",
                                "title": content[:50],
                                "summary": content[:200],
                                "keyword": "",
                                "source_name": "私聊",
                            })
                except Exception as e:
                    print(f"获取私聊数据失败: {e}")
                
                # 群聊消息
                try:
                    group_rows = conn.execute(
                        """
                        select id, content_text, group_id, create_at
                        from im_group_messages
                        where content_type='text' and content_text is not null and content_text <> ''
                        order by id desc
                        limit 20
                        """
                    ).fetchall()
                    
                    for row in group_rows:
                        content = (row["content_text"] or "").strip()
                        if content:
                            records.append({
                                "id": f"group_{row['id']}",
                                "title": content[:50],
                                "summary": content[:200],
                                "keyword": "",
                                "source_name": "群聊",
                            })
                except Exception as e:
                    print(f"获取群聊数据失败: {e}")
        except Exception as e:
            print(f"获取子系统聊天数据失败: {e}")
        
        return records

    @staticmethod
    def _build_analysis_prompt(records: list):
        data_text = ""
        for i, r in enumerate(records[:30], 1):
            data_text += f"{i}. [{r['source_name']}] {r['title']}\n"
            if r.get("summary"):
                data_text += f"   摘要: {r['summary'][:200]}\n"
            if r.get("keyword"):
                data_text += f"   关键字: {r['keyword']}\n"
            data_text += "\n"

        prompt = f"""
你是智能舆情分析助手，请基于以下采集的数据进行综合分析。

数据列表：
{data_text}

请输出严格JSON：
{{
  "title": "舆情分析标题（不超过30字）",
  "content": "综合分析内容（不超过500字的Markdown格式文本）",
  "sentiment": "正向/中性/负向",
  "score": 0,
  "keywords": ["关键词1", "关键词2", "关键词3"],
  "summary": "一句话总结（不超过50字）"
}}

要求：
1. sentiment 为整体舆情倾向
2. score 为 0-100 的舆情健康度评分（越高越正面）
3. keywords 提取3-5个核心关键词
4. content 需要包含趋势分析、热点话题、风险预警等内容
""".strip()
        return prompt

    @staticmethod
    def _normalize_analysis(content: str):
        content = (content or "").strip()
        content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.I)
        content = re.sub(r"\s*```$", "", content)

        try:
            data = json.loads(content)
        except Exception:
            match = re.search(r"\{[\s\S]*\}", content)
            if match:
                try:
                    data = json.loads(match.group(0))
                except Exception:
                    data = {}
            else:
                data = {}

        if not isinstance(data, dict):
            data = {}

        keywords = data.get("keywords") if isinstance(data.get("keywords"), list) else []
        return {
            "title": str(data.get("title") or "舆情分析报告").strip()[:50],
            "content": str(data.get("content") or "").strip()[:2000],
            "sentiment": str(data.get("sentiment") or "中性").strip()[:10],
            "score": max(0, min(100, int(float(data.get("score") or 0)))),
            "keywords": [str(k).strip()[:30] for k in keywords if str(k).strip()][:5],
        }

    @staticmethod
    def _save_analysis(analysis: dict, model_name: str, source_ids: list):
        from app.models.db import get_connection
        with get_connection() as conn:
            cursor = conn.execute(
                """
                insert into public_opinion_analysis(
                    title,content,sentiment,score,keywords_json,source_type,source_ids_json,model_name,status,create_at,update_at
                ) values(?,?,?,?,?,'auto',?,?,1,datetime('now','localtime'),datetime('now','localtime'))
                """,
                (
                    analysis["title"],
                    analysis["content"],
                    analysis["sentiment"],
                    analysis["score"],
                    json.dumps(analysis["keywords"], ensure_ascii=False),
                    json.dumps(source_ids, ensure_ascii=False),
                    model_name,
                ),
            )
            return cursor.lastrowid

    @staticmethod
    async def stream_analyze():
        try:
            yield {"type": "status", "message": "正在采集数据..."}

            records = OpinionAnalysisService._collect_data_for_analysis()
            if not records:
                yield {"type": "error", "message": "没有可分析的数据，请先进行瞭望采集"}
                return

            yield {"type": "status", "message": f"已采集 {len(records)} 条数据，正在加载模型..."}

            config = ModelEngineRepository.get_default_model(include_secret=True)
            if not config:
                config = ModelEngineRepository.get_first_active_model(include_secret=True)
            if not config:
                yield {"type": "error", "message": "未找到可用模型，请先在模型引擎中配置"}
                return

            yield {"type": "status", "message": f"已加载模型：{config['name']}，正在分析..."}

            prompt = OpinionAnalysisService._build_analysis_prompt(records)
            model_result = await ModelEngineClient.chat_once(config, prompt)

            analysis = OpinionAnalysisService._normalize_analysis(model_result.get("content", ""))
            source_ids = [r["id"] for r in records]
            opinion_id = OpinionAnalysisService._save_analysis(analysis, config.get("name", ""), source_ids)

            yield {
                "type": "done",
                "message": "分析完成",
                "opinion_id": opinion_id,
                "analysis": analysis,
            }
        except Exception as e:
            import traceback
            error_msg = f"分析过程出错: {str(e)}"
            yield {"type": "error", "message": error_msg}
            # 打印详细堆栈到服务器日志
            traceback.print_exc()
