import json
import re
from typing import Dict, List, Optional
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup

from app.models.db import get_connection


def _safe_json_loads(value, default):
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def _first_non_empty_text(item, selector_list: List[str]) -> str:
    for selector in selector_list:
        selector = selector.strip()
        if not selector:
            continue
        node = item.select_one(selector)
        if node:
            text = _normalize_text(node.get_text(" ", strip=True))
            if text:
                return text
    return ""


def _parse_source_and_time(item, meta_text: str):
    meta_text = _normalize_text(meta_text)
    source_name = ""
    publish_time = ""

    if meta_text:
        parts = [part.strip() for part in re.split(r"\s{2,}|\u00a0|\||/|·", meta_text) if part.strip()]
        time_pattern = re.compile(r"(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?|\d{1,2}小时前|\d{1,2}分钟前|\d{1,2}天前|\d{1,2}月\d{1,2}日)")
        for part in parts:
            if not publish_time and time_pattern.search(part):
                publish_time = part
            elif not source_name:
                source_name = part

    if not source_name:
        for link in item.select("a"):
            text = _normalize_text(link.get_text(" ", strip=True))
            href = link.get("href", "")
            if text and not href.startswith("javascript") and text not in ("查看更多相关新闻>>", "查看更多相关新闻"):
                title_text = _normalize_text(item.select_one("h3 a").get_text(" ", strip=True)) if item.select_one("h3 a") else ""
                if text != title_text and len(text) <= 30:
                    source_name = text
                    break

    return source_name, publish_time


