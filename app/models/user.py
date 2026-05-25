import hashlib
import secrets
import sqlite3
 
from app.models.db import get_connection

def _hash_password(password:str,salt:bytes) -> str:
	dk = hashlib.pbkdf2_hmac('sha256',password.encode('utf-8'),salt,100_000)
	return dk.hex()

class UserRepository:
	SYSTEM_USERNAME = "admin"
	FRONT_ROLE_CODES = {"normal_user", "member_user"}
	DEFAULT_FRONT_ROLE_CODE = "normal_user"

	@staticmethod
	def build_avatar_url(avatar_path:str='') -> str:
		value = (avatar_path or "").strip().replace("\\", "/")
		if not value:
			return ""
		if value.startswith("/static/"):
			return value
		return "/static/" + value

	@staticmethod
	def _is_system_username(username:str) -> bool:
		return (username or "").strip().lower() == UserRepository.SYSTEM_USERNAME

	@staticmethod
	def _get_active_role(conn, role_name:str):
		return conn.execute(
			"select id,name,code,is_system,status from roles where name=? and status=1",
			(role_name,),
		).fetchone()

	@staticmethod
	def _get_active_role_by_code(conn, role_code:str):
		return conn.execute(
			"select id,name,code,is_system,status from roles where code=? and status=1",
			((role_code or "").strip(),),
		).fetchone()

	@staticmethod
	def _get_default_role_name(conn):
		role_row = conn.execute(
			"select name from roles where code=? limit 1",
			(UserRepository.DEFAULT_FRONT_ROLE_CODE,),
		).fetchone()
		if role_row:
			return role_row["name"]
		role_row = conn.execute("select name from roles where code='super_admin' limit 1").fetchone()
		if role_row:
			return role_row["name"]
		return "普通用户"

	@staticmethod
	def _normalize_role(conn, role_value:str=''):
		role_value = (role_value or "").strip()
		if not role_value:
			role_value = UserRepository._get_default_role_name(conn)
		role_row = UserRepository._get_active_role(conn, role_value)
		if role_row:
			return role_row
		return UserRepository._get_active_role_by_code(conn, role_value)

	@staticmethod
	def _validate_username(username:str) -> bool:
		username = (username or "").strip()
		if len(username) < 2 or len(username) > 30:
			return False
		return username.replace("_", "").isalnum()

	@staticmethod
	def _validate_password(password:str) -> bool:
		return isinstance(password, str) and len(password) >= 6

	@staticmethod
	def validate_create_user(username:str, password:str, role:str=''):
		username = (username or "").strip()
		if not UserRepository._validate_username(username):
			return False, "用户名需为 2-30 位字母、数字或下划线"
		if not UserRepository._validate_password(password):
			return False, "密码长度至少 6 位"
		if UserRepository.get_user_by_username(username):
			return False, "用户名已存在"
		with get_connection() as conn:
			role_row = UserRepository._normalize_role(conn, role)
			if not role_row:
				return False, "角色不存在或未启用"
		return True, ""

	@staticmethod
	def create_user(username:str,password:str,email:str='',phone:str='',role:str='user', avatar_path:str='') -> bool:
		username = (username or "").strip()
		valid, _ = UserRepository.validate_create_user(username, password, role)
		if not valid:
			return False
		salt = secrets.token_bytes(16)
		password_hash = _hash_password(password,salt)

		try:
			with get_connection() as conn:
				role_row = UserRepository._normalize_role(conn, role)
				if not role_row:
					return False

				conn.execute(
					"insert into users(username,password_hash,salt,email,phone,role,avatar_path) values(?,?,?,?,?,?,?)",
					(username,password_hash,salt.hex(),email,phone,role_row["name"],(avatar_path or "").strip())
				)
			return True
		except sqlite3.IntegrityError:
			return False

	@staticmethod
	def register_front_user(username:str,password:str,email:str='',phone:str='', avatar_path:str='') -> bool:
		return UserRepository.create_user(
			username=username,
			password=password,
			email=email,
			phone=phone,
			avatar_path=avatar_path,
			role=UserRepository.DEFAULT_FRONT_ROLE_CODE,
		)

	@staticmethod
	def get_user_by_username(username:str):
		with  get_connection() as conn:
			row = conn.execute(
				"""
				select u.id,u.username,u.password_hash,u.salt,u.email,u.phone,u.role,u.avatar_path,u.status,u.create_at,u.update_at,
					   r.code as role_code,
					   case when username=? then 1 else 0 end as is_system
				from users u
				left join roles r on r.name = u.role
				where u.username=?
				""",
				(UserRepository.SYSTEM_USERNAME, username),
			).fetchone()
			return row

	@staticmethod
	def verify_user(username:str,password:str) -> bool:
		row = UserRepository.get_user_by_username(username)
		if not row:
			return False
		if int(row["status"] or 0) != 1:
			return False

		salt = bytes.fromhex(row["salt"])
		return _hash_password(password,salt) == row["password_hash"]

	@staticmethod
	def get_user_role_info(username:str):
		row = UserRepository.get_user_by_username(username)
		if not row:
			return None
		return {
			"role_name": row["role"],
			"role_code": row["role_code"] or "",
			"status": row["status"],
			"is_system": row["is_system"],
		}

	@staticmethod
	def can_access_front(username:str) -> bool:
		info = UserRepository.get_user_role_info(username)
		if not info or int(info["status"] or 0) != 1:
			return False
		return (info["role_code"] or "") in UserRepository.FRONT_ROLE_CODES

	@staticmethod
	def can_access_admin(username:str) -> bool:
		info = UserRepository.get_user_role_info(username)
		if not info or int(info["status"] or 0) != 1:
			return False
		return (info["role_code"] or "") not in UserRepository.FRONT_ROLE_CODES

	@staticmethod
	def get_user_by_id(user_id:int):
		with get_connection() as conn:
			row = conn.execute(
				"""
				select u.id,u.username,u.email,u.phone,u.role,u.avatar_path,u.status,u.create_at,u.update_at,
					   r.code as role_code,
					   case when u.username=? then 1 else 0 end as is_system
				from users u
				left join roles r on r.name = u.role
				where u.id=?
				""",
				(UserRepository.SYSTEM_USERNAME, user_id),
			).fetchone()
			return row

	@staticmethod
	def get_user_list(page:int=1,page_size:int=20,keyword:str=''):
		offset = (page - 1) * page_size
		
		if keyword:
			sql = """
				select u.id,u.username,u.email,u.phone,u.role,u.avatar_path,u.status,u.create_at,u.update_at,
					   r.code as role_code,
					   case when u.username=? then 1 else 0 end as is_system
				from users u
				left join roles r on r.name = u.role
				where u.username like ? or u.email like ? or u.phone like ? or u.role like ?
				order by u.id desc
				limit ? offset ?
			"""
			count_sql = "select count(*) as total from users where username like ? or email like ? or phone like ? or role like ?"
			params = (
				UserRepository.SYSTEM_USERNAME,
				f'%{keyword}%',
				f'%{keyword}%',
				f'%{keyword}%',
				f'%{keyword}%',
				page_size,
				offset,
			)
			count_params = (f'%{keyword}%', f'%{keyword}%', f'%{keyword}%', f'%{keyword}%')
		else:
			sql = """
				select u.id,u.username,u.email,u.phone,u.role,u.avatar_path,u.status,u.create_at,u.update_at,
					   r.code as role_code,
					   case when u.username=? then 1 else 0 end as is_system
				from users u
				left join roles r on r.name = u.role
				order by u.id desc
				limit ? offset ?
			"""
			count_sql = "select count(*) as total from users"
			params = (UserRepository.SYSTEM_USERNAME, page_size, offset)
			count_params = ()

		with get_connection() as conn:
			rows = conn.execute(sql, params).fetchall()
			total = conn.execute(count_sql, count_params).fetchone()["total"]
			
			users = []
			for row in rows:
				users.append({
					"id": row["id"],
					"username": row["username"],
					"email": row["email"],
					"phone": row["phone"],
					"role": row["role"],
					"avatar_url": UserRepository.build_avatar_url(row["avatar_path"]),
					"role_code": row["role_code"] or "",
					"is_system": row["is_system"],
					"status": row["status"],
					"create_at": row["create_at"],
					"update_at": row["update_at"]
				})
			
			return {"list": users, "total": total, "page": page, "page_size": page_size}

	@staticmethod
	def update_user(user_id:int, email:str='', phone:str='', role:str='', status:int=-1) -> bool:
		fields = []
		params = []

		try:
			with get_connection() as conn:
				user_row = conn.execute(
					"select id,username from users where id=?",
					(user_id,),
				).fetchone()
				if not user_row:
					return False
				if UserRepository._is_system_username(user_row["username"]):
					return False

				if email:
					fields.append("email=?")
					params.append(email)
				if phone:
					fields.append("phone=?")
					params.append(phone)
				if role:
					role_row = UserRepository._get_active_role(conn, role)
					if not role_row:
						return False
					fields.append("role=?")
					params.append(role_row["name"])
				if status >= 0:
					fields.append("status=?")
					params.append(status)

				if not fields:
					return False

				fields.append("update_at=datetime('now')")
				params.append(user_id)

				sql = f"update users set {','.join(fields)} where id=?"
				conn.execute(sql, params)
			return True
		except Exception:
			return False

	@staticmethod
	def update_password(user_id:int, new_password:str) -> bool:
		if not new_password:
			return False

		salt = secrets.token_bytes(16)
		password_hash = _hash_password(new_password, salt)
		
		try:
			with get_connection() as conn:
				user_row = conn.execute("select id from users where id=?", (user_id,)).fetchone()
				if not user_row:
					return False
				conn.execute(
					"update users set password_hash=?, salt=?, update_at=datetime('now') where id=?",
					(password_hash, salt.hex(), user_id)
				)
			return True
		except Exception:
			return False

	@staticmethod
	def delete_user(user_id:int) -> bool:
		try:
			with get_connection() as conn:
				user_row = conn.execute(
					"select username from users where id=?",
					(user_id,),
				).fetchone()
				if not user_row:
					return False
				if UserRepository._is_system_username(user_row["username"]):
					return False
				conn.execute("delete from users where id=?", (user_id,))
			return True
		except Exception:
			return False

	@staticmethod
	def batch_delete_user(user_ids:list):
		try:
			with get_connection() as conn:
				rows = conn.execute(
					"select id,username from users where id in ({})".format(','.join(['?']*len(user_ids))),
					user_ids
				).fetchall()
				deletable_ids = [row["id"] for row in rows if not UserRepository._is_system_username(row["username"])]
				skipped_system = len(rows) - len(deletable_ids)
				if not deletable_ids:
					return {"deleted": 0, "skipped_system": skipped_system}

				cursor = conn.execute(
					"delete from users where id in ({})".format(','.join(['?']*len(deletable_ids))),
					deletable_ids
				)
				conn.commit()
				return {"deleted": cursor.rowcount, "skipped_system": skipped_system}
		except Exception:
			return {"deleted": 0, "skipped_system": 0}
