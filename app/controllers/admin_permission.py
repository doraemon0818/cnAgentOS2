import json

import tornado.web

from app.controllers.admin import AdminBaseHandler
from app.models.permission import PermissionRepository


class AdminPermissionListHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		self.render("admin/permission/list.html", title="权限管理", username=self.current_user)


class AdminPermissionApiHandler(AdminBaseHandler):
	def _write_json(self, data):
		self.set_header("Content-Type", "application/json")
		self.write(json.dumps(data, ensure_ascii=False))

	@tornado.web.authenticated
	def get(self):
		action = self.get_argument("action", "")

		if action == "detail":
			role_id = int(self.get_argument("role_id", 0))
			function_id = int(self.get_argument("function_id", 0))
			data = PermissionRepository.get_permission_detail(role_id, function_id)
			if not data:
				self._write_json({"code": 1, "msg": "权限映射不存在"})
				return
			self._write_json({"code": 0, "msg": "", "data": data})
			return

		page = int(self.get_argument("page", 1))
		limit = int(self.get_argument("limit", 20))
		keyword = (self.get_argument("keyword", "") or "").strip()
		role_id = self.get_argument("role_id", "")
		parent_id = self.get_argument("parent_id", "")
		result = PermissionRepository.get_permission_list(
			page=page,
			page_size=limit,
			role_id=int(role_id) if role_id else None,
			parent_id=int(parent_id) if parent_id else None,
			keyword=keyword,
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

		if action == "add":
			role_id = int(self.get_body_argument("role_id", 0))
			function_id = int(self.get_body_argument("function_id", 0))
			success, message = PermissionRepository.create_permission(role_id, function_id)
			self._write_json({"code": 0 if success else 1, "msg": message})
			return

		if action == "update":
			old_role_id = int(self.get_body_argument("old_role_id", 0))
			old_function_id = int(self.get_body_argument("old_function_id", 0))
			role_id = int(self.get_body_argument("role_id", 0))
			function_id = int(self.get_body_argument("function_id", 0))
			success, message = PermissionRepository.update_permission(
				old_role_id,
				old_function_id,
				role_id,
				function_id,
			)
			self._write_json({"code": 0 if success else 1, "msg": message})
			return

		if action == "delete":
			role_id = int(self.get_body_argument("role_id", 0))
			function_id = int(self.get_body_argument("function_id", 0))
			success, message = PermissionRepository.delete_permission(role_id, function_id)
			self._write_json({"code": 0 if success else 1, "msg": message})
			return

		self._write_json({"code": 1, "msg": "未知操作"})
