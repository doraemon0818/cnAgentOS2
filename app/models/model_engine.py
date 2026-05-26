import copy
import json
import time
from typing import Dict, List, Optional

import aiohttp

from app.models.db import get_connection


def _mask_api_key(api_key: str) -> str:
	if not api_key:
		return ""
	if len(api_key) <= 10:
		return "*" * len(api_key)
	return f"{api_key[:6]}******{api_key[-4:]}"


def _estimate_tokens(text: str) -> int:
	if not text:
		return 0
	return max(1, len(text.encode("utf-8")) // 4)


def _normalize_api_path(api_path: str) -> str:
	api_path = (api_path or "/chat/completions").strip()
	if not api_path.startswith("/"):
		api_path = "/" + api_path
	return api_path


def _build_endpoint(base_url: str, api_path: str) -> str:
	return base_url.rstrip("/") + _normalize_api_path(api_path)


class ModelEngineRepository:
	@staticmethod
	def get_model_by_id(model_id: int, include_secret: bool = False):
		with get_connection() as conn:
			row = conn.execute(
				"""
				select id,name,provider,base_url,api_path,api_key,model_name,system_prompt,
					   temperature,max_tokens,timeout_seconds,enable_sse,is_default,status,
					   description,create_at,update_at
				from model_services
				where id=?
				""",
				(model_id,),
			).fetchone()
		if not row:
			return None
		data = dict(row)
		data["api_key_masked"] = _mask_api_key(data["api_key"])
		if not include_secret:
			data.pop("api_key", None)
		return data

	@staticmethod
	def get_default_model(include_secret: bool = True):
		with get_connection() as conn:
			row = conn.execute(
				"""
				select id,name,provider,base_url,api_path,api_key,model_name,system_prompt,
					   temperature,max_tokens,timeout_seconds,enable_sse,is_default,status,
					   description,create_at,update_at
				from model_services
				where is_default=1 and status=1
				order by id desc
				limit 1
				"""
			).fetchone()
		if not row:
			return None
		data = dict(row)
		data["api_key_masked"] = _mask_api_key(data["api_key"])
		if not include_secret:
			data.pop("api_key", None)
		return data

	@staticmethod
	def get_first_active_model(include_secret: bool = True):
		with get_connection() as conn:
			row = conn.execute(
				"""
				select id,name,provider,base_url,api_path,api_key,model_name,system_prompt,
					   temperature,max_tokens,timeout_seconds,enable_sse,is_default,status,
					   description,create_at,update_at
				from model_services
				where status=1
				order by is_default desc,id asc
				limit 1
				"""
			).fetchone()
		if not row:
			return None
		data = dict(row)
		data["api_key_masked"] = _mask_api_key(data["api_key"])
		if not include_secret:
			data.pop("api_key", None)
		return data

	@staticmethod
	def get_model_options():
		with get_connection() as conn:
			rows = conn.execute(
				"""
				select id,name,model_name,is_default,status
				from model_services
				where status=1
				order by is_default desc,id asc
				"""
			).fetchall()
		return [dict(row) for row in rows]

	@staticmethod
	def get_model_cards(page: int = 1, page_size: int = 6, keyword: str = ""):
		offset = (page - 1) * page_size
		params: List = []
		where_sql = ""
		if keyword:
			where_sql = """
				where ms.name like ? or ms.model_name like ? or ms.base_url like ? or ms.description like ?
			"""
			like_value = f"%{keyword}%"
			params.extend([like_value, like_value, like_value, like_value])

		sql = f"""
			select ms.id,ms.name,ms.provider,ms.base_url,ms.api_path,ms.api_key,ms.model_name,
				   ms.system_prompt,ms.temperature,ms.max_tokens,ms.timeout_seconds,ms.enable_sse,
				   ms.is_default,ms.status,ms.description,ms.create_at,ms.update_at,
				   count(mul.id) as call_count,
				   coalesce(sum(mul.total_tokens),0) as total_tokens,
				   coalesce(avg(case when mul.success=1 then mul.response_ms end),0) as avg_response_ms,
				   max(mul.create_at) as last_called_at
			from model_services ms
			left join model_usage_logs mul on mul.model_id = ms.id
			{where_sql}
			group by ms.id,ms.name,ms.provider,ms.base_url,ms.api_path,ms.api_key,ms.model_name,
					 ms.system_prompt,ms.temperature,ms.max_tokens,ms.timeout_seconds,ms.enable_sse,
					 ms.is_default,ms.status,ms.description,ms.create_at,ms.update_at
			order by ms.is_default desc,ms.status desc,ms.id desc
			limit ? offset ?
		"""
		count_sql = f"select count(*) as total from model_services ms {where_sql}"

		with get_connection() as conn:
			rows = conn.execute(sql, tuple(params + [page_size, offset])).fetchall()
			total = conn.execute(count_sql, tuple(params)).fetchone()["total"]

		data = []
		for row in rows:
			item = dict(row)
			item["api_key_masked"] = _mask_api_key(item["api_key"])
			item.pop("api_key", None)
			data.append(item)
		return {"list": data, "total": total}

	@staticmethod
	def get_dashboard_summary():
		with get_connection() as conn:
			model_summary = conn.execute(
				"""
				select
					count(*) as total_models,
					sum(case when status=1 then 1 else 0 end) as enabled_models,
					sum(case when is_default=1 then 1 else 0 end) as default_models,
					sum(case when enable_sse=1 then 1 else 0 end) as sse_models
				from model_services
				"""
			).fetchone()
			usage_summary = conn.execute(
				"""
				select
					count(*) as total_calls,
					coalesce(sum(total_tokens),0) as total_tokens,
					coalesce(avg(case when success=1 then response_ms end),0) as avg_response_ms,
					sum(case when success=1 then 1 else 0 end) as success_calls
				from model_usage_logs
				"""
			).fetchone()
			default_row = conn.execute(
				"select name from model_services where is_default=1 and status=1 limit 1"
			).fetchone()

		total_calls = usage_summary["total_calls"] or 0
		success_calls = usage_summary["success_calls"] or 0
		success_rate = round((success_calls / total_calls) * 100, 2) if total_calls else 0
		return {
			"total_models": model_summary["total_models"] or 0,
			"enabled_models": model_summary["enabled_models"] or 0,
			"default_models": model_summary["default_models"] or 0,
			"sse_models": model_summary["sse_models"] or 0,
			"total_calls": total_calls,
			"total_tokens": usage_summary["total_tokens"] or 0,
			"avg_response_ms": round(usage_summary["avg_response_ms"] or 0),
			"success_rate": success_rate,
			"default_model_name": default_row["name"] if default_row else "未设置",
		}

	@staticmethod
	def get_usage_stat_cards(page: int = 1, page_size: int = 6):
		offset = (page - 1) * page_size
		sql = """
			select
				ms.id as model_id,
				ms.name,
				ms.model_name,
				ms.provider,
				ms.is_default,
				ms.status,
				count(mul.id) as total_calls,
				sum(case when mul.success=1 then 1 else 0 end) as success_calls,
				coalesce(sum(mul.prompt_tokens),0) as prompt_tokens,
				coalesce(sum(mul.completion_tokens),0) as completion_tokens,
				coalesce(sum(mul.total_tokens),0) as total_tokens,
				coalesce(avg(case when mul.success=1 then mul.response_ms end),0) as avg_response_ms,
				max(mul.create_at) as last_called_at
			from model_services ms
			left join model_usage_logs mul on mul.model_id = ms.id
			group by ms.id,ms.name,ms.model_name,ms.provider,ms.is_default,ms.status
			order by total_tokens desc, total_calls desc, ms.id desc
			limit ? offset ?
		"""
		count_sql = "select count(*) as total from model_services"
		with get_connection() as conn:
			rows = conn.execute(sql, (page_size, offset)).fetchall()
			total = conn.execute(count_sql).fetchone()["total"]

		data = []
		for row in rows:
			item = dict(row)
			total_calls = item["total_calls"] or 0
			success_calls = item["success_calls"] or 0
			item["success_rate"] = round((success_calls / total_calls) * 100, 2) if total_calls else 0
			item["avg_response_ms"] = round(item["avg_response_ms"] or 0)
			data.append(item)
		return {"list": data, "total": total}

	@staticmethod
	def _set_default(conn, model_id: int):
		conn.execute("update model_services set is_default=0")
		conn.execute(
			"update model_services set is_default=1, update_at=datetime('now','localtime') where id=?",
			(model_id,),
		)

	@staticmethod
	def save_model(data: Dict, model_id: Optional[int] = None):
		name = (data.get("name") or "").strip()
		base_url = (data.get("base_url") or "").strip()
		api_key = (data.get("api_key") or "").strip()
		model_name = (data.get("model_name") or "").strip()
		api_path = _normalize_api_path(data.get("api_path") or "/chat/completions")
		if not name or not base_url or not api_key or not model_name:
			return False, "模型名称、基础地址、API Key、模型标识不能为空"

		provider = (data.get("provider") or "openai-compatible").strip()
		system_prompt = (data.get("system_prompt") or "").strip()
		temperature = float(data.get("temperature") or 0.7)
		max_tokens = int(data.get("max_tokens") or 2048)
		timeout_seconds = int(data.get("timeout_seconds") or 60)
		enable_sse = int(data.get("enable_sse") or 0)
		is_default = int(data.get("is_default") or 0)
		status = int(data.get("status") or 1)
		description = (data.get("description") or "").strip()

		with get_connection() as conn:
			if model_id:
				duplicate = conn.execute(
					"select id from model_services where name=? and id<>?",
					(name, model_id),
				).fetchone()
			else:
				duplicate = conn.execute(
					"select id from model_services where name=?",
					(name,),
				).fetchone()
			if duplicate:
				return False, "模型名称已存在"

			if model_id:
				conn.execute(
					"""
					update model_services
					set name=?,provider=?,base_url=?,api_path=?,api_key=?,model_name=?,system_prompt=?,
						temperature=?,max_tokens=?,timeout_seconds=?,enable_sse=?,status=?,description=?,
						update_at=datetime('now','localtime')
					where id=?
					""",
					(
						name,
						provider,
						base_url,
						api_path,
						api_key,
						model_name,
						system_prompt,
						temperature,
						max_tokens,
						timeout_seconds,
						enable_sse,
						status,
						description,
						model_id,
					),
				)
				if is_default == 1:
					ModelEngineRepository._set_default(conn, model_id)
			else:
				cursor = conn.execute(
					"""
					insert into model_services(
						name,provider,base_url,api_path,api_key,model_name,system_prompt,
						temperature,max_tokens,timeout_seconds,enable_sse,is_default,status,description,create_at,update_at
					) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now','localtime'),datetime('now','localtime'))
					""",
					(
						name,
						provider,
						base_url,
						api_path,
						api_key,
						model_name,
						system_prompt,
						temperature,
						max_tokens,
						timeout_seconds,
						enable_sse,
						0,
						status,
						description,
					),
				)
				model_id = cursor.lastrowid
				if is_default == 1:
					ModelEngineRepository._set_default(conn, model_id)
		return True, "保存成功"

	@staticmethod
	def delete_model(model_id: int):
		with get_connection() as conn:
			conn.execute("delete from model_usage_logs where model_id=?", (model_id,))
			conn.execute("delete from model_services where id=?", (model_id,))
		return True, "删除成功"

	@staticmethod
	def set_default_model(model_id: int):
		with get_connection() as conn:
			row = conn.execute("select id from model_services where id=?", (model_id,)).fetchone()
			if not row:
				return False, "模型不存在"
			ModelEngineRepository._set_default(conn, model_id)
		return True, "已设为系统默认模型"

	@staticmethod
	def log_usage(
		model_id: int,
		model_name: str,
		request_preview: str,
		response_preview: str,
		prompt_tokens: int,
		completion_tokens: int,
		total_tokens: int,
		response_ms: int,
		success: int,
		error_message: str = "",
	):
		with get_connection() as conn:
			conn.execute(
				"""
				insert into model_usage_logs(
					model_id,model_name,request_preview,response_preview,prompt_tokens,
					completion_tokens,total_tokens,response_ms,success,error_message,create_at
				) values(?,?,?,?,?,?,?,?,?,?,datetime('now','localtime'))
				""",
				(
					model_id,
					model_name,
					(request_preview or "")[:200],
					(response_preview or "")[:300],
					prompt_tokens,
					completion_tokens,
					total_tokens,
					response_ms,
					success,
					(error_message or "")[:500],
				),
			)


class ModelEngineClient:
	@staticmethod
	def _build_messages(config: Dict, user_message: str = "", messages: Optional[List[Dict]] = None):
		request_messages = []
		history_messages = messages or []
		system_prompt = (config.get("system_prompt") or "").strip()
		if system_prompt:
			request_messages.append({"role": "system", "content": system_prompt})
		if history_messages:
			for item in history_messages:
				role = (item or {}).get("role")
				content = (item or {}).get("content")
				if role in ("system", "user", "assistant") and content is not None:
					request_messages.append({"role": role, "content": str(content)})
		elif user_message:
			request_messages.append({"role": "user", "content": user_message})
		return request_messages

	@staticmethod
	async def chat_once(config: Dict, user_message: str = "", messages: Optional[List[Dict]] = None):
		start_time = time.time()
		endpoint = _build_endpoint(config["base_url"], config.get("api_path") or "/chat/completions")
		request_messages = ModelEngineClient._build_messages(config, user_message=user_message, messages=messages)
		payload = {
			"model": config["model_name"],
			"messages": request_messages,
			"temperature": config.get("temperature", 0.7),
			"max_tokens": config.get("max_tokens", 2048),
			"stream": False,
		}
		headers = {
			"Authorization": f"Bearer {config['api_key']}",
			"Content-Type": "application/json",
		}
		timeout = aiohttp.ClientTimeout(total=int(config.get("timeout_seconds") or 60))

		async with aiohttp.ClientSession(timeout=timeout) as session:
			async with session.post(endpoint, headers=headers, json=payload) as response:
				text = await response.text()
				if response.status >= 400:
					raise RuntimeError(f"接口调用失败({response.status})：{text[:300]}")
				data = json.loads(text)

		choices = data.get("choices") or []
		content = ""
		if choices:
			message = choices[0].get("message") or {}
			content = message.get("content") or ""

		usage = data.get("usage") or {}
		prompt_text = json.dumps(request_messages, ensure_ascii=False)
		prompt_tokens = int(usage.get("prompt_tokens") or _estimate_tokens(prompt_text))
		completion_tokens = int(usage.get("completion_tokens") or _estimate_tokens(content))
		total_tokens = int(usage.get("total_tokens") or (prompt_tokens + completion_tokens))
		response_ms = int((time.time() - start_time) * 1000)
		return {
			"content": content,
			"raw": data,
			"prompt_tokens": prompt_tokens,
			"completion_tokens": completion_tokens,
			"total_tokens": total_tokens,
			"response_ms": response_ms,
		}

	@staticmethod
	async def stream_chat(config: Dict, user_message: str = "", messages: Optional[List[Dict]] = None):
		endpoint = _build_endpoint(config["base_url"], config.get("api_path") or "/chat/completions")
		request_messages = ModelEngineClient._build_messages(config, user_message=user_message, messages=messages)
		payload = {
			"model": config["model_name"],
			"messages": request_messages,
			"temperature": config.get("temperature", 0.7),
			"max_tokens": config.get("max_tokens", 2048),
			"stream": True,
			"stream_options": {"include_usage": True},
		}
		headers = {
			"Authorization": f"Bearer {config['api_key']}",
			"Content-Type": "application/json",
		}
		timeout = aiohttp.ClientTimeout(total=int(config.get("timeout_seconds") or 60))

		start_time = time.time()
		full_content = []
		usage_info = {}
		async with aiohttp.ClientSession(timeout=timeout) as session:
			async with session.post(endpoint, headers=headers, json=payload) as response:
				if response.status >= 400:
					text = await response.text()
					raise RuntimeError(f"接口调用失败({response.status})：{text[:300]}")

				async for raw_line in response.content:
					line = raw_line.decode("utf-8", errors="ignore").strip()
					if not line or not line.startswith("data:"):
						continue

					payload_text = line[5:].strip()
					if payload_text == "[DONE]":
						break

					try:
						event = json.loads(payload_text)
					except json.JSONDecodeError:
						continue

					choices = event.get("choices") or []
					delta = ""
					if choices:
						delta = (choices[0].get("delta") or {}).get("content") or ""
					if delta:
						full_content.append(delta)
						yield {"type": "delta", "content": delta}

					if event.get("usage"):
						usage_info = event["usage"]

		content = "".join(full_content)
		prompt_text = json.dumps(request_messages, ensure_ascii=False)
		prompt_tokens = int(usage_info.get("prompt_tokens") or _estimate_tokens(prompt_text))
		completion_tokens = int(usage_info.get("completion_tokens") or _estimate_tokens(content))
		total_tokens = int(usage_info.get("total_tokens") or (prompt_tokens + completion_tokens))
		response_ms = int((time.time() - start_time) * 1000)
		yield {
			"type": "done",
			"content": content,
			"prompt_tokens": prompt_tokens,
			"completion_tokens": completion_tokens,
			"total_tokens": total_tokens,
			"response_ms": response_ms,
		}
