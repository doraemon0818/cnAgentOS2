import json

import tornado.web

from app.controllers.admin import AdminBaseHandler
from app.models.api_endpoint import ApiEndpointRepository


class AdminInterfaceListHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		self.render("admin/interface/list.html", title="接口管理", username=self.current_user)


class AdminInterfaceApiHandler(AdminBaseHandler):
	def _write_json(self, data):
		self.set_header("Content-Type", "application/json")
		self.write(json.dumps(data, ensure_ascii=False))

	@tornado.web.authenticated
	def get(self):
		action = self.get_argument("action", "list")
		if action == "detail":
			endpoint_id = int(self.get_argument("id", 0))
			data = ApiEndpointRepository.get_endpoint_by_id(endpoint_id)
			if not data:
				self._write_json({"code": 1, "msg": "接口不存在"})
				return
			self._write_json({"code": 0, "msg": "", "data": data})
			return

		if action == "options":
			self._write_json({"code": 0, "msg": "", "data": ApiEndpointRepository.get_endpoint_options()})
			return

		page = int(self.get_argument("page", 1))
		limit = int(self.get_argument("limit", 20))
		keyword = (self.get_argument("keyword", "") or "").strip()
		result = ApiEndpointRepository.get_endpoint_list(page=page, page_size=limit, keyword=keyword)
		self._write_json({"code": 0, "msg": "", "count": result["total"], "data": result["list"]})

	@tornado.web.authenticated
	def post(self):
		action = self.get_argument("action", "")
		if action == "delete":
			endpoint_id = int(self.get_body_argument("id", 0))
			success, message = ApiEndpointRepository.delete_endpoint(endpoint_id)
			self._write_json({"code": 0 if success else 1, "msg": message})
			return

		payload = {
			"name": self.get_body_argument("name", ""),
			"code": self.get_body_argument("code", ""),
			"url": self.get_body_argument("url", ""),
			"method": self.get_body_argument("method", "GET"),
			"response_format": self.get_body_argument("response_format", "JSON"),
			"sample_url": self.get_body_argument("sample_url", ""),
			"default_qps": self.get_body_argument("default_qps", ""),
			"auth_note": self.get_body_argument("auth_note", ""),
			"remark": self.get_body_argument("remark", ""),
			"headers_json": self.get_body_argument("headers_json", "{}"),
			"params_schema_json": self.get_body_argument("params_schema_json", "[]"),
			"body_template": self.get_body_argument("body_template", ""),
			"timeout_seconds": self.get_body_argument("timeout_seconds", "20"),
			"status": self.get_body_argument("status", "1"),
		}

		if action == "add":
			success, message = ApiEndpointRepository.save_endpoint(payload)
			self._write_json({"code": 0 if success else 1, "msg": message})
			return

		if action == "update":
			endpoint_id = int(self.get_body_argument("id", 0))
			success, message = ApiEndpointRepository.save_endpoint(payload, endpoint_id=endpoint_id)
			self._write_json({"code": 0 if success else 1, "msg": message})
			return

		self._write_json({"code": 1, "msg": "未知操作"})


class AdminInterfaceTestHandler(AdminBaseHandler):
	def _write_json(self, data):
		self.set_header("Content-Type", "application/json")
		self.write(json.dumps(data, ensure_ascii=False))

	@tornado.web.authenticated
	def post(self):
		endpoint_id = int(self.get_body_argument("id", 0))
		params_json = (self.get_body_argument("params_json", "") or "").strip()
		body_json = (self.get_body_argument("body_json", "") or "").strip()

		config = ApiEndpointRepository.get_endpoint_by_id(endpoint_id)
		if not config:
			self._write_json({"code": 1, "msg": "接口不存在"})
			return

		try:
			params = json.loads(params_json) if params_json else {}
		except json.JSONDecodeError:
			self._write_json({"code": 1, "msg": "测试参数JSON格式错误"})
			return

		try:
			body = json.loads(body_json) if body_json else {}
		except json.JSONDecodeError:
			self._write_json({"code": 1, "msg": "请求体JSON格式错误"})
			return

		try:
			result = ApiEndpointRepository.call_endpoint(config, params=params, body=body)
			self._write_json({"code": 0, "msg": "调用成功", "data": result})
		except Exception as exc:
			self._write_json({"code": 1, "msg": str(exc)})


class AdminInterfaceServiceHandler(AdminBaseHandler):
	def _write_json(self, data):
		self.set_header("Content-Type", "application/json")
		self.write(json.dumps(data, ensure_ascii=False))

	@tornado.web.authenticated
	def get(self):
		code = (self.get_argument("code", "") or "").strip()
		params = {}
		for key in self.request.arguments:
			if key == "code":
				continue
			params[key] = self.get_argument(key)
		try:
			result = ApiEndpointRepository.call_by_code(code, params=params)
			self._write_json({"code": 0, "msg": "ok", "data": result.get("json") if result.get("json") is not None else result})
		except Exception as exc:
			self._write_json({"code": 1, "msg": str(exc)})

	@tornado.web.authenticated
	def post(self):
		code = (self.get_body_argument("code", "") or "").strip()
		params_json = (self.get_body_argument("params_json", "") or "").strip()
		body_json = (self.get_body_argument("body_json", "") or "").strip()

		try:
			params = json.loads(params_json) if params_json else {}
		except json.JSONDecodeError:
			self._write_json({"code": 1, "msg": "params_json 格式错误"})
			return

		try:
			body = json.loads(body_json) if body_json else {}
		except json.JSONDecodeError:
			self._write_json({"code": 1, "msg": "body_json 格式错误"})
			return

		try:
			result = ApiEndpointRepository.call_by_code(code, params=params, body=body)
			self._write_json({"code": 0, "msg": "ok", "data": result.get("json") if result.get("json") is not None else result})
		except Exception as exc:
			self._write_json({"code": 1, "msg": str(exc)})
