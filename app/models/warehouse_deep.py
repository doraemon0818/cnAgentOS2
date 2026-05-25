import asyncio
import json
import re
import time
import uuid
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup

from app.models.db import get_connection
from app.models.model_engine import ModelEngineClient, ModelEngineRepository


def _safe_json_loads(value, default):
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def _normalize_text(value: str) -> str:
    text = (value or "").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


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


class Raw4AIExtractor:
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/136.0.0.0 Safari/537.36"
    )

    @staticmethod
    def _pick_best_node(soup: BeautifulSoup):
        selectors = [
            "article",
            "main article",
            ".article",
            ".article-content",
            ".post-content",
            ".entry-content",
            ".content",
            "#article",
            "#content",
            "main",
        ]
        candidates = []
        for selector in selectors:
            for node in soup.select(selector):
                text = _normalize_text(node.get_text("\n", strip=True))
                if len(text) >= 120:
                    candidates.append((len(text), node))
        if candidates:
            candidates.sort(key=lambda item: item[0], reverse=True)
            return candidates[0][1]
        return soup.body or soup

    @staticmethod
    def extract(url: str):
        headers = {
            "User-Agent": Raw4AIExtractor.USER_AGENT,
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding or "utf-8"
        html = response.text[:500000]
        soup = BeautifulSoup(html, "lxml")

        for tag in soup(["script", "style", "noscript", "iframe", "svg", "canvas", "footer", "nav"]):
            tag.decompose()

        best_node = Raw4AIExtractor._pick_best_node(soup)
        page_title = _normalize_text(soup.title.get_text(" ", strip=True) if soup.title else "")
        content_text = _normalize_text(best_node.get_text("\n", strip=True))
        if len(content_text) < 120 and soup.body:
            content_text = _normalize_text(soup.body.get_text("\n", strip=True))
        if not content_text:
            raise RuntimeError("页面正文提取失败，未获取到有效内容")

        content_html = str(best_node)[:200000]
        content_markdown = content_text
        return {
            "page_title": page_title[:300],
            "content_text": content_text[:50000],
            "content_markdown": content_markdown[:50000],
            "content_html": content_html,
            "extract_engine": "raw4ai-fallback",
            "extract_status": 1,
        }


class WarehouseDeepTaskRepository:
    @staticmethod
    def create_task(record_ids: List[int]):
        batch_no = "deep_" + uuid.uuid4().hex[:16]
        with get_connection() as conn:
            cursor = conn.execute(
                """
                insert into surveillance_deep_tasks(
                    batch_no,record_ids_json,total_count,status,create_at,update_at
                ) values(?,?,?,'running',datetime('now'),datetime('now'))
                """,
                (batch_no, json.dumps(record_ids, ensure_ascii=False), len(record_ids)),
            )
            return cursor.lastrowid, batch_no

    @staticmethod
    def add_log(task_id: int, message: str, level: str = "info", record_id: Optional[int] = None):
        with get_connection() as conn:
            conn.execute(
                """
                insert into surveillance_deep_logs(task_id,record_id,level,message,create_at)
                values(?,?,?,?,datetime('now'))
                """,
                (task_id, record_id, level, message),
            )

    @staticmethod
    def update_task(task_id: int, stats: Dict, status: str, error_message: str = ""):
        with get_connection() as conn:
            conn.execute(
                """
                update surveillance_deep_tasks
                set success_count=?,failed_count=?,total_tokens=?,avg_score=?,status=?,error_message=?,
                    update_at=datetime('now')
                where id=?
                """,
                (
                    int(stats.get("success_count") or 0),
                    int(stats.get("failed_count") or 0),
                    int(stats.get("total_tokens") or 0),
                    round(float(stats.get("avg_score") or 0), 2),
                    status,
                    (error_message or "")[:500],
                    task_id,
                ),
            )


class WarehouseDetailRepository:
    @staticmethod
    def get_records_by_ids(record_ids: List[int]):
        if not record_ids:
            return []
        placeholders = ",".join(["?"] * len(record_ids))
        sql = f"""
            select id,source_id,source_name,keyword,page_no,title,url,summary,origin_site,publish_time,
                   deep_status,deep_collect_at,deep_detail_id,deep_task_id,deep_error_message
            from surveillance_records
            where id in ({placeholders})
            order by id asc
        """
        with get_connection() as conn:
            rows = conn.execute(sql, record_ids).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def mark_record_processing(record_id: int, task_id: int):
        with get_connection() as conn:
            conn.execute(
                """
                update surveillance_records
                set deep_status=3,deep_task_id=?,deep_error_message='',update_at=datetime('now')
                where id=?
                """,
                (task_id, record_id),
            )

    @staticmethod
    def mark_record_failed(record_id: int, task_id: int, error_message: str):
        with get_connection() as conn:
            conn.execute(
                """
                update surveillance_records
                set deep_status=2,deep_task_id=?,deep_error_message=?,update_at=datetime('now')
                where id=?
                """,
                (task_id, (error_message or "")[:500], record_id),
            )

    @staticmethod
    def save_detail(
        record: Dict,
        task_id: int,
        extract_result: Dict,
        analysis_result: Dict,
        model_config: Dict,
        usage_result: Dict,
        error_message: str = "",
    ):
        with get_connection() as conn:
            payload = (
                task_id,
                record.get("source_id"),
                record.get("source_name", ""),
                record.get("keyword", ""),
                record.get("title", ""),
                record.get("url", ""),
                extract_result.get("page_title", ""),
                extract_result.get("content_markdown", ""),
                extract_result.get("content_text", ""),
                extract_result.get("content_html", ""),
                extract_result.get("extract_engine", "raw4ai-fallback"),
                int(extract_result.get("extract_status") or 1),
                analysis_result.get("summary", ""),
                json.dumps(analysis_result.get("keywords") or [], ensure_ascii=False),
                json.dumps(analysis_result.get("key_points") or [], ensure_ascii=False),
                json.dumps(analysis_result.get("entities") or [], ensure_ascii=False),
                analysis_result.get("sentiment", ""),
                int(analysis_result.get("score") or 0),
                model_config.get("id"),
                model_config.get("name", ""),
                int(usage_result.get("prompt_tokens") or 0),
                int(usage_result.get("completion_tokens") or 0),
                int(usage_result.get("total_tokens") or 0),
                int(usage_result.get("response_ms") or 0),
                (error_message or "")[:500],
            )
            exists = conn.execute(
                "select id from surveillance_record_details where record_id=? order by id desc limit 1",
                (record["id"],),
            ).fetchone()
            if exists:
                detail_id = exists["id"]
                conn.execute(
                    """
                    update surveillance_record_details
                    set task_id=?,source_id=?,source_name=?,keyword=?,title=?,url=?,page_title=?,
                        content_markdown=?,content_text=?,content_html=?,extract_engine=?,extract_status=?,
                        ai_summary=?,ai_keywords_json=?,ai_key_points_json=?,ai_entities_json=?,ai_sentiment=?,
                        ai_score=?,model_id=?,model_name=?,prompt_tokens=?,completion_tokens=?,total_tokens=?,
                        response_ms=?,error_message=?,update_at=datetime('now')
                    where id=?
                    """,
                    payload + (detail_id,),
                )
            else:
                cursor = conn.execute(
                    """
                    insert into surveillance_record_details(
                        record_id,task_id,source_id,source_name,keyword,title,url,page_title,
                        content_markdown,content_text,content_html,extract_engine,extract_status,
                        ai_summary,ai_keywords_json,ai_key_points_json,ai_entities_json,ai_sentiment,ai_score,
                        model_id,model_name,prompt_tokens,completion_tokens,total_tokens,response_ms,error_message,
                        create_at,update_at
                    ) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'),datetime('now'))
                    """,
                    (record["id"],) + payload,
                )
                detail_id = cursor.lastrowid
            conn.execute(
                """
                update surveillance_records
                set deep_status=1,deep_collect_at=datetime('now'),deep_detail_id=?,deep_task_id=?,
                    deep_error_message='',update_at=datetime('now')
                where id=?
                """,
                (detail_id, task_id, record["id"]),
            )
        return detail_id

    @staticmethod
    def get_latest_detail(record_id: int):
        with get_connection() as conn:
            row = conn.execute(
                """
                select *
                from surveillance_record_details
                where record_id=?
                order by id desc
                limit 1
                """,
                (record_id,),
            ).fetchone()
        if not row:
            return None
        data = dict(row)
        data["ai_keywords"] = _safe_json_loads(data.get("ai_keywords_json"), [])
        data["ai_key_points"] = _safe_json_loads(data.get("ai_key_points_json"), [])
        data["ai_entities"] = _safe_json_loads(data.get("ai_entities_json"), [])
        return data

    @staticmethod
    def get_summary():
        with get_connection() as conn:
            row = conn.execute(
                """
                select
                    count(*) as total_records,
                    sum(case when deep_status=1 then 1 else 0 end) as deep_success_count,
                    sum(case when deep_status=2 then 1 else 0 end) as deep_failed_count,
                    sum(case when deep_status=3 then 1 else 0 end) as deep_running_count,
                    sum(case when coalesce(deep_status,0)=0 then 1 else 0 end) as deep_pending_count
                from surveillance_records
                """
            ).fetchone()
            detail_row = conn.execute(
                """
                select
                    count(*) as total_details,
                    coalesce(sum(total_tokens),0) as total_tokens,
                    coalesce(avg(ai_score),0) as avg_score
                from surveillance_record_details
                """
            ).fetchone()
        return {
            "total_records": row["total_records"] or 0,
            "deep_success_count": row["deep_success_count"] or 0,
            "deep_failed_count": row["deep_failed_count"] or 0,
            "deep_running_count": row["deep_running_count"] or 0,
            "deep_pending_count": row["deep_pending_count"] or 0,
            "total_details": detail_row["total_details"] or 0,
            "total_tokens": detail_row["total_tokens"] or 0,
            "avg_score": round(detail_row["avg_score"] or 0, 2),
        }


class WarehouseDeepCollector:
    @staticmethod
    def _resolve_model_config():
        config = ModelEngineRepository.get_default_model(include_secret=True)
        if not config:
            config = ModelEngineRepository.get_first_active_model(include_secret=True)
        if not config:
            raise RuntimeError("未找到可用默认模型，请先在模型引擎中启用并配置一个模型")
        return config

    @staticmethod
    def _build_prompt(record: Dict, extract_result: Dict):
        content_text = (extract_result.get("content_text") or "")[:12000]
        title = record.get("title", "")
        keyword = record.get("keyword", "")
        source_name = record.get("source_name", "")
        prompt = f"""
你是数据仓库的 AI 深度采集分析助手，需要对网页正文做结构化总结。

请根据以下信息输出严格 JSON，不要输出任何额外解释：
{{
  "summary": "不超过180字的中文摘要",
  "keywords": ["关键词1", "关键词2", "关键词3"],
  "key_points": ["要点1", "要点2", "要点3"],
  "entities": [
    {{"name": "实体名", "type": "机构/人物/地点/事件"}}
  ],
  "sentiment": "正向/中性/负向",
  "score": 0
}}

要求：
1. score 为 0-100 的信息质量评分，分数越高表示正文越完整、价值越高。
2. keywords 最多 6 个，key_points 最多 5 个，entities 最多 6 个。
3. 如果正文信息不足，也要返回合法 JSON。

采集源：{source_name}
原始关键字：{keyword}
标题：{title}
正文：
{content_text}
""".strip()
        return prompt

    @staticmethod
    def _normalize_analysis(content: str):
        data = _extract_json_block(content)
        if not isinstance(data, dict):
            return {
                "summary": (content or "").strip()[:300],
                "keywords": [],
                "key_points": [],
                "entities": [],
                "sentiment": "中性",
                "score": 0,
            }

        keywords = data.get("keywords") if isinstance(data.get("keywords"), list) else []
        key_points = data.get("key_points") if isinstance(data.get("key_points"), list) else []
        entities = data.get("entities") if isinstance(data.get("entities"), list) else []
        score = data.get("score") or 0
        try:
            score = max(0, min(100, int(score)))
        except Exception:
            score = 0
        return {
            "summary": str(data.get("summary") or "").strip()[:500],
            "keywords": [str(item).strip()[:40] for item in keywords if str(item).strip()][:6],
            "key_points": [str(item).strip()[:120] for item in key_points if str(item).strip()][:5],
            "entities": entities[:6],
            "sentiment": str(data.get("sentiment") or "中性").strip()[:20],
            "score": score,
        }

    @staticmethod
    def _build_event(task_id: int, message: str, level: str = "info", record_id: Optional[int] = None, extra: Optional[Dict] = None):
        WarehouseDeepTaskRepository.add_log(task_id, message, level=level, record_id=record_id)
        payload = {
            "type": "log",
            "task_id": task_id,
            "level": level,
            "record_id": record_id,
            "message": message,
        }
        if extra:
            payload.update(extra)
        return payload

    @staticmethod
    async def stream_collect(record_ids: List[int]):
        normalized_ids = []
        seen = set()
        for item in record_ids:
            try:
                value = int(item)
            except Exception:
                continue
            if value > 0 and value not in seen:
                seen.add(value)
                normalized_ids.append(value)

        if not normalized_ids:
            raise RuntimeError("请选择要进行 AI 深度采集的数据")

        records = WarehouseDetailRepository.get_records_by_ids(normalized_ids)
        if not records:
            raise RuntimeError("未找到可采集的数据记录")

        task_id, batch_no = WarehouseDeepTaskRepository.create_task([item["id"] for item in records])
        stats = {
            "total_count": len(records),
            "success_count": 0,
            "failed_count": 0,
            "total_tokens": 0,
            "score_sum": 0,
            "avg_score": 0,
        }
        yield WarehouseDeepCollector._build_event(task_id, f"深度采集任务已创建，批次号：{batch_no}")

        model_config = WarehouseDeepCollector._resolve_model_config()
        yield WarehouseDeepCollector._build_event(task_id, f"已加载模型：{model_config['name']}")

        for index, record in enumerate(records, start=1):
            record_id = record["id"]
            WarehouseDetailRepository.mark_record_processing(record_id, task_id)
            yield WarehouseDeepCollector._build_event(
                task_id,
                f"[{index}/{len(records)}] 开始采集：{record['title']}",
                record_id=record_id,
            )
            request_prompt = ""
            analysis_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "response_ms": 0}
            try:
                extract_result = await asyncio.to_thread(Raw4AIExtractor.extract, record["url"])
                content_length = len(extract_result.get("content_text") or "")
                yield WarehouseDeepCollector._build_event(
                    task_id,
                    f"正文抽取完成，长度 {content_length} 字，抽取引擎：{extract_result.get('extract_engine')}",
                    record_id=record_id,
                )

                request_prompt = WarehouseDeepCollector._build_prompt(record, extract_result)
                started_at = time.time()
                model_result = await ModelEngineClient.chat_once(model_config, request_prompt)
                analysis_usage = {
                    "prompt_tokens": model_result.get("prompt_tokens", 0),
                    "completion_tokens": model_result.get("completion_tokens", 0),
                    "total_tokens": model_result.get("total_tokens", 0),
                    "response_ms": model_result.get("response_ms", int((time.time() - started_at) * 1000)),
                }
                ModelEngineRepository.log_usage(
                    model_id=model_config["id"],
                    model_name=model_config["name"],
                    request_preview=request_prompt,
                    response_preview=model_result.get("content", ""),
                    prompt_tokens=analysis_usage["prompt_tokens"],
                    completion_tokens=analysis_usage["completion_tokens"],
                    total_tokens=analysis_usage["total_tokens"],
                    response_ms=analysis_usage["response_ms"],
                    success=1,
                )

                analysis_result = WarehouseDeepCollector._normalize_analysis(model_result.get("content", ""))
                detail_id = WarehouseDetailRepository.save_detail(
                    record=record,
                    task_id=task_id,
                    extract_result=extract_result,
                    analysis_result=analysis_result,
                    model_config=model_config,
                    usage_result=analysis_usage,
                )
                stats["success_count"] += 1
                stats["total_tokens"] += analysis_usage["total_tokens"]
                stats["score_sum"] += analysis_result.get("score", 0)
                stats["avg_score"] = (
                    stats["score_sum"] / stats["success_count"] if stats["success_count"] else 0
                )
                yield WarehouseDeepCollector._build_event(
                    task_id,
                    f"深采完成，详情ID：{detail_id}，评分：{analysis_result.get('score', 0)}，Token：{analysis_usage['total_tokens']}",
                    level="success",
                    record_id=record_id,
                    extra={"detail_id": detail_id, "score": analysis_result.get("score", 0)},
                )
            except Exception as exc:
                if request_prompt:
                    ModelEngineRepository.log_usage(
                        model_id=model_config["id"],
                        model_name=model_config["name"],
                        request_preview=request_prompt,
                        response_preview="",
                        prompt_tokens=0,
                        completion_tokens=0,
                        total_tokens=0,
                        response_ms=0,
                        success=0,
                        error_message=str(exc),
                    )
                WarehouseDetailRepository.mark_record_failed(record_id, task_id, str(exc))
                stats["failed_count"] += 1
                yield WarehouseDeepCollector._build_event(
                    task_id,
                    f"采集失败：{exc}",
                    level="error",
                    record_id=record_id,
                )

        task_status = "completed" if stats["failed_count"] == 0 else ("partial" if stats["success_count"] else "failed")
        WarehouseDeepTaskRepository.update_task(task_id, stats, status=task_status)
        yield {
            "type": "done",
            "task_id": task_id,
            "status": task_status,
            "stats": {
                "total_count": stats["total_count"],
                "success_count": stats["success_count"],
                "failed_count": stats["failed_count"],
                "total_tokens": stats["total_tokens"],
                "avg_score": round(stats["avg_score"], 2),
            },
        }
