import json
from typing import Dict, Optional

import requests

from app.models.db import get_connection


def _safe_json_loads(value, default):
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


class ApiEndpointRepository:
    @staticmethod
    def _normalize_method(method: str) -> str:
        method = (method or "GET").strip().upper()
        return method if method in ("GET", "POST", "PUT", "DELETE") else "GET"

    @staticmethod
    def _normalize_format(response_format: str) -> str:
        response_format = (response_format or "JSON").strip().upper()
        return response_format if response_format in ("JSON", "TEXT", "XML", "HTML") else "JSON"

    @staticmethod
    def _row_to_dict(row, include_runtime_json=True):
        if not row:
            return None
        data = dict(row)
        if include_runtime_json:
            data["headers"] = _safe_json_loads(data.get("headers_json"), {})
            data["params_schema"] = _safe_json_loads(data.get("params_schema_json"), [])
        return data

    @staticmethod
    def get_endpoint_list(page=1, page_size=20, keyword=""):
        offset = (page - 1) * page_size
        conditions = []
        params = []
        if keyword:
            like_value = f"%{keyword}%"
            conditions.append("(name like ? or code like ? or url like ? or remark like ?)")
            params.extend([like_value, like_value, like_value, like_value])

        where_sql = f"where {' and '.join(conditions)}" if conditions else ""
        sql = f"""
            select id,name,code,url,method,response_format,sample_url,default_qps,
                   auth_note,remark,timeout_seconds,status,create_at,update_at
            from api_endpoints
            {where_sql}
            order by id desc
            limit ? offset ?
        """
        count_sql = f"select count(*) as total from api_endpoints {where_sql}"
        with get_connection() as conn:
            rows = conn.execute(sql, tuple(params + [page_size, offset])).fetchall()
            total = conn.execute(count_sql, tuple(params)).fetchone()["total"]
        return {"list": [dict(row) for row in rows], "total": total}

    @staticmethod
    def get_endpoint_by_id(endpoint_id: int):
        with get_connection() as conn:
            row = conn.execute("select * from api_endpoints where id=?", (endpoint_id,)).fetchone()
        return ApiEndpointRepository._row_to_dict(row)

    @staticmethod
    def get_endpoint_by_code(code: str):
        with get_connection() as conn:
            row = conn.execute("select * from api_endpoints where code=?", (code,)).fetchone()
        return ApiEndpointRepository._row_to_dict(row)

    @staticmethod
    def get_endpoint_options():
        with get_connection() as conn:
            rows = conn.execute(
                """
                select id,name,code,method,response_format,status
                from api_endpoints
                where status=1
                order by id desc
                """
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def save_endpoint(data: Dict, endpoint_id: Optional[int] = None):
        name = (data.get("name") or "").strip()
        code = (data.get("code") or "").strip()
        url = (data.get("url") or "").strip()
        method = ApiEndpointRepository._normalize_method(data.get("method") or "GET")
        response_format = ApiEndpointRepository._normalize_format(data.get("response_format") or "JSON")
        sample_url = (data.get("sample_url") or "").strip()
        default_qps = (data.get("default_qps") or "").strip()
        auth_note = (data.get("auth_note") or "").strip()
        remark = (data.get("remark") or "").strip()
        headers_json = data.get("headers_json") or "{}"
        params_schema_json = data.get("params_schema_json") or "[]"
        body_template = (data.get("body_template") or "").strip()
        timeout_seconds = int(data.get("timeout_seconds") or 20)
        status = int(data.get("status") or 1)

        if not name or not code or not url:
            return False, "接口名称、接口编码和接口地址不能为空"

        try:
            json.loads(headers_json)
        except json.JSONDecodeError:
            return False, "请求头JSON格式不正确"

        try:
            json.loads(params_schema_json)
        except json.JSONDecodeError:
            return False, "参数定义JSON格式不正确"

        with get_connection() as conn:
            duplicate_sql = "select id from api_endpoints where (name=? or code=?)"
            duplicate_params = [name, code]
            if endpoint_id:
                duplicate_sql += " and id<>?"
                duplicate_params.append(endpoint_id)
            duplicate = conn.execute(duplicate_sql, tuple(duplicate_params)).fetchone()
            if duplicate:
                return False, "接口名称或编码已存在"

            payload = (
                name,
                code,
                url,
                method,
                response_format,
                sample_url,
                default_qps,
                auth_note,
                remark,
                headers_json,
                params_schema_json,
                body_template,
                timeout_seconds,
                status,
            )

            if endpoint_id:
                conn.execute(
                    """
                    update api_endpoints
                    set name=?,code=?,url=?,method=?,response_format=?,sample_url=?,default_qps=?,auth_note=?,
                        remark=?,headers_json=?,params_schema_json=?,body_template=?,timeout_seconds=?,status=?,
                        update_at=datetime('now')
                    where id=?
                    """,
                    payload + (endpoint_id,),
                )
            else:
                conn.execute(
                    """
                    insert into api_endpoints(
                        name,code,url,method,response_format,sample_url,default_qps,auth_note,remark,
                        headers_json,params_schema_json,body_template,timeout_seconds,status,create_at,update_at
                    ) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'),datetime('now'))
                    """,
                    payload,
                )
        return True, "保存成功"

    @staticmethod
    def delete_endpoint(endpoint_id: int):
        with get_connection() as conn:
            conn.execute("delete from api_endpoints where id=?", (endpoint_id,))
        return True, "删除成功"

    @staticmethod
    def call_endpoint(config: Dict, params: Optional[Dict] = None, body: Optional[Dict] = None):
        if not config:
            raise RuntimeError("接口配置不存在")
        if int(config.get("status") or 0) != 1:
            raise RuntimeError("接口已停用")

        params = params or {}
        body = body or {}
        headers = _safe_json_loads(config.get("headers_json"), {})
        method = ApiEndpointRepository._normalize_method(config.get("method") or "GET")
        timeout_seconds = int(config.get("timeout_seconds") or 20)

        request_kwargs = {
            "method": method,
            "url": config["url"],
            "headers": headers,
            "timeout": timeout_seconds,
        }

        if params:
            request_kwargs["params"] = params

        if method in ("GET", "DELETE"):
            pass
        else:
            if headers.get("Content-Type", "").lower().startswith("application/json"):
                request_kwargs["json"] = body or params
            else:
                request_kwargs["data"] = body or params

        response = requests.request(**request_kwargs)
        content_type = response.headers.get("Content-Type", "")
        preview_text = response.text[:5000]

        result = {
            "status_code": response.status_code,
            "content_type": content_type,
            "text": preview_text,
        }
        if "application/json" in content_type.lower():
            try:
                result["json"] = response.json()
            except Exception:
                result["json"] = None
        else:
            result["json"] = None
        return result

    @staticmethod
    def call_by_code(code: str, params: Optional[Dict] = None, body: Optional[Dict] = None):
        config = ApiEndpointRepository.get_endpoint_by_code(code)
        if not config:
            raise RuntimeError("接口编码不存在")
        return ApiEndpointRepository.call_endpoint(config, params=params, body=body)
