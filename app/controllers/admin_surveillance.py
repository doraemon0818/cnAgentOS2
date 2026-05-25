import json

import tornado.web

from app.controllers.admin import AdminBaseHandler
from app.models.surveillance import (
	SurveillanceCollector,
	SurveillanceRecordRepository,
	SurveillanceSourceRepository,
)
from app.models.warehouse_deep import WarehouseDeepCollector, WarehouseDetailRepository


class AdminSurveillanceSourceListHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		self.render("admin/surveillance/source_list.html", title="采集源管理", username=self.current_user)


class AdminSurveillanceCollectHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		self.render("admin/surveillance/collect.html", title="瞭望采集", username=self.current_user)


class AdminWarehouseListHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		self.render("admin/warehouse/list.html", title="数据仓库", username=self.current_user)


class AdminSurveillanceSourceApiHandler(AdminBaseHandler):
	def _write_json(self, data):
		self.set_header("Content-Type", "application/json")
		self.write(json.dumps(data, ensure_ascii=False))

	@tornado.web.authenticated
	def get(self):
		action = self.get_argument("action", "")
		if action == "options":
			self._write_json({"code": 0, "msg": "", "data": SurveillanceSourceRepository.get_source_options()})
			return

		if action == "detail":
			source_id = int(self.get_argument("id", 0))
			data = SurveillanceSourceRepository.get_source_by_id(source_id)
			if not data:
				self._write_json({"code": 1, "msg": "采集源不存在"})
				return
			self._write_json({"code": 0, "msg": "", "data": data})
			return

		page = int(self.get_argument("page", 1))
		limit = int(self.get_argument("limit", 20))
		keyword = (self.get_argument("keyword", "") or "").strip()
		result = SurveillanceSourceRepository.get_source_list(page=page, page_size=limit, keyword=keyword)
		self._write_json({"code": 0, "msg": "", "count": result["total"], "data": result["list"]})

	@tornado.web.authenticated
	def post(self):
		action = self.get_argument("action", "")
		if action == "delete":
			source_id = int(self.get_body_argument("id", 0))
			success, message = SurveillanceSourceRepository.delete_source(source_id)
			self._write_json({"code": 0 if success else 1, "msg": message})
			return

		payload = {
			"name": self.get_body_argument("name", ""),
			"code": self.get_body_argument("code", ""),
			"description": self.get_body_argument("description", ""),
			"entry_url_template": self.get_body_argument("entry_url_template", ""),
			"page_url_template": self.get_body_argument("page_url_template", ""),
			"method": self.get_body_argument("method", "GET"),
			"page_step": self.get_body_argument("page_step", "10"),
			"default_page_count": self.get_body_argument("default_page_count", "1"),
			"default_limit": self.get_body_argument("default_limit", "20"),
			"status": self.get_body_argument("status", "1"),
			"headers": {},
			"params": [
				{"name": "keyword", "label": "关键字", "required": 1, "default": "", "placeholder": "请输入瞭望关键字"},
				{"name": "pn", "label": "分页步进", "required": 0, "default": "0", "placeholder": "默认由系统自动计算"},
			],
			"selectors": {
				"list_selector": self.get_body_argument("list_selector", ""),
				"title_selector": self.get_body_argument("title_selector", ""),
				"summary_selector": self.get_body_argument("summary_selector", ""),
				"meta_selector": self.get_body_argument("meta_selector", ""),
			},
		}

		headers_text = (self.get_body_argument("headers_json", "") or "").strip()
		if headers_text:
			try:
				payload["headers"] = json.loads(headers_text)
			except json.JSONDecodeError:
				self._write_json({"code": 1, "msg": "请求头JSON格式错误"})
				return

		if action == "add":
			success, message = SurveillanceSourceRepository.save_source(payload)
			self._write_json({"code": 0 if success else 1, "msg": message})
			return

		if action == "update":
			source_id = int(self.get_body_argument("id", 0))
			success, message = SurveillanceSourceRepository.save_source(payload, source_id=source_id)
			self._write_json({"code": 0 if success else 1, "msg": message})
			return

		self._write_json({"code": 1, "msg": "未知操作"})


