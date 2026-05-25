import json

import tornado.web

from app.controllers.admin import AdminBaseHandler
from app.models.function import FunctionRepository


class AdminFunctionListHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		self.render("admin/function/list.html", title="功能管理", username=self.current_user)


class AdminFunctionApiHandler(AdminBaseHandler):
	def _write_json(self, data):
		self.set_header("Content-Type", "application/json")
		self.write(json.dumps(data, ensure_ascii=False))

	@tornado.web.authenticated
	def get(self):
		action = self.get_argument("action", "")

		if action == "parents":
			self._write_json({"code": 0, "msg": "", "data": FunctionRepository.get_parent_options()})
			return

		if action == "children":
			parent_id = int(self.get_argument("parent_id", 0))
			self._write_json({"code": 0, "msg": "", "data": FunctionRepository.get_children_by_parent(parent_id)})
			return

		if action == "tree":
			self._write_json({"code": 0, "msg": "", "data": FunctionRepository.get_function_tree_for_form()})
			return

		if action == "detail":
			function_id = int(self.get_argument("id", 0))
			data = FunctionRepository.get_function_by_id(function_id)
			if not data:
				self._write_json({"code": 1, "msg": "功能不存在"})
				return
			self._write_json({"code": 0, "msg": "", "data": data})
			return

		page = int(self.get_argument("page", 1))
		limit = int(self.get_argument("limit", 20))
		keyword = (self.get_argument("keyword", "") or "").strip()
		parent_id = self.get_argument("parent_id", "")
		parent_value = None if parent_id == "" else int(parent_id)

		result = FunctionRepository.get_function_list(
			page=page,
			page_size=limit,
			keyword=keyword,
			parent_id=parent_value,
		)
		self._write_json({
			"code": 0,
			"msg": "",
			"count": result["total"],
			"data": result["list"],
		})

	@tornado.web.authenticated
	def post(self):
		action = self.get_argument("action", "")
		parent_id = int(self.get_body_argument("parent_id", 0))
		name = (self.get_body_argument("name", "") or "").strip()
		code = (self.get_body_argument("code", "") or "").strip()
		icon = (self.get_body_argument("icon", "") or "").strip()
		url = (self.get_body_argument("url", "") or "").strip()
		function_type = int(self.get_body_argument("type", 1))
		sort = int(self.get_body_argument("sort", 0))
		status = int(self.get_body_argument("status", 1))

		if action == "add":
			success, message = FunctionRepository.create_function(
				parent_id=parent_id,
				name=name,
				code=code,
				icon=icon,
				url=url,
				function_type=function_type,
				sort=sort,
				status=status,
			)
			self._write_json({"code": 0 if success else 1, "msg": message})
			return

		if action == "update":
			function_id = int(self.get_body_argument("id", 0))
			success, message = FunctionRepository.update_function(
				function_id=function_id,
				parent_id=parent_id,
				name=name,
				code=code,
				icon=icon,
				url=url,
				function_type=function_type,
				sort=sort,
				status=status,
			)
			self._write_json({"code": 0 if success else 1, "msg": message})
			return

		if action == "delete":
			function_id = int(self.get_body_argument("id", 0))
			success, message = FunctionRepository.delete_function(function_id)
			self._write_json({"code": 0 if success else 1, "msg": message})
			return

		self._write_json({"code": 1, "msg": "未知操作"})
