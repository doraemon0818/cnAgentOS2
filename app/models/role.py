import sqlite3

from app.models.db import get_connection


class RoleRepository:
	@staticmethod
	def get_role_options(active_only=True):
		sql = "select id,name,code,is_system from roles"
		params = []
		if active_only:
			sql += " where status=1"
		sql += " order by sort asc,id asc"

		with get_connection() as conn:
			rows = conn.execute(sql, tuple(params)).fetchall()
		return [dict(row) for row in rows]

	@staticmethod
	def get_role_function_ids(role_id):
		with get_connection() as conn:
			rows = conn.execute(
				"select function_id from role_functions where role_id=? order by function_id asc",
				(role_id,),
			).fetchall()
		return [row["function_id"] for row in rows]

	@staticmethod
	def get_role_detail(role_id):
		with get_connection() as conn:
			row = conn.execute(
				"""
				select id,name,code,description,sort,status,is_system,create_at,update_at
				from roles
				where id=?
				""",
				(role_id,),
			).fetchone()
		if not row:
			return None

		data = dict(row)
		data["function_ids"] = RoleRepository.get_role_function_ids(role_id)
		return data

	@staticmethod
	def get_role_list(page=1, page_size=20, keyword=""):
		offset = (page - 1) * page_size
		params = []
		where_sql = ""
		if keyword:
			where_sql = "where r.name like ? or r.code like ? or r.description like ?"
			like_value = f"%{keyword}%"
			params.extend([like_value, like_value, like_value])

		sql = f"""
			select r.id,r.name,r.code,r.description,r.sort,r.status,r.is_system,r.create_at,r.update_at,
				   count(rf.function_id) as function_count
			from roles r
			left join role_functions rf on r.id = rf.role_id
			{where_sql}
			group by r.id,r.name,r.code,r.description,r.sort,r.status,r.is_system,r.create_at,r.update_at
			order by r.sort asc,r.id asc
			limit ? offset ?
		"""
		count_sql = f"select count(*) as total from roles r {where_sql}"

		with get_connection() as conn:
			rows = conn.execute(sql, tuple(params + [page_size, offset])).fetchall()
			total = conn.execute(count_sql, tuple(params)).fetchone()["total"]

		return {"list": [dict(row) for row in rows], "total": total}

	@staticmethod
	def _check_duplicate(conn, name, code, exclude_id=None):
		name_sql = "select id from roles where name=?"
		code_sql = "select id from roles where code=?"
		params = [name]
		code_params = [code]
		if exclude_id:
			name_sql += " and id<>?"
			code_sql += " and id<>?"
			params.append(exclude_id)
			code_params.append(exclude_id)

		if conn.execute(name_sql, tuple(params)).fetchone():
			return "角色名称已存在"
		if conn.execute(code_sql, tuple(code_params)).fetchone():
			return "角色编码已存在"
		return ""

	@staticmethod
	def _set_role_functions(conn, role_id, function_ids):
		conn.execute("delete from role_functions where role_id=?", (role_id,))
		for function_id in sorted(set(function_ids)):
			conn.execute(
				"insert into role_functions(role_id,function_id) values(?,?)",
				(role_id, int(function_id)),
			)

	@staticmethod
	def create_role(name, code, description="", sort=0, status=1, function_ids=None):
		if not name or not code:
			return False, "角色名称和编码不能为空"

		function_ids = function_ids or []
		sort = int(sort or 0)
		status = int(status or 1)

		with get_connection() as conn:
			message = RoleRepository._check_duplicate(conn, name, code)
			if message:
				return False, message

			try:
				cursor = conn.execute(
					"""
					insert into roles(name,code,description,sort,status,is_system,create_at,update_at)
					values(?,?,?,?,?,0,datetime('now','localtime'),datetime('now','localtime'))
					""",
					(name, code, description, sort, status),
				)
				RoleRepository._set_role_functions(conn, cursor.lastrowid, function_ids)
				return True, "新增成功"
			except sqlite3.IntegrityError:
				return False, "新增失败，角色名称或编码已存在"

	@staticmethod
	def update_role(role_id, name, code, description="", sort=0, status=1, function_ids=None):
		if not role_id:
			return False, "角色ID不能为空"
		if not name or not code:
			return False, "角色名称和编码不能为空"

		role_id = int(role_id)
		function_ids = function_ids or []
		sort = int(sort or 0)
		status = int(status or 1)

		with get_connection() as conn:
			role_row = conn.execute(
				"select id,is_system from roles where id=?",
				(role_id,),
			).fetchone()
			if not role_row:
				return False, "角色不存在"
			if role_row["is_system"] == 1:
				return False, "超级管理员角色不允许修改"

			message = RoleRepository._check_duplicate(conn, name, code, exclude_id=role_id)
			if message:
				return False, message

			try:
				conn.execute(
					"""
					update roles
					set name=?,code=?,description=?,sort=?,status=?,update_at=datetime('now','localtime')
					where id=?
					""",
					(name, code, description, sort, status, role_id),
				)
				RoleRepository._set_role_functions(conn, role_id, function_ids)
				return True, "修改成功"
			except sqlite3.IntegrityError:
				return False, "修改失败，角色名称或编码已存在"

	@staticmethod
	def delete_role(role_id):
		if not role_id:
			return False, "角色ID不能为空"

		role_id = int(role_id)
		with get_connection() as conn:
			role_row = conn.execute(
				"select id,name,is_system from roles where id=?",
				(role_id,),
			).fetchone()
			if not role_row:
				return False, "角色不存在"
			if role_row["is_system"] == 1:
				return False, "超级管理员角色不允许删除"

			user_row = conn.execute(
				"select id from users where role=? limit 1",
				(role_row["name"],),
			).fetchone()
			if user_row:
				return False, "当前角色仍有用户使用，不能删除"

			conn.execute("delete from role_functions where role_id=?", (role_id,))
			conn.execute("delete from roles where id=?", (role_id,))
			return True, "删除成功"
