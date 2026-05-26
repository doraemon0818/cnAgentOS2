import json

import tornado.web

from app.controllers.admin import AdminBaseHandler
from app.models.model_engine import ModelEngineClient, ModelEngineRepository


class AdminModelListHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		self.render("admin/model/list.html", title="模型引擎", username=self.current_user)


class AdminModelApiHandler(AdminBaseHandler):
	def _write_json(self, data):
		self.set_header("Content-Type", "application/json")
		self.write(json.dumps(data, ensure_ascii=False))

	@tornado.web.authenticated
	def get(self):
		action = self.get_argument("action", "list")

		if action == "detail":
			model_id = int(self.get_argument("id", 0))
			data = ModelEngineRepository.get_model_by_id(model_id, include_secret=True)
			if not data:
				self._write_json({"code": 1, "msg": "模型服务不存在"})
				return
			self._write_json({"code": 0, "msg": "", "data": data})
			return

		if action == "options":
			self._write_json({"code": 0, "msg": "", "data": ModelEngineRepository.get_model_options()})
			return

		if action == "summary":
			self._write_json({"code": 0, "msg": "", "data": ModelEngineRepository.get_dashboard_summary()})
			return

		if action == "stats":
			page = int(self.get_argument("page", 1))
			limit = int(self.get_argument("limit", 6))
			result = ModelEngineRepository.get_usage_stat_cards(page=page, page_size=limit)
			self._write_json({"code": 0, "msg": "", "count": result["total"], "data": result["list"]})
			return

		page = int(self.get_argument("page", 1))
		limit = int(self.get_argument("limit", 6))
		keyword = (self.get_argument("keyword", "") or "").strip()
		result = ModelEngineRepository.get_model_cards(page=page, page_size=limit, keyword=keyword)
		self._write_json({"code": 0, "msg": "", "count": result["total"], "data": result["list"]})

	@tornado.web.authenticated
	def post(self):
		action = self.get_argument("action", "")
		if action == "delete":
			model_id = int(self.get_body_argument("id", 0))
			success, message = ModelEngineRepository.delete_model(model_id)
			self._write_json({"code": 0 if success else 1, "msg": message})
			return

		if action == "set_default":
			model_id = int(self.get_body_argument("id", 0))
			success, message = ModelEngineRepository.set_default_model(model_id)
			self._write_json({"code": 0 if success else 1, "msg": message})
			return

		payload = {
			"name": self.get_body_argument("name", ""),
			"provider": self.get_body_argument("provider", "openai-compatible"),
			"base_url": self.get_body_argument("base_url", ""),
			"api_path": self.get_body_argument("api_path", "/chat/completions"),
			"api_key": self.get_body_argument("api_key", ""),
			"model_name": self.get_body_argument("model_name", ""),
			"system_prompt": self.get_body_argument("system_prompt", ""),
			"temperature": self.get_body_argument("temperature", "0.7"),
			"max_tokens": self.get_body_argument("max_tokens", "2048"),
			"timeout_seconds": self.get_body_argument("timeout_seconds", "60"),
			"enable_sse": self.get_body_argument("enable_sse", "0"),
			"is_default": self.get_body_argument("is_default", "0"),
			"status": self.get_body_argument("status", "1"),
			"description": self.get_body_argument("description", ""),
		}

		if action == "add":
			success, message = ModelEngineRepository.save_model(payload)
			self._write_json({"code": 0 if success else 1, "msg": message})
			return

		if action == "update":
			model_id = int(self.get_body_argument("id", 0))
			success, message = ModelEngineRepository.save_model(payload, model_id=model_id)
			self._write_json({"code": 0 if success else 1, "msg": message})
			return

		self._write_json({"code": 1, "msg": "未知操作"})


