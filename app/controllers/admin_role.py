import json

import tornado.web

from app.controllers.admin import AdminBaseHandler
from app.models.role import RoleRepository


def _parse_ids(ids_text):
	if not ids_text:
		return []
	return [int(item) for item in ids_text.split(",") if item.strip().isdigit()]


class AdminRoleListHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		self.render("admin/role/list.html", title="角色管理", username=self.current_user)


class AdminRoleApiHandler(AdminBaseHandler):
	def _write_json(self, data):
		self.set_header("Content-Type", "application/json")
		self.write(json.dumps(data, ensure_ascii=False))

	@tornado.web.authenticated
	def get(self):
		action = self.get_argument("action", "")

		if action == "options":
			self._write_json({"code": 0, "msg": "", "data": RoleRepository.get_role_options(active_only=True)})
			return

		if action == "detail":
			role_id = int(self.get_argument("id", 0))
			data = RoleRepository.get_role_detail(role_id)
			if not data:
				self._write_json({"code": 1, "msg": "角色不存在"})
				return
			self._write_json({"code": 0, "msg": "", "data": data})
			return

		page = int(self.get_argument("page", 1))
		limit = int(self.get_argument("limit", 20))
		keyword = (self.get_argument("keyword", "") or "").strip()
		result = RoleRepository.get_role_list(page=page, page_size=limit, keyword=keyword)

		self._write_json({
			"code": 0,
			"msg": "",
			"count": result["total"],
			"data": result["list"],
		})

	@tornado.web.authenticated
	def post(self):
		action = self.get_argument("action", "")
		name = (self.get_body_argument("name", "") or "").strip()
		code = (self.get_body_argument("code", "") or "").strip()
		description = (self.get_body_argument("description", "") or "").strip()
		sort = int(self.get_body_argument("sort", 0))
		status = int(self.get_body_argument("status", 1))
		function_ids = _parse_ids(self.get_body_argument("function_ids", ""))

		if action == "add":
			success, message = RoleRepository.create_role(
				name=name,
				code=code,
				description=description,
				sort=sort,
				status=status,
				function_ids=function_ids,
			)
			self._write_json({"code": 0 if success else 1, "msg": message})
			return

		if action == "update":
			role_id = int(self.get_body_argument("id", 0))
			success, message = RoleRepository.update_role(
				role_id=role_id,
				name=name,
				code=code,
				description=description,
				sort=sort,
				status=status,
				function_ids=function_ids,
			)
			self._write_json({"code": 0 if success else 1, "msg": message})
			return

		if action == "delete":
			role_id = int(self.get_body_argument("id", 0))
			success, message = RoleRepository.delete_role(role_id)
			self._write_json({"code": 0 if success else 1, "msg": message})
			return

		self._write_json({"code": 1, "msg": "未知操作"})
