import sqlite3

from app.models.db import get_connection


class PermissionRepository:
	@staticmethod
	def get_permission_list(page=1, page_size=20, role_id=None, parent_id=None, keyword=""):
		offset = (page - 1) * page_size
		conditions = []
		params = []

		if role_id:
			conditions.append("rf.role_id = ?")
			params.append(int(role_id))

		if parent_id:
			conditions.append("(case when f.parent_id = 0 then f.id else f.parent_id end) = ?")
			params.append(int(parent_id))

		if keyword:
			conditions.append("(r.name like ? or r.code like ? or f.name like ? or f.code like ?)")
			like_value = f"%{keyword}%"
			params.extend([like_value, like_value, like_value, like_value])

		where_sql = f"where {' and '.join(conditions)}" if conditions else ""
		sql = f"""
			select rf.role_id,rf.function_id,r.name as role_name,r.code as role_code,r.is_system,
				   f.name as function_name,f.code as function_code,f.url,f.type,f.status as function_status,
				   case when f.parent_id = 0 then f.id else f.parent_id end as parent_id,
				   case when f.parent_id = 0 then f.name else p.name end as parent_name
			from role_functions rf
			join roles r on rf.role_id = r.id
			join functions f on rf.function_id = f.id
			left join functions p on f.parent_id = p.id
			{where_sql}
			order by r.sort asc,r.id asc,parent_id asc,f.sort asc,f.id asc
			limit ? offset ?
		"""
		count_sql = f"""
			select count(*) as total
			from role_functions rf
			join roles r on rf.role_id = r.id
			join functions f on rf.function_id = f.id
			left join functions p on f.parent_id = p.id
			{where_sql}
		"""

		with get_connection() as conn:
			rows = conn.execute(sql, tuple(params + [page_size, offset])).fetchall()
			total = conn.execute(count_sql, tuple(params)).fetchone()["total"]

		return {"list": [dict(row) for row in rows], "total": total}

	@staticmethod
	def get_permission_detail(role_id, function_id):
		with get_connection() as conn:
			row = conn.execute(
				"""
				select rf.role_id,rf.function_id,r.name as role_name,r.code as role_code,r.is_system,
					   f.name as function_name,f.code as function_code,
					   case when f.parent_id = 0 then f.id else f.parent_id end as parent_id
				from role_functions rf
				join roles r on rf.role_id = r.id
				join functions f on rf.function_id = f.id
				where rf.role_id=? and rf.function_id=?
				""",
				(role_id, function_id),
			).fetchone()
		return dict(row) if row else None

	@staticmethod
	def create_permission(role_id, function_id):
		if not role_id or not function_id:
			return False, "角色和功能不能为空"

		role_id = int(role_id)
		function_id = int(function_id)

		with get_connection() as conn:
			role_row = conn.execute(
				"select id,is_system from roles where id=?",
				(role_id,),
			).fetchone()
			if not role_row:
				return False, "角色不存在"
			if role_row["is_system"] == 1:
				return False, "超级管理员权限不允许单独维护"

			function_row = conn.execute("select id from functions where id=?", (function_id,)).fetchone()
			if not function_row:
				return False, "功能不存在"

			exists = conn.execute(
				"select 1 from role_functions where role_id=? and function_id=?",
				(role_id, function_id),
			).fetchone()
			if exists:
				return False, "权限映射已存在"

			try:
				conn.execute(
					"insert into role_functions(role_id,function_id) values(?,?)",
					(role_id, function_id),
				)
				return True, "新增成功"
			except sqlite3.IntegrityError:
				return False, "新增失败，权限映射已存在"

	@staticmethod
	def update_permission(old_role_id, old_function_id, role_id, function_id):
		if not old_role_id or not old_function_id:
			return False, "原权限信息不能为空"
		if not role_id or not function_id:
			return False, "角色和功能不能为空"

		old_role_id = int(old_role_id)
		old_function_id = int(old_function_id)
		role_id = int(role_id)
		function_id = int(function_id)

		with get_connection() as conn:
			old_role_row = conn.execute(
				"select is_system from roles where id=?",
				(old_role_id,),
			).fetchone()
			if old_role_row and old_role_row["is_system"] == 1:
				return False, "超级管理员权限不允许修改"

			new_role_row = conn.execute(
				"select is_system from roles where id=?",
				(role_id,),
			).fetchone()
			if not new_role_row:
				return False, "角色不存在"
			if new_role_row["is_system"] == 1:
				return False, "超级管理员权限不允许单独维护"

			exists = conn.execute(
				"select 1 from role_functions where role_id=? and function_id=?",
				(role_id, function_id),
			).fetchone()
			if exists and not (old_role_id == role_id and old_function_id == function_id):
				return False, "目标权限映射已存在"

			conn.execute(
				"delete from role_functions where role_id=? and function_id=?",
				(old_role_id, old_function_id),
			)
			conn.execute(
				"insert into role_functions(role_id,function_id) values(?,?)",
				(role_id, function_id),
			)
			return True, "修改成功"

	@staticmethod
	def delete_permission(role_id, function_id):
		if not role_id or not function_id:
			return False, "权限信息不能为空"

		role_id = int(role_id)
		function_id = int(function_id)

		with get_connection() as conn:
			role_row = conn.execute(
				"select is_system from roles where id=?",
				(role_id,),
			).fetchone()
			if role_row and role_row["is_system"] == 1:
				return False, "超级管理员权限不允许删除"

			conn.execute(
				"delete from role_functions where role_id=? and function_id=?",
				(role_id, function_id),
			)
			return True, "删除成功"
