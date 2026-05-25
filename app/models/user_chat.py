import json
import re
import sqlite3
from typing import Dict, List, Optional

from app.models.db import DB_PATH, get_connection
from app.models.digital_employee import DigitalEmployeeRepository
from app.models.model_engine import ModelEngineClient, ModelEngineRepository


def _safe_json_loads(value, default):
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def _clip_text(text: str, limit: int = 120) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[: limit - 1] + "..."


def _extract_json_block(text: str):
    content = (text or "").strip()
    if not content:
        return None
    content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.I)
    content = re.sub(r"\s*```$", "", content)
    try:
        return json.loads(content)
    except Exception:
        pass
    match = re.search(r"\{[\s\S]*\}", content)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except Exception:
        return None


class UserChatSessionRepository:
    @staticmethod
    def _row_to_session(row):
        if not row:
            return None
        return dict(row)

    @staticmethod
    def create_session(user_id: int, username: str, title: str, model_id: Optional[int] = None, model_name: str = ""):
        with get_connection() as conn:
            cursor = conn.execute(
                """
                insert into user_chat_sessions(
                    user_id,username,title,model_id,model_name,last_message_preview,last_intent,message_count,create_at,update_at
                ) values(?,?,?,?,?,'','',0,datetime('now'),datetime('now'))
                """,
                (user_id, username, title, model_id, model_name),
            )
            session_id = cursor.lastrowid
            row = conn.execute("select * from user_chat_sessions where id=?", (session_id,)).fetchone()
        return UserChatSessionRepository._row_to_session(row)

    @staticmethod
    def get_session(user_id: int, session_id: int):
        with get_connection() as conn:
            row = conn.execute(
                "select * from user_chat_sessions where id=? and user_id=?",
                (session_id, user_id),
            ).fetchone()
        return UserChatSessionRepository._row_to_session(row)

    @staticmethod
    def ensure_session(
        user_id: int,
        username: str,
        session_id: Optional[int] = None,
        title: str = "",
        model_id: Optional[int] = None,
        model_name: str = "",
    ):
        if session_id:
            session = UserChatSessionRepository.get_session(user_id, int(session_id))
            if session:
                return session
        return UserChatSessionRepository.create_session(
            user_id=user_id,
            username=username,
            title=title or "新对话",
            model_id=model_id,
            model_name=model_name,
        )

    @staticmethod
    def list_sessions(user_id: int, limit: int = 100):
        with get_connection() as conn:
            rows = conn.execute(
                """
                select id,user_id,username,title,model_id,model_name,last_message_preview,last_intent,message_count,create_at,update_at
                from user_chat_sessions
                where user_id=?
                order by update_at desc,id desc
                limit ?
                """,
                (user_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def update_session(
        session_id: int,
        last_message_preview: str = "",
        last_intent: str = "",
        model_id: Optional[int] = None,
        model_name: str = "",
        title: Optional[str] = None,
    ):
        with get_connection() as conn:
            row = conn.execute(
                "select count(*) as cnt from user_chat_messages where session_id=?",
                (session_id,),
            ).fetchone()
            count_value = row["cnt"] if row else 0
            if title is None:
                conn.execute(
                    """
                    update user_chat_sessions
                    set last_message_preview=?,last_intent=?,model_id=?,model_name=?,message_count=?,update_at=datetime('now')
                    where id=?
                    """,
                    (last_message_preview, last_intent, model_id, model_name, count_value, session_id),
                )
            else:
                conn.execute(
                    """
                    update user_chat_sessions
                    set title=?,last_message_preview=?,last_intent=?,model_id=?,model_name=?,message_count=?,update_at=datetime('now')
                    where id=?
                    """,
                    (title, last_message_preview, last_intent, model_id, model_name, count_value, session_id),
                )

    @staticmethod
    def get_messages(user_id: int, session_id: int):
        session = UserChatSessionRepository.get_session(user_id, session_id)
        if not session:
            return None, []
        with get_connection() as conn:
            rows = conn.execute(
                """
                select id,session_id,user_id,role,message_type,intent,model_id,model_name,content_text,content_markdown,
                       extra_json,prompt_tokens,completion_tokens,total_tokens,response_ms,create_at
                from user_chat_messages
                where session_id=?
                order by id asc
                """,
                (session_id,),
            ).fetchall()
        messages = []
        for row in rows:
            item = dict(row)
            item["extra"] = _safe_json_loads(item.get("extra_json"), {})
            messages.append(item)
        return session, messages

    @staticmethod
    def delete_session(user_id: int, session_id: int):
        session = UserChatSessionRepository.get_session(user_id, session_id)
        if not session:
            return False
        with get_connection() as conn:
            conn.execute("delete from user_chat_messages where session_id=?", (int(session_id),))
            conn.execute("delete from user_chat_sessions where id=? and user_id=?", (int(session_id), int(user_id)))
        return True

    @staticmethod
    def add_message(
        session_id: int,
        user_id: int,
        role: str,
        content_text: str,
        content_markdown: str = "",
        message_type: str = "chat",
        intent: str = "",
        model_id: Optional[int] = None,
        model_name: str = "",
        extra: Optional[Dict] = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        response_ms: int = 0,
    ):
        with get_connection() as conn:
            cursor = conn.execute(
                """
                insert into user_chat_messages(
                    session_id,user_id,role,message_type,intent,model_id,model_name,content_text,content_markdown,
                    extra_json,prompt_tokens,completion_tokens,total_tokens,response_ms,create_at
                ) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'))
                """,
                (
                    session_id,
                    user_id,
                    role,
                    message_type,
                    intent,
                    model_id,
                    model_name,
                    content_text,
                    content_markdown or content_text,
                    json.dumps(extra or {}, ensure_ascii=False),
                    prompt_tokens,
                    completion_tokens,
                    total_tokens,
                    response_ms,
                ),
            )
            return cursor.lastrowid


class AskDataService:
    INTENT_CHAT = "chat"
    INTENT_DB = "db"
    INTENT_EMPLOYEE = "employee"

    @staticmethod
    def _build_title(message: str):
        text = re.sub(r"\s+", " ", (message or "").strip())
        return _clip_text(text or "新对话", 22)

    @staticmethod
    def _resolve_model(model_id: Optional[int] = None):
        if model_id:
            config = ModelEngineRepository.get_model_by_id(int(model_id), include_secret=True)
        else:
            config = ModelEngineRepository.get_default_model(include_secret=True)
            if not config:
                config = ModelEngineRepository.get_first_active_model(include_secret=True)
        if not config:
            raise RuntimeError("当前没有可用模型，请先在模型引擎中启用并配置模型服务")
        return config

    @staticmethod
    def _history_as_messages(messages: List[Dict], keep: int = 10):
        history = []
        for item in messages[-keep:]:
            role = item.get("role")
            if role not in ("user", "assistant"):
                continue
            content = item.get("content_markdown") or item.get("content_text") or ""
            if content:
                history.append({"role": role, "content": content})
        return history

    @staticmethod
    def _history_preview(messages: List[Dict], keep: int = 6):
        lines = []
        for item in messages[-keep:]:
            role = "用户" if item.get("role") == "user" else "助手"
            content = _clip_text(item.get("content_text") or item.get("content_markdown") or "", 140)
            if content:
                lines.append(f"{role}: {content}")
        return "\n".join(lines)

    @staticmethod
    def _guess_db_intent(message: str):
        text = (message or "").lower()
        keywords = [
            "数据仓库", "深度采集", "采集", "sqlite", "sql", "数据库", "记录",
            "最新一条", "最近一条", "多少条", "统计", "来源", "关键词", "标题", "链接",
            "最新数据", "明细", "详情", "数据详情", "哪条", "哪些",
        ]
        return any(item in text for item in keywords)

    @staticmethod
    async def _detect_intent(message: str, history_messages: List[Dict], model_config: Dict):
        if DigitalEmployeeRepository.parse_at_message(message):
            return {"intent": AskDataService.INTENT_EMPLOYEE, "reason": "命中数字员工 @ 调用格式"}

        if AskDataService._guess_db_intent(message):
            return {"intent": AskDataService.INTENT_DB, "reason": "命中数据问答关键词"}

        prompt = f"""
你是智能问数系统的意图识别器，请判断用户问题更适合：
1. chat：普通 AI 对话、解释、写作、分析建议
2. db：需要结合 SQLite 中的数据仓库记录进行检索、统计、筛选、查询

请只输出 JSON：
{{"intent":"chat 或 db","reason":"不超过40字"}}

最近上下文：
{AskDataService._history_preview([{"role": item["role"], "content_text": item["content"]} for item in history_messages], keep=4)}

当前问题：
{message}
        """.strip()
        result = await ModelEngineClient.chat_once(model_config, prompt)
        data = _extract_json_block(result.get("content", "")) or {}
        intent = str(data.get("intent") or "").strip().lower()
        if intent not in (AskDataService.INTENT_CHAT, AskDataService.INTENT_DB):
            intent = AskDataService.INTENT_CHAT
        return {"intent": intent, "reason": str(data.get("reason") or "").strip()[:80]}

    @staticmethod
    def _schema_prompt():
        return """
你可以查询的 SQLite 表仅有以下两张：

1. surveillance_records
- id: 主键
- source_id: 采集源ID
- source_name: 采集源名称
- keyword: 采集关键字
- page_no: 页码
- title: 标题
- url: 链接
- summary: 简介
- origin_site: 来源站点
- publish_time: 发布时间
- create_at: 入库时间
- update_at: 更新时间
- deep_status: 深采状态，0未深采 1已深采 2失败 3进行中
- deep_collect_at: 深采时间
- deep_detail_id: 关联详情ID
- deep_task_id: 深采任务ID
- deep_error_message: 深采错误

2. surveillance_record_details
- id: 主键
- record_id: 关联 surveillance_records.id
- task_id: 深采任务ID
- source_id: 采集源ID
- source_name: 采集源名称
- keyword: 关键字
- title: 标题
- url: 链接
- page_title: 页面标题
- content_markdown: 正文Markdown
- content_text: 正文文本
- ai_summary: AI摘要
- ai_keywords_json: AI关键词JSON
- ai_key_points_json: AI要点JSON
- ai_entities_json: AI实体JSON
- ai_sentiment: 情感
- ai_score: 信息质量评分
- model_name: 深采使用模型
- total_tokens: 深采消耗Token
- response_ms: 响应耗时
- create_at: 创建时间
- update_at: 更新时间
        """.strip()

    @staticmethod
    async def _generate_sql(message: str, history_messages: List[Dict], model_config: Dict):
        prompt = f"""
你是 SQLite 查询规划助手，需要根据用户问题生成只读 SQL。

规则：
1. 只能输出 JSON：{{"sql":"...","reason":"..."}}
2. SQL 只能是 SELECT 或 WITH 开头的只读查询
3. 只能查询 surveillance_records、surveillance_record_details 及其 join
4. 必须使用 SQLite 语法
5. 如无明确数量限制，请加 limit 20
6. 如果问题包含“最新”“最近”，优先按 create_at、publish_time 或 id 倒序

{AskDataService._schema_prompt()}

最近上下文：
{AskDataService._history_preview([{"role": item["role"], "content_text": item["content"]} for item in history_messages], keep=4)}

用户问题：
{message}
        """.strip()
        result = await ModelEngineClient.chat_once(model_config, prompt)
        data = _extract_json_block(result.get("content", "")) or {}
        sql = AskDataService._sanitize_sql(str(data.get("sql") or ""))
        return {
            "sql": sql,
            "reason": str(data.get("reason") or "").strip()[:80],
            "usage": result,
        }

    @staticmethod
    def _sanitize_sql(sql: str):
        sql = (sql or "").strip()
        sql = re.sub(r"^```(?:sql)?\s*", "", sql, flags=re.I)
        sql = re.sub(r"\s*```$", "", sql)
        sql = sql.strip().rstrip(";")
        if not sql:
            raise RuntimeError("模型未生成有效 SQL")
        if not re.match(r"^(select|with)\b", sql, flags=re.I):
            raise RuntimeError("生成的 SQL 不是只读查询")
        if re.search(r"\b(insert|update|delete|drop|alter|pragma|attach|detach|replace|create|vacuum|reindex)\b", sql, flags=re.I):
            raise RuntimeError("生成的 SQL 包含非法操作")
        if not re.search(r"\b(surveillance_records|surveillance_record_details)\b", sql, flags=re.I):
            raise RuntimeError("SQL 未使用允许的数据表")
        if not re.search(r"\blimit\b", sql, flags=re.I):
            sql += " limit 20"
        return sql

    @staticmethod
    def _execute_sql(sql: str):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(sql).fetchall()
        finally:
            conn.close()
        data_rows = [dict(row) for row in rows]
        columns = list(data_rows[0].keys()) if data_rows else []
        return {"columns": columns, "rows": data_rows, "row_count": len(data_rows)}

    @staticmethod
    def _result_markdown(result: Dict):
        rows = result.get("rows") or []
        columns = result.get("columns") or []
        if not rows or not columns:
            return "查询结果为空。"
        display_columns = columns[:8]
        lines = [
            "| " + " | ".join(display_columns) + " |",
            "| " + " | ".join(["---"] * len(display_columns)) + " |",
        ]
        for row in rows[:10]:
            values = []
            for key in display_columns:
                value = row.get(key, "")
                cell = str(value if value is not None else "")
                cell = cell.replace("\n", " ").replace("|", "\\|")
                values.append(_clip_text(cell, 80))
            lines.append("| " + " | ".join(values) + " |")
        if len(rows) > 10:
            lines.append(f"\n共 {len(rows)} 条结果，这里仅展示前 10 条。")
        return "\n".join(lines)

    @staticmethod
    def _build_db_answer_prompt(message: str, sql: str, query_result: Dict):
        rows_json = json.dumps(query_result.get("rows") or [], ensure_ascii=False)[:12000]
        preview_md = AskDataService._result_markdown(query_result)
        return f"""
你是智能问数助手，请基于用户问题、SQL 查询结果，用中文输出清晰的 Markdown 回答。

要求：
1. 先直接回答问题
2. 必要时给出简短结论或列表
3. 不要编造结果，必须以查询结果为准
4. 如果结果为空，要明确说明
5. 可以适度引用表格摘要，但不要输出原始 JSON

用户问题：
{message}

执行 SQL：
```sql
{sql}
```

查询结果摘要：
{preview_md}

查询结果 JSON：
{rows_json}
        """.strip()

    @staticmethod
    async def stream_chat(user_id: int, username: str, message: str, session_id: Optional[int] = None, model_id: Optional[int] = None):
        message = (message or "").strip()
        if not message:
            raise RuntimeError("消息内容不能为空")

        selected_model = None
        if not DigitalEmployeeRepository.parse_at_message(message):
            selected_model = AskDataService._resolve_model(model_id)

        session = UserChatSessionRepository.ensure_session(
            user_id=user_id,
            username=username,
            session_id=session_id,
            title=AskDataService._build_title(message),
            model_id=(selected_model or {}).get("id"),
            model_name=(selected_model or {}).get("name", ""),
        )
        yield {"type": "session", "session": session}

        UserChatSessionRepository.add_message(
            session_id=session["id"],
            user_id=user_id,
            role="user",
            content_text=message,
            content_markdown=message,
            message_type="chat",
            intent="",
            model_id=(selected_model or {}).get("id"),
            model_name=(selected_model or {}).get("name", ""),
        )

        _, stored_messages = UserChatSessionRepository.get_messages(user_id, session["id"])
        history_messages = AskDataService._history_as_messages(stored_messages[:-1], keep=10)

        if DigitalEmployeeRepository.parse_at_message(message):
            yield {"type": "status", "intent": AskDataService.INTENT_EMPLOYEE, "message": "正在连接数字员工服务..."}
            full_text = ""
            done_payload = {}
            async for item in DigitalEmployeeRepository.stream_chat(message):
                item["session_id"] = session["id"]
                if item["type"] == "delta":
                    full_text += item.get("content") or ""
                elif item["type"] == "done":
                    full_text = item.get("content") or full_text
                    done_payload = item
                yield item

            employee_meta = done_payload.get("employee") or {}
            employee_extra = {"employee": employee_meta}
            if done_payload.get("payload") is not None:
                employee_extra["payload"] = done_payload.get("payload")
            if isinstance(done_payload.get("weather_card"), dict):
                employee_extra["weather_card"] = done_payload.get("weather_card")
            if done_payload.get("status_code") is not None:
                employee_extra["status_code"] = done_payload.get("status_code")
            if done_payload.get("content_type"):
                employee_extra["content_type"] = done_payload.get("content_type")
            UserChatSessionRepository.add_message(
                session_id=session["id"],
                user_id=user_id,
                role="assistant",
                content_text=full_text,
                content_markdown=full_text,
                message_type="employee",
                intent=AskDataService.INTENT_EMPLOYEE,
                extra=employee_extra,
                prompt_tokens=int(done_payload.get("prompt_tokens") or 0),
                completion_tokens=int(done_payload.get("completion_tokens") or 0),
                total_tokens=int(done_payload.get("total_tokens") or 0),
                response_ms=int(done_payload.get("response_ms") or 0),
            )
            UserChatSessionRepository.update_session(
                session_id=session["id"],
                last_message_preview=_clip_text(full_text, 150),
                last_intent=AskDataService.INTENT_EMPLOYEE,
                model_id=session.get("model_id"),
                model_name=session.get("model_name", ""),
            )
            return

        intent_result = await AskDataService._detect_intent(message, history_messages, selected_model)
        intent = intent_result["intent"]

        if intent == AskDataService.INTENT_DB:
            yield {"type": "status", "intent": intent, "message": "已识别为智能问数请求，正在生成查询 SQL..."}
            sql_result = await AskDataService._generate_sql(message, history_messages, selected_model)
            sql = sql_result["sql"]
            yield {"type": "status", "intent": intent, "message": "SQL 生成完成，正在查询 SQLite 数据仓库...", "sql": sql}
            query_result = AskDataService._execute_sql(sql)
            yield {
                "type": "status",
                "intent": intent,
                "message": f"查询完成，共命中 {query_result['row_count']} 条记录，正在整理 Markdown 回答...",
                "sql": sql,
                "row_count": query_result["row_count"],
            }
            answer_prompt = AskDataService._build_db_answer_prompt(message, sql, query_result)
            full_text = ""
            done_payload = {}
            async for item in ModelEngineClient.stream_chat(selected_model, answer_prompt):
                if item["type"] == "delta":
                    full_text += item.get("content") or ""
                    yield {"type": "delta", "intent": intent, "content": item.get("content") or "", "session_id": session["id"]}
                elif item["type"] == "done":
                    full_text = item.get("content") or full_text
                    done_payload = item
                    yield {
                        "type": "done",
                        "intent": intent,
                        "content": full_text,
                        "session_id": session["id"],
                        "model": {"id": selected_model["id"], "name": selected_model["name"]},
                        "sql": sql,
                        "row_count": query_result["row_count"],
                        "prompt_tokens": item.get("prompt_tokens", 0),
                        "completion_tokens": item.get("completion_tokens", 0),
                        "total_tokens": item.get("total_tokens", 0),
                        "response_ms": item.get("response_ms", 0),
                    }
            ModelEngineRepository.log_usage(
                model_id=selected_model["id"],
                model_name=selected_model["name"],
                request_preview=answer_prompt,
                response_preview=full_text,
                prompt_tokens=int(done_payload.get("prompt_tokens") or 0),
                completion_tokens=int(done_payload.get("completion_tokens") or 0),
                total_tokens=int(done_payload.get("total_tokens") or 0),
                response_ms=int(done_payload.get("response_ms") or 0),
                success=1,
            )
            UserChatSessionRepository.add_message(
                session_id=session["id"],
                user_id=user_id,
                role="assistant",
                content_text=full_text,
                content_markdown=full_text,
                message_type="db",
                intent=intent,
                model_id=selected_model["id"],
                model_name=selected_model["name"],
                extra={"sql": sql, "row_count": query_result["row_count"]},
                prompt_tokens=int(done_payload.get("prompt_tokens") or 0),
                completion_tokens=int(done_payload.get("completion_tokens") or 0),
                total_tokens=int(done_payload.get("total_tokens") or 0),
                response_ms=int(done_payload.get("response_ms") or 0),
            )
            UserChatSessionRepository.update_session(
                session_id=session["id"],
                last_message_preview=_clip_text(full_text, 150),
                last_intent=intent,
                model_id=selected_model["id"],
                model_name=selected_model["name"],
            )
            return

        yield {"type": "status", "intent": intent, "message": "已识别为普通 AI 对话，正在生成流式回复..."}
        model_messages = history_messages + [{"role": "user", "content": message}]
        full_text = ""
        done_payload = {}
        async for item in ModelEngineClient.stream_chat(selected_model, messages=model_messages):
            if item["type"] == "delta":
                full_text += item.get("content") or ""
                yield {"type": "delta", "intent": intent, "content": item.get("content") or "", "session_id": session["id"]}
            elif item["type"] == "done":
                full_text = item.get("content") or full_text
                done_payload = item
                yield {
                    "type": "done",
                    "intent": intent,
                    "content": full_text,
                    "session_id": session["id"],
                    "model": {"id": selected_model["id"], "name": selected_model["name"]},
                    "prompt_tokens": item.get("prompt_tokens", 0),
                    "completion_tokens": item.get("completion_tokens", 0),
                    "total_tokens": item.get("total_tokens", 0),
                    "response_ms": item.get("response_ms", 0),
                }
        ModelEngineRepository.log_usage(
            model_id=selected_model["id"],
            model_name=selected_model["name"],
            request_preview=json.dumps(model_messages, ensure_ascii=False),
            response_preview=full_text,
            prompt_tokens=int(done_payload.get("prompt_tokens") or 0),
            completion_tokens=int(done_payload.get("completion_tokens") or 0),
            total_tokens=int(done_payload.get("total_tokens") or 0),
            response_ms=int(done_payload.get("response_ms") or 0),
            success=1,
        )
        UserChatSessionRepository.add_message(
            session_id=session["id"],
            user_id=user_id,
            role="assistant",
            content_text=full_text,
            content_markdown=full_text,
            message_type="chat",
            intent=intent,
            model_id=selected_model["id"],
            model_name=selected_model["name"],
            prompt_tokens=int(done_payload.get("prompt_tokens") or 0),
            completion_tokens=int(done_payload.get("completion_tokens") or 0),
            total_tokens=int(done_payload.get("total_tokens") or 0),
            response_ms=int(done_payload.get("response_ms") or 0),
        )
        UserChatSessionRepository.update_session(
            session_id=session["id"],
            last_message_preview=_clip_text(full_text, 150),
            last_intent=intent,
            model_id=selected_model["id"],
            model_name=selected_model["name"],
        )