class SurveillanceSourceRepository:
    @staticmethod
    def _row_to_dict(row):
        if not row:
            return None
        item = dict(row)
        item["headers"] = _safe_json_loads(item.get("headers_json"), {})
        item["params"] = _safe_json_loads(item.get("params_json"), [])
        item["selectors"] = _safe_json_loads(item.get("selectors_json"), {})
        return item

    @staticmethod
    def get_active_sources():
        with get_connection() as conn:
            rows = conn.execute(
                """
                select *
                from surveillance_sources
                where status=1
                order by id asc
                """
            ).fetchall()
        return [SurveillanceSourceRepository._row_to_dict(row) for row in rows]

    @staticmethod
    def get_source_options():
        with get_connection() as conn:
            rows = conn.execute(
                """
                select id,name,code,default_page_count,default_limit,page_step
                from surveillance_sources
                where status=1
                order by id asc
                """
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def get_source_by_id(source_id: int):
        with get_connection() as conn:
            row = conn.execute("select * from surveillance_sources where id=?", (source_id,)).fetchone()
        return SurveillanceSourceRepository._row_to_dict(row)

    @staticmethod
    def get_source_list(page=1, page_size=20, keyword=""):
        offset = (page - 1) * page_size
        conditions = []
        params = []
        if keyword:
            like_value = f"%{keyword}%"
            conditions.append("(name like ? or code like ? or description like ?)")
            params.extend([like_value, like_value, like_value])

        where_sql = f"where {' and '.join(conditions)}" if conditions else ""
        sql = f"""
            select id,name,code,description,entry_url_template,page_url_template,method,page_step,
                   default_page_count,default_limit,status,create_at,update_at
            from surveillance_sources
            {where_sql}
            order by id desc
            limit ? offset ?
        """
        count_sql = f"select count(*) as total from surveillance_sources {where_sql}"

        with get_connection() as conn:
            rows = conn.execute(sql, tuple(params + [page_size, offset])).fetchall()
            total = conn.execute(count_sql, tuple(params)).fetchone()["total"]
        return {"list": [dict(row) for row in rows], "total": total}

    @staticmethod
    def save_source(data: Dict, source_id: Optional[int] = None):
        name = (data.get("name") or "").strip()
        code = (data.get("code") or "").strip()
        entry_url_template = (data.get("entry_url_template") or "").strip()
        page_url_template = (data.get("page_url_template") or "").strip()
        method = (data.get("method") or "GET").strip().upper()
        description = (data.get("description") or "").strip()
        page_step = int(data.get("page_step") or 10)
        default_page_count = int(data.get("default_page_count") or 1)
        default_limit = int(data.get("default_limit") or 20)
        status = int(data.get("status") or 1)

        headers = data.get("headers") or {}
        params_schema = data.get("params") or []
        selectors = data.get("selectors") or {}

        if not name or not code or not entry_url_template or not page_url_template:
            return False, "采集源名称、编码和URL模板不能为空"

        with get_connection() as conn:
            duplicate_sql = "select id from surveillance_sources where code=?"
            duplicate_params = [code]
            if source_id:
                duplicate_sql += " and id<>?"
                duplicate_params.append(source_id)
            duplicate = conn.execute(duplicate_sql, tuple(duplicate_params)).fetchone()
            if duplicate:
                return False, "采集源编码已存在"

            payload = (
                name,
                code,
                description,
                entry_url_template,
                page_url_template,
                method,
                json.dumps(headers, ensure_ascii=False),
                json.dumps(params_schema, ensure_ascii=False),
                json.dumps(selectors, ensure_ascii=False),
                page_step,
                default_page_count,
                default_limit,
                status,
            )

            if source_id:
                conn.execute(
                    """
                    update surveillance_sources
                    set name=?,code=?,description=?,entry_url_template=?,page_url_template=?,method=?,
                        headers_json=?,params_json=?,selectors_json=?,page_step=?,default_page_count=?,
                        default_limit=?,status=?,update_at=datetime('now','localtime')
                    where id=?
                    """,
                    payload + (source_id,),
                )
            else:
                conn.execute(
                    """
                    insert into surveillance_sources(
                        name,code,description,entry_url_template,page_url_template,method,
                        headers_json,params_json,selectors_json,page_step,default_page_count,
                        default_limit,status,create_at,update_at
                    ) values(?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now','localtime'),datetime('now','localtime'))
                    """,
                    payload,
                )

        return True, "保存成功"

    @staticmethod
    def delete_source(source_id: int):
        with get_connection() as conn:
            conn.execute("delete from surveillance_records where source_id=?", (source_id,))
            conn.execute("delete from surveillance_sources where id=?", (source_id,))
        return True, "删除成功"


class SurveillanceCollector:
    @staticmethod
    def _render_url(template: str, keyword: str, pn: int):
        return (
            (template or "")
            .replace("{关键字}", quote(keyword))
            .replace("{keyword}", quote(keyword))
            .replace("{pn}", str(pn))
            .replace("{分页步进，默认0=第一页，10等于第二页，20=第三页}", str(pn))
        )

    @staticmethod
    def _build_headers(headers_config: Dict, keyword: str):
        headers = {}
        for key, value in (headers_config or {}).items():
            if isinstance(value, str):
                headers[key] = value.replace("{keyword}", quote(keyword)).replace("{关键字}", quote(keyword))
            else:
                headers[key] = value
        return headers

    @staticmethod
    def _parse_items(source_config: Dict, html: str):
        selectors = source_config.get("selectors") or {}
        list_selector = selectors.get("list_selector") or "#content_left > div.result, #content_left > div.result-op"
        title_selector = selectors.get("title_selector") or "h3 a"
        summary_selector = selectors.get("summary_selector") or ".c-summary, .content"
        meta_selector = selectors.get("meta_selector") or ".c-title-author, .c-color-gray2"

        soup = BeautifulSoup(html, "lxml")
        items = []
        for block in soup.select(list_selector):
            title_node = block.select_one(title_selector)
            if not title_node:
                continue

            title = _normalize_text(title_node.get_text(" ", strip=True))
            href = (title_node.get("href") or "").strip()
            if not title or not href:
                continue

            meta_text = _first_non_empty_text(block, [meta_selector])
            summary_text = _first_non_empty_text(block, [summary_selector])
            origin_site, publish_time = _parse_source_and_time(block, meta_text)

            items.append({
                "title": title,
                "url": urljoin("https://www.baidu.com", href),
                "summary": summary_text,
                "origin_site": origin_site,
                "publish_time": publish_time,
            })
        return items

    @staticmethod
    def collect(source_id: int, keyword: str, page_count: int = 1, limit: int = 20):
        source_config = SurveillanceSourceRepository.get_source_by_id(source_id)
        if not source_config:
            return False, "采集源不存在", None
        if not keyword:
            return False, "关键字不能为空", None

        page_count = max(1, min(int(page_count or 1), 10))
        limit = max(1, min(int(limit or 20), 100))
        page_step = max(1, int(source_config.get("page_step") or 10))
        headers = SurveillanceCollector._build_headers(source_config.get("headers") or {}, keyword)

        session = requests.Session()
        collected = []

        for page_index in range(page_count):
            pn = page_index * page_step
            url_template = source_config["entry_url_template"] if page_index == 0 else source_config["page_url_template"]
            request_url = SurveillanceCollector._render_url(url_template, keyword, pn)
            response = session.get(request_url, headers=headers, timeout=20)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or response.encoding or "utf-8"
            page_items = SurveillanceCollector._parse_items(source_config, response.text)
            for item in page_items:
                item["page_no"] = page_index + 1
                item["raw_json"] = json.dumps(item, ensure_ascii=False)
                collected.append(item)
                if len(collected) >= limit:
                    break
            if len(collected) >= limit:
                break

        seen = set()
        deduped = []
        for item in collected:
            key = item["url"]
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)

        saved_count = SurveillanceRecordRepository.batch_upsert(
            source_id=source_config["id"],
            source_name=source_config["name"],
            keyword=keyword,
            items=deduped,
        )

        return True, "采集成功", {
            "source": {
                "id": source_config["id"],
                "name": source_config["name"],
                "code": source_config["code"],
            },
            "keyword": keyword,
            "page_count": page_count,
            "request_limit": limit,
            "saved_count": saved_count,
            "items": deduped,
        }