class AdminModelTestHandler(AdminBaseHandler):
	def _write_json(self, data):
		self.set_header("Content-Type", "application/json")
		self.write(json.dumps(data, ensure_ascii=False))

	@tornado.web.authenticated
	async def post(self):
		model_id = int(self.get_body_argument("model_id", 0))
		message = (self.get_body_argument("message", "") or "").strip()
		if not model_id or not message:
			self._write_json({"code": 1, "msg": "模型和测试内容不能为空"})
			return

		config = ModelEngineRepository.get_model_by_id(model_id, include_secret=True)
		if not config:
			self._write_json({"code": 1, "msg": "模型不存在"})
			return

		try:
			result = await ModelEngineClient.chat_once(config, message)
			ModelEngineRepository.log_usage(
				model_id=config["id"],
				model_name=config["name"],
				request_preview=message,
				response_preview=result["content"],
				prompt_tokens=result["prompt_tokens"],
				completion_tokens=result["completion_tokens"],
				total_tokens=result["total_tokens"],
				response_ms=result["response_ms"],
				success=1,
			)
			self._write_json({
				"code": 0,
				"msg": "测试成功",
				"data": {
					"content": result["content"],
					"prompt_tokens": result["prompt_tokens"],
					"completion_tokens": result["completion_tokens"],
					"total_tokens": result["total_tokens"],
					"response_ms": result["response_ms"],
				},
			})
		except Exception as exc:
			ModelEngineRepository.log_usage(
				model_id=config["id"],
				model_name=config["name"],
				request_preview=message,
				response_preview="",
				prompt_tokens=0,
				completion_tokens=0,
				total_tokens=0,
				response_ms=0,
				success=0,
				error_message=str(exc),
			)
			self._write_json({"code": 1, "msg": str(exc)})


class AdminModelStreamHandler(AdminBaseHandler):
	@tornado.web.authenticated
	async def get(self):
		model_id = int(self.get_argument("model_id", 0))
		message = (self.get_argument("message", "") or "").strip()
		if not model_id or not message:
			self.set_status(400)
			self.write("data: " + json.dumps({"type": "error", "message": "模型和测试内容不能为空"}, ensure_ascii=False) + "\n\n")
			return

		config = ModelEngineRepository.get_model_by_id(model_id, include_secret=True)
		if not config:
			self.set_status(404)
			self.write("data: " + json.dumps({"type": "error", "message": "模型不存在"}, ensure_ascii=False) + "\n\n")
			return

		self.set_header("Content-Type", "text/event-stream; charset=utf-8")
		self.set_header("Cache-Control", "no-cache")
		self.set_header("Connection", "keep-alive")
		await self.flush()

		try:
			async for item in ModelEngineClient.stream_chat(config, message):
				if item["type"] == "delta":
					self.write("data: " + json.dumps({"type": "delta", "content": item["content"]}, ensure_ascii=False) + "\n\n")
					await self.flush()
				elif item["type"] == "done":
					ModelEngineRepository.log_usage(
						model_id=config["id"],
						model_name=config["name"],
						request_preview=message,
						response_preview=item["content"],
						prompt_tokens=item["prompt_tokens"],
						completion_tokens=item["completion_tokens"],
						total_tokens=item["total_tokens"],
						response_ms=item["response_ms"],
						success=1,
					)
					self.write("data: " + json.dumps({
						"type": "done",
						"prompt_tokens": item["prompt_tokens"],
						"completion_tokens": item["completion_tokens"],
						"total_tokens": item["total_tokens"],
						"response_ms": item["response_ms"],
					}, ensure_ascii=False) + "\n\n")
					await self.flush()
		except Exception as exc:
			ModelEngineRepository.log_usage(
				model_id=config["id"],
				model_name=config["name"],
				request_preview=message,
				response_preview="",
				prompt_tokens=0,
				completion_tokens=0,
				total_tokens=0,
				response_ms=0,
				success=0,
				error_message=str(exc),
			)
			self.write("data: " + json.dumps({"type": "error", "message": str(exc)}, ensure_ascii=False) + "\n\n")
			await self.flush()