class AdminSurveillanceCollectApiHandler(AdminBaseHandler):
	def _write_json(self, data):
		self.set_header("Content-Type", "application/json")
		self.write(json.dumps(data, ensure_ascii=False))

	@tornado.web.authenticated
	def get(self):
		self._write_json({"code": 0, "msg": "", "data": SurveillanceSourceRepository.get_active_sources()})

	@tornado.web.authenticated
	def post(self):
		source_id = int(self.get_body_argument("source_id", 0))
		keyword = (self.get_body_argument("keyword", "") or "").strip()
		page_count = int(self.get_body_argument("page_count", 1))
		limit = int(self.get_body_argument("limit", 20))

		try:
			success, message, data = SurveillanceCollector.collect(
				source_id=source_id,
				keyword=keyword,
				page_count=page_count,
				limit=limit,
			)
		except Exception as exc:
			self._write_json({"code": 1, "msg": str(exc)})
			return

		self._write_json({"code": 0 if success else 1, "msg": message, "data": data})


class AdminWarehouseApiHandler(AdminBaseHandler):
	def _write_json(self, data):
		self.set_header("Content-Type", "application/json")
		self.write(json.dumps(data, ensure_ascii=False))

	@tornado.web.authenticated
	def get(self):
		action = self.get_argument("action", "")
		if action == "source_options":
			self._write_json({"code": 0, "msg": "", "data": SurveillanceSourceRepository.get_source_options()})
			return

		if action == "summary":
			self._write_json({"code": 0, "msg": "", "data": WarehouseDetailRepository.get_summary()})
			return

		if action == "detail":
			record_id = int(self.get_argument("id", 0))
			record = SurveillanceRecordRepository.get_record_by_id(record_id)
			if not record:
				self._write_json({"code": 1, "msg": "仓库记录不存在"})
				return
			detail = WarehouseDetailRepository.get_latest_detail(record_id)
			self._write_json({"code": 0, "msg": "", "data": {"record": record, "detail": detail}})
			return

		page = int(self.get_argument("page", 1))
		limit = int(self.get_argument("limit", 20))
		keyword = (self.get_argument("keyword", "") or "").strip()
		source_id = self.get_argument("source_id", "")
		source_value = None if source_id == "" else int(source_id)
		result = SurveillanceRecordRepository.get_record_list(
			page=page,
			page_size=limit,
			keyword=keyword,
			source_id=source_value,
		)
		self._write_json({"code": 0, "msg": "", "count": result["total"], "data": result["list"]})

	@tornado.web.authenticated
	def post(self):
		action = self.get_argument("action", "")
		if action == "delete":
			record_id = int(self.get_body_argument("id", 0))
			success, message = SurveillanceRecordRepository.delete_record(record_id)
			self._write_json({"code": 0 if success else 1, "msg": message})
			return

		if action == "batch_delete":
			ids_str = self.get_body_argument("ids", "")
			record_ids = [int(item) for item in ids_str.split(",") if item.isdigit()]
			count = SurveillanceRecordRepository.batch_delete(record_ids)
			self._write_json({"code": 0, "msg": f"成功删除{count}条数据"})
			return

		self._write_json({"code": 1, "msg": "未知操作"})


class AdminWarehouseDeepCollectStreamHandler(AdminBaseHandler):
	@tornado.web.authenticated
	async def get(self):
		ids_str = (self.get_argument("ids", "") or "").strip()
		record_ids = [int(item) for item in ids_str.split(",") if item.strip().isdigit()]
		if not record_ids:
			self.set_status(400)
			self.write("data: " + json.dumps({"type": "error", "message": "请选择要深度采集的数据"}, ensure_ascii=False) + "\n\n")
			return

		self.set_header("Content-Type", "text/event-stream; charset=utf-8")
		self.set_header("Cache-Control", "no-cache")
		self.set_header("Connection", "keep-alive")
		await self.flush()

		try:
			async for item in WarehouseDeepCollector.stream_collect(record_ids):
				self.write("data: " + json.dumps(item, ensure_ascii=False) + "\n\n")
				await self.flush()
		except Exception as exc:
			self.write("data: " + json.dumps({"type": "error", "message": str(exc)}, ensure_ascii=False) + "\n\n")
			await self.flush()
