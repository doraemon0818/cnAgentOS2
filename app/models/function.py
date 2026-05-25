import sqlite3

from app.models.db import get_connection


def _rows_to_tree(rows):
	items = []
	for row in rows:
		item = dict(row)
		item["children"] = []
		items.append(item)

	item_map = {item["id"]: item for item in items}
	tree = []

	for item in items:
		parent_id = item["parent_id"]
		if parent_id and parent_id in item_map:
			item_map[parent_id]["children"].append(item)
		else:
			tree.append(item)

	return tree


class FunctionRepository:
	@staticmethod
	def get_menu_tree():
		with get_connection() as conn:
			rows = conn.execute(
				"""
				select id,parent_id,name,code,icon,url,type,sort,status
				from functions
				where status=1
				order by sort asc,id asc
				"""
			).fetchall()
		return _rows_to_tree(rows)

	@staticmethod
	def get_parent_options():
		with get_connection() as conn:
			rows = conn.execute(
				"""
				select id,name,code
				from functions
				where parent_id=0 and status=1
				order by sort asc,id asc
				"""
			).fetchall()
		return [dict(row) for row in rows]

	@staticmethod
	def get_children_by_parent(parent_id):
		with get_connection() as conn:
			rows = conn.execute(
				"""
				select id,parent_id,name,code,url
				from functions
				where parent_id=? and status=1
				order by sort asc,id asc
				""",
				(parent_id,),
			).fetchall()
		return [dict(row) for row in rows]

	@staticmethod
	def get_function_tree_for_form():
		with get_connection() as conn:
			rows = conn.execute(
				"""
				select id,parent_id,name,code,url,type,sort,status
				from functions
				where status=1
				order by sort asc,id asc
				"""
			).fetchall()
		return _rows_to_tree(rows)

	@staticmethod
	def get_function_by_id(function_id):
		with get_connection() as conn:
			row = conn.execute(
				"""
				select f.id,f.parent_id,f.name,f.code,f.icon,f.url,f.type,f.sort,f.status,
					   p.name as parent_name
				from functions f
				left join functions p on f.parent_id = p.id
				where f.id=?
				""",
				(function_id,),
			).fetchone()
		return dict(row) if row else None

	@staticmethod
	def get_function_list(page=1, page_size=20, keyword="", parent_id=None):
		offset = (page - 1) * page_size
		conditions = []
		params = []

		if keyword:
			conditions.append("(f.name like ? or f.code like ? or f.url like ?)")
			like_value = f"%{keyword}%"
			params.extend([like_value, like_value, like_value])

		if parent_id is not None and str(parent_id) != "":
			conditions.append("f.parent_id = ?")
			params.append(int(parent_id))

		where_sql = f"where {' and '.join(conditions)}" if conditions else ""
		sql = f"""
			select f.id,f.parent_id,f.name,f.code,f.icon,f.url,f.type,f.sort,f.status,
				   f.create_at,f.update_at,coalesce(p.name,'-') as parent_name
			from functions f
			left join functions p on f.parent_id = p.id
			{where_sql}
			order by f.parent_id asc,f.sort asc,f.id asc
			limit ? offset ?
		"""
		count_sql = f"select count(*) as total from functions f {where_sql}"

		with get_connection() as conn:
			rows = conn.execute(sql, tuple(params + [page_size, offset])).fetchall()
			total = conn.execute(count_sql, tuple(params)).fetchone()["total"]

		data = []
		for row in rows:
			item = dict(row)
			item["type_text"] = "一级模块" if item["type"] == 1 else "二级功能"
			data.append(item)
		return {"list": data, "total": total}

	@staticmethod
	def create_function(parent_id, name, code, icon="", url="", function_type=1, sort=0, status=1):
		if not name or not code:
			return False, "功能名称和编码不能为空"

		parent_id = int(parent_id or 0)
		function_type = int(function_type or 1)
		sort = int(sort or 0)
		status = int(status or 1)
		url = url if function_type == 2 else ""

		with get_connection() as conn:
			exists = conn.execute("select id from functions where code=?", (code,)).fetchone()
			if exists:
				return False, "功能编码已存在"

			if parent_id:
				parent_row = conn.execute("select id from functions where id=?", (parent_id,)).fetchone()
				if not parent_row:
					return False, "上级模块不存在"

			try:
				conn.execute(
					"""
					insert into functions(parent_id,name,code,icon,url,type,sort,status,create_at,update_at)
					values(?,?,?,?,?,?,?,?,datetime('now'),datetime('now'))
					""",
					(parent_id, name, code, icon, url, function_type, sort, status),
				)
				return True, "新增成功"
			except sqlite3.IntegrityError:
				return False, "新增失败，功能编码已存在"

	@staticmethod
	def update_function(function_id, parent_id, name, code, icon="", url="", function_type=1, sort=0, status=1):
		if not function_id:
			return False, "功能ID不能为空"
		if not name or not code:
			return False, "功能名称和编码不能为空"

		function_id = int(function_id)
		parent_id = int(parent_id or 0)
		function_type = int(function_type or 1)
		sort = int(sort or 0)
		status = int(status or 1)
		url = url if function_type == 2 else ""

		if function_id == parent_id:
			return False, "上级模块不能选择自身"

		with get_connection() as conn:
			exists = conn.execute("select id from functions where id=?", (function_id,)).fetchone()
			if not exists:
				return False, "功能不存在"

			duplicate = conn.execute(
				"select id from functions where code=? and id<>?",
				(code, function_id),
			).fetchone()
			if duplicate:
				return False, "功能编码已存在"

			if parent_id:
				parent_row = conn.execute("select id,type from functions where id=?", (parent_id,)).fetchone()
				if not parent_row:
					return False, "上级模块不存在"
				if parent_row["type"] != 1:
					return False, "只能挂载到一级模块下"

			try:
				conn.execute(
					"""
					update functions
					set parent_id=?,name=?,code=?,icon=?,url=?,type=?,sort=?,status=?,update_at=datetime('now')
					where id=?
					""",
					(parent_id, name, code, icon, url, function_type, sort, status, function_id),
				)
				return True, "修改成功"
			except sqlite3.IntegrityError:
				return False, "修改失败，功能编码已存在"

	@staticmethod
	def delete_function(function_id):
		if not function_id:
			return False, "功能ID不能为空"

		function_id = int(function_id)
		with get_connection() as conn:
			child_count = conn.execute(
				"select count(*) as total from functions where parent_id=?",
				(function_id,),
			).fetchone()["total"]
			if child_count > 0:
				return False, "请先删除下级功能后再删除当前模块"

			conn.execute("delete from role_functions where function_id=?", (function_id,))
			conn.execute("delete from functions where id=?", (function_id,))
			return True, "删除成功"
