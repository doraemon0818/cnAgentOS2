import copy
import json
import re
from typing import Dict, Optional

from app.models.api_endpoint import ApiEndpointRepository
from app.models.db import get_connection
from app.models.model_engine import ModelEngineClient, ModelEngineRepository


def _safe_json_loads(value, default):
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def _flatten_data(value, prefix="", result=None):
    if result is None:
        result = {}
    if isinstance(value, dict):
        for key, item in value.items():
            new_prefix = f"{prefix}.{key}" if prefix else str(key)
            _flatten_data(item, new_prefix, result)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            new_prefix = f"{prefix}.{index}" if prefix else str(index)
            _flatten_data(item, new_prefix, result)
    else:
        result[prefix] = value if value is not None else ""
    return result


def _render_template(template: str, payload):
    if not template:
        if isinstance(payload, (dict, list)):
            return json.dumps(payload, ensure_ascii=False, indent=2)
        return str(payload or "")

    flat_map = _flatten_data(payload)
    content = template
    for key, value in flat_map.items():
        content = content.replace("{" + key + "}", str(value))
    content = re.sub(r"\{[^{}]+\}", "", content)
    return content.strip()


class DigitalEmployeeRepository:
    EMPLOYEE_AI = "AI"
    EMPLOYEE_NORMAL = "普通"
    AT_PATTERN = re.compile(r"^\s*@([^\s：:]+)\s*[：:]?\s*(.*)$", re.S)

    @staticmethod
    def _row_to_dict(row):
        if not row:
            return None
        data = dict(row)
        data["api_params"] = _safe_json_loads(data.get("api_params_json"), {})
        return data

    @staticmethod
    def get_employee_list(page=1, page_size=20, keyword=""):
        offset = (page - 1) * page_size
        params = []
        where_sql = ""
        if keyword:
            like_value = f"%{keyword}%"
            where_sql = """
                where de.name like ? or de.alias like ? or de.code like ? or de.description like ?
            """
            params.extend([like_value, like_value, like_value, like_value])

        sql = f"""
            select de.id,de.name,de.alias,de.code,de.category,de.model_id,de.endpoint_id,
                   de.prompt,de.api_param_name,de.api_params_json,de.response_template,
                   de.default_user_input,de.description,de.sort,de.status,de.create_at,de.update_at,
                   ms.name as model_name,
                   ae.name as endpoint_name
            from digital_employees de
            left join model_services ms on ms.id = de.model_id
            left join api_endpoints ae on ae.id = de.endpoint_id
            {where_sql}
            order by de.sort asc,de.id desc
            limit ? offset ?
        """
        count_sql = f"select count(*) as total from digital_employees de {where_sql}"
        with get_connection() as conn:
            rows = conn.execute(sql, tuple(params + [page_size, offset])).fetchall()
            total = conn.execute(count_sql, tuple(params)).fetchone()["total"]
        return {"list": [DigitalEmployeeRepository._row_to_dict(row) for row in rows], "total": total}

    @staticmethod
    def get_employee_by_id(employee_id: int):
        with get_connection() as conn:
            row = conn.execute(
                """
                select de.*, ms.name as model_name, ae.name as endpoint_name
                from digital_employees de
                left join model_services ms on ms.id = de.model_id
                left join api_endpoints ae on ae.id = de.endpoint_id
                where de.id=?
                """,
                (employee_id,),
            ).fetchone()
        return DigitalEmployeeRepository._row_to_dict(row)

    @staticmethod
    def get_employee_by_alias(alias: str):
        with get_connection() as conn:
            row = conn.execute(
                """
                select de.*, ms.name as model_name, ae.name as endpoint_name
                from digital_employees de
                left join model_services ms on ms.id = de.model_id
                left join api_endpoints ae on ae.id = de.endpoint_id
                where de.alias=? and de.status=1
                limit 1
                """,
                ((alias or "").strip(),),
            ).fetchone()
        return DigitalEmployeeRepository._row_to_dict(row)

    @staticmethod
    def get_employee_options():
        with get_connection() as conn:
            rows = conn.execute(
                """
                select id,name,alias,code,category,description,default_user_input,api_param_name
                from digital_employees
                where status=1
                order by sort asc,id asc
                """
            ).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def save_employee(data: Dict, employee_id: Optional[int] = None):
        name = (data.get("name") or "").strip()
        alias = (data.get("alias") or "").strip()
        code = (data.get("code") or "").strip()
        category = (data.get("category") or DigitalEmployeeRepository.EMPLOYEE_AI).strip()
        prompt = (data.get("prompt") or "").strip()
        api_param_name = (data.get("api_param_name") or "").strip()
        api_params_json = (data.get("api_params_json") or "{}").strip() or "{}"
        response_template = (data.get("response_template") or "").strip()
        default_user_input = (data.get("default_user_input") or "").strip()
        description = (data.get("description") or "").strip()
        sort = int(data.get("sort") or 0)
        status = int(data.get("status") or 1)

        if not name or not alias or not code:
            return False, "员工名称、别名、编码不能为空"
        if category not in (DigitalEmployeeRepository.EMPLOYEE_AI, DigitalEmployeeRepository.EMPLOYEE_NORMAL):
            return False, "员工分类不正确"

        try:
            json.loads(api_params_json)
        except json.JSONDecodeError:
            return False, "默认参数JSON格式不正确"

        model_id = data.get("model_id")
        endpoint_id = data.get("endpoint_id")
        model_id = int(model_id) if str(model_id or "").strip() else None
        endpoint_id = int(endpoint_id) if str(endpoint_id or "").strip() else None

        if category == DigitalEmployeeRepository.EMPLOYEE_NORMAL and not endpoint_id:
            return False, "普通员工必须绑定接口服务"

        with get_connection() as conn:
            duplicate_sql = "select id from digital_employees where (name=? or alias=? or code=?)"
            duplicate_params = [name, alias, code]
            if employee_id:
                duplicate_sql += " and id<>?"
                duplicate_params.append(employee_id)
            duplicate = conn.execute(duplicate_sql, tuple(duplicate_params)).fetchone()
            if duplicate:
                return False, "员工名称、别名或编码已存在"

            if model_id:
                model_row = conn.execute("select id from model_services where id=?", (model_id,)).fetchone()
                if not model_row:
                    return False, "绑定模型不存在"
            if endpoint_id:
                endpoint_row = conn.execute("select id from api_endpoints where id=?", (endpoint_id,)).fetchone()
                if not endpoint_row:
                    return False, "绑定接口不存在"

            payload = (
                name,
                alias,
                code,
                category,
                model_id if category == DigitalEmployeeRepository.EMPLOYEE_AI else None,
                endpoint_id if category == DigitalEmployeeRepository.EMPLOYEE_NORMAL else None,
                prompt if category == DigitalEmployeeRepository.EMPLOYEE_AI else "",
                api_param_name if category == DigitalEmployeeRepository.EMPLOYEE_NORMAL else "",
                api_params_json,
                response_template if category == DigitalEmployeeRepository.EMPLOYEE_NORMAL else "",
                default_user_input,
                description,
                sort,
                status,
            )

            if employee_id:
                conn.execute(
                    """
                    update digital_employees
                    set name=?,alias=?,code=?,category=?,model_id=?,endpoint_id=?,prompt=?,api_param_name=?,
                        api_params_json=?,response_template=?,default_user_input=?,description=?,sort=?,status=?,
                        update_at=datetime('now')
                    where id=?
                    """,
                    payload + (employee_id,),
                )
            else:
                conn.execute(
                    """
                    insert into digital_employees(
                        name,alias,code,category,model_id,endpoint_id,prompt,api_param_name,api_params_json,
                        response_template,default_user_input,description,sort,status,create_at,update_at
                    ) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'),datetime('now'))
                    """,
                    payload,
                )
        return True, "保存成功"

    @staticmethod
    def delete_employee(employee_id: int):
        with get_connection() as conn:
            conn.execute("delete from digital_employees where id=?", (employee_id,))
        return True, "删除成功"

    @staticmethod
    def parse_at_message(message: str):
        match = DigitalEmployeeRepository.AT_PATTERN.match((message or "").strip())
        if not match:
            return None
        return {"alias": match.group(1).strip(), "content": (match.group(2) or "").strip()}

    @staticmethod
    def _get_employee_request_text(employee: Dict, user_text: str):
        text = (user_text or "").strip()
        return text or (employee.get("default_user_input") or "").strip()

    @staticmethod
    def _resolve_model_config(employee: Dict):
        if employee.get("model_id"):
            config = ModelEngineRepository.get_model_by_id(int(employee["model_id"]), include_secret=True)
        else:
            config = ModelEngineRepository.get_default_model(include_secret=True)
            if not config:
                config = ModelEngineRepository.get_first_active_model(include_secret=True)
        if not config:
            raise RuntimeError("当前数字员工未绑定模型，且系统中暂无启用模型，请先到模型引擎中启用一个模型或设为默认模型")
        config = copy.deepcopy(config)
        prompts = []
        if config.get("system_prompt"):
            prompts.append(config["system_prompt"])
        if employee.get("prompt"):
            prompts.append(employee["prompt"])
        config["system_prompt"] = "\n\n".join([item for item in prompts if item]).strip()
        return config

    @staticmethod
    def _resolve_api_content(employee: Dict, user_text: str):
        endpoint_id = int(employee.get("endpoint_id") or 0)
        endpoint = ApiEndpointRepository.get_endpoint_by_id(endpoint_id)
        if not endpoint:
            raise RuntimeError("当前数字员工绑定的接口不存在")

        params = _safe_json_loads(employee.get("api_params_json"), {})
        request_text = DigitalEmployeeRepository._get_employee_request_text(employee, user_text)
        param_name = (employee.get("api_param_name") or "").strip()
        if param_name and request_text:
            params[param_name] = request_text
        if param_name and not params.get(param_name):
            raise RuntimeError(f"请使用 @{employee['alias']} 后补充参数内容")

        result = ApiEndpointRepository.call_endpoint(endpoint, params=params)
        payload = result.get("json") if result.get("json") is not None else {"text": result.get("text", "")}
        content = _render_template(employee.get("response_template") or "", payload)
        if not content:
            content = json.dumps(payload, ensure_ascii=False, indent=2)
        return {
            "content": content,
            "payload": payload,
            "status_code": result.get("status_code"),
            "content_type": result.get("content_type"),
        }

    @staticmethod
    async def chat_once(message: str):
        parsed = DigitalEmployeeRepository.parse_at_message(message)
        if not parsed:
            raise RuntimeError("请使用 @数字员工别名 进行调用，例如：@天气 北京市")

        employee = DigitalEmployeeRepository.get_employee_by_alias(parsed["alias"])
        if not employee:
            raise RuntimeError(f"未找到别名为 @{parsed['alias']} 的数字员工")

        user_text = parsed["content"]
        if employee["category"] == DigitalEmployeeRepository.EMPLOYEE_AI:
            request_text = DigitalEmployeeRepository._get_employee_request_text(employee, user_text)
            if not request_text:
                raise RuntimeError(f"请在 @{employee['alias']} 后输入问题内容")
            config = DigitalEmployeeRepository._resolve_model_config(employee)
            try:
                result = await ModelEngineClient.chat_once(config, request_text)
                ModelEngineRepository.log_usage(
                    model_id=config["id"],
                    model_name=config["name"],
                    request_preview=request_text,
                    response_preview=result["content"],
                    prompt_tokens=result["prompt_tokens"],
                    completion_tokens=result["completion_tokens"],
                    total_tokens=result["total_tokens"],
                    response_ms=result["response_ms"],
                    success=1,
                )
                return {
                    "employee": employee,
                    "category": employee["category"],
                    "content": result["content"],
                    "prompt_tokens": result["prompt_tokens"],
                    "completion_tokens": result["completion_tokens"],
                    "total_tokens": result["total_tokens"],
                    "response_ms": result["response_ms"],
                }
            except Exception as exc:
                ModelEngineRepository.log_usage(
                    model_id=config["id"],
                    model_name=config["name"],
                    request_preview=request_text,
                    response_preview="",
                    prompt_tokens=0,
                    completion_tokens=0,
                    total_tokens=0,
                    response_ms=0,
                    success=0,
                    error_message=str(exc),
                )
                raise

        api_result = DigitalEmployeeRepository._resolve_api_content(employee, user_text)
        weather_card = None
        payload = api_result["payload"]
        if isinstance(payload, dict) and ("天气" in employee.get("alias", "") or "天气" in employee.get("name", "")):
            weather_payload = payload.get("data") if isinstance(payload.get("data"), dict) else payload
            if isinstance(weather_payload, dict):
                weather_card = weather_payload
        return {
            "employee": employee,
            "category": employee["category"],
            "content": api_result["content"],
            "payload": payload,
            "weather_card": weather_card,
            "status_code": api_result["status_code"],
            "content_type": api_result["content_type"],
        }

    @staticmethod
    async def stream_chat(message: str):
        parsed = DigitalEmployeeRepository.parse_at_message(message)
        if not parsed:
            raise RuntimeError("请使用 @数字员工别名 进行调用，例如：@天气 北京市")

        employee = DigitalEmployeeRepository.get_employee_by_alias(parsed["alias"])
        if not employee:
            raise RuntimeError(f"未找到别名为 @{parsed['alias']} 的数字员工")

        user_text = parsed["content"]
        if employee["category"] == DigitalEmployeeRepository.EMPLOYEE_AI:
            request_text = DigitalEmployeeRepository._get_employee_request_text(employee, user_text)
            if not request_text:
                raise RuntimeError(f"请在 @{employee['alias']} 后输入问题内容")
            config = DigitalEmployeeRepository._resolve_model_config(employee)
            try:
                async for item in ModelEngineClient.stream_chat(config, request_text):
                    if item["type"] == "delta":
                        yield {
                            "type": "delta",
                            "employee": {"name": employee["name"], "alias": employee["alias"], "category": employee["category"]},
                            "content": item["content"],
                        }
                    elif item["type"] == "done":
                        ModelEngineRepository.log_usage(
                            model_id=config["id"],
                            model_name=config["name"],
                            request_preview=request_text,
                            response_preview=item["content"],
                            prompt_tokens=item["prompt_tokens"],
                            completion_tokens=item["completion_tokens"],
                            total_tokens=item["total_tokens"],
                            response_ms=item["response_ms"],
                            success=1,
                        )
                        yield {
                            "type": "done",
                            "employee": {"name": employee["name"], "alias": employee["alias"], "category": employee["category"]},
                            "content": item["content"],
                            "prompt_tokens": item["prompt_tokens"],
                            "completion_tokens": item["completion_tokens"],
                            "total_tokens": item["total_tokens"],
                            "response_ms": item["response_ms"],
                        }
            except Exception as exc:
                ModelEngineRepository.log_usage(
                    model_id=config["id"],
                    model_name=config["name"],
                    request_preview=request_text,
                    response_preview="",
                    prompt_tokens=0,
                    completion_tokens=0,
                    total_tokens=0,
                    response_ms=0,
                    success=0,
                    error_message=str(exc),
                )
                raise
            return

        api_result = DigitalEmployeeRepository._resolve_api_content(employee, user_text)
        weather_card = None
        payload = api_result["payload"]
        if isinstance(payload, dict) and ("天气" in employee.get("alias", "") or "天气" in employee.get("name", "")):
            weather_payload = payload.get("data") if isinstance(payload.get("data"), dict) else payload
            if isinstance(weather_payload, dict):
                weather_card = weather_payload
        yield {
            "type": "done",
            "employee": {"name": employee["name"], "alias": employee["alias"], "category": employee["category"]},
            "content": api_result["content"],
            "payload": payload,
            "weather_card": weather_card,
            "status_code": api_result["status_code"],
            "content_type": api_result["content_type"],
        }