class SurveillanceRecordRepository:
    @staticmethod
    def batch_upsert(source_id: int, source_name: str, keyword: str, items: List[Dict]):
        saved_count = 0
        with get_connection() as conn:
            for item in items:
                exists = conn.execute(
                    "select id from surveillance_records where source_id=? and keyword=? and url=?",
                    (source_id, keyword, item["url"]),
                ).fetchone()
                if exists:
                    conn.execute(
                        """
                        update surveillance_records
                        set title=?,summary=?,origin_site=?,publish_time=?,raw_json=?,update_at=datetime('now','localtime')
                        where id=?
                        """,
                        (
                            item["title"],
                            item.get("summary", ""),
                            item.get("origin_site", ""),
                            item.get("publish_time", ""),
                            item.get("raw_json", "{}"),
                            exists["id"],
                        ),
                    )
                else:
                    conn.execute(
                        """
                        insert into surveillance_records(
                            source_id,source_name,keyword,page_no,title,url,summary,origin_site,publish_time,
                            raw_json,create_at,update_at
                        ) values(?,?,?,?,?,?,?,?,?,?,datetime('now','localtime'),datetime('now','localtime'))
                        """,
                        (
                            source_id,
                            source_name,
                            keyword,
                            item.get("page_no", 1),
                            item["title"],
                            item["url"],
                            item.get("summary", ""),
                            item.get("origin_site", ""),
                            item.get("publish_time", ""),
                            item.get("raw_json", "{}"),
                        ),
                    )
                saved_count += 1
        return saved_count

    @staticmethod
    def get_record_list(page=1, page_size=20, keyword="", source_id=None):
        offset = (page - 1) * page_size
        conditions = []
        params = []
        if keyword:
            like_value = f"%{keyword}%"
            conditions.append("(title like ? or keyword like ? or origin_site like ?)")
            params.extend([like_value, like_value, like_value])
        if source_id is not None and str(source_id) != "":
            conditions.append("source_id=?")
            params.append(int(source_id))

        where_sql = f"where {' and '.join(conditions)}" if conditions else ""
        sql = f"""
            select id,source_id,source_name,keyword,page_no,title,url,summary,origin_site,publish_time,create_at,
                   coalesce(deep_status,0) as deep_status,deep_collect_at,deep_detail_id,deep_task_id,deep_error_message
            from surveillance_records
            {where_sql}
            order by id desc
            limit ? offset ?
        """
        count_sql = f"select count(*) as total from surveillance_records {where_sql}"

        with get_connection() as conn:
            rows = conn.execute(sql, tuple(params + [page_size, offset])).fetchall()
            total = conn.execute(count_sql, tuple(params)).fetchone()["total"]
        return {"list": [dict(row) for row in rows], "total": total}

    @staticmethod
    def get_record_by_id(record_id: int):
        with get_connection() as conn:
            row = conn.execute(
                """
                select id,source_id,source_name,keyword,page_no,title,url,summary,origin_site,publish_time,raw_json,
                       create_at,update_at,coalesce(deep_status,0) as deep_status,deep_collect_at,deep_detail_id,
                       deep_task_id,deep_error_message
                from surveillance_records
                where id=?
                """,
                (record_id,),
            ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def delete_record(record_id: int):
        with get_connection() as conn:
            conn.execute("delete from surveillance_record_details where record_id=?", (record_id,))
            conn.execute("delete from surveillance_records where id=?", (record_id,))
        return True, "删除成功"

    @staticmethod
    def batch_delete(record_ids: List[int]):
        if not record_ids:
            return 0
        with get_connection() as conn:
            conn.execute(
                "delete from surveillance_record_details where record_id in ({})".format(",".join(["?"] * len(record_ids))),
                record_ids,
            )
            cursor = conn.execute(
                "delete from surveillance_records where id in ({})".format(",".join(["?"] * len(record_ids))),
                record_ids,
            )
            return cursor.rowcount
