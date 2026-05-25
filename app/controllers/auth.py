# 认证相关 controller(登录/注册/退出)
#
# 通过Handler来展示mvc中controller层如何接收表单，校验输入，调用model层，再渲染view层 或 跳转
# 登录态 用secure cookie保存username

import os
import secrets

import tornado.web

from app.controllers.base import BaseHandler
from app.models.user import UserRepository


def _save_avatar_file(handler, file_meta):
	filename = (file_meta.get("filename") or "").strip()
	body = file_meta.get("body") or b""
	content_type = (file_meta.get("content_type") or "").lower()
	if not filename or not body:
		return False, "头像文件为空", ""
	_, ext = os.path.splitext(filename)
	ext = (ext or "").lower()
	if ext not in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
		return False, "头像仅支持 png/jpg/jpeg/webp/gif 格式", ""
	if content_type and not content_type.startswith("image/"):
		return False, "上传的头像文件类型无效", ""

	relative_dir = os.path.join("uploads", "avatars")
	abs_dir = os.path.join(handler.settings["static_path"], relative_dir)
	os.makedirs(abs_dir, exist_ok=True)
	storage_name = secrets.token_hex(12) + ext
	relative_path = os.path.join(relative_dir, storage_name)
	abs_path = os.path.join(handler.settings["static_path"], relative_path)
	with open(abs_path, "wb") as fp:
		fp.write(body)
	return True, "", relative_path

class LoginHandler(BaseHandler):
# /auth/login
# get:渲染登录页
# post:校验用户名和密码，通过后写入secure cookie 并跳转到目标页
	def get(self):
		# self.write(f"""<h3>登录</h3>"
		# 	<form method="post",action="/auth/login">
		# 	<input name="username">
		# 	<input name="password">
		# 	{self.xsrf_form_html()}
		# 	<button type="submit">登录admin</button>
		# 	</form>
		# 	""")
		self.render("login.html", title="登录", error=None, success=None, mode="login")

	def post(self):
		username = (self.get_body_argument("username","") or "").strip()
		password = self.get_body_argument("password","")
		if not username or not password:
			self.set_status(400)
			# return self.write(f"""<h3>登录</h3>"
			# 用户名或密码不能为空或输入了无效数据
			# <form method="post",action="/auth/login">
			# <input name="username">
			# <input name="password">
			# {self.xsrf_form_html()}
			# <button type="submit">登录admin</button>
			# </form>
			# """)
			self.render("login.html", title="登录", error="用户名或密码不能为空或输入了无效数据", success=None, mode="login")
			return

		if not UserRepository.verify_user(username,password):
			self.set_status(401)
			# return self.write(f"""<h3>登录</h3>"
			# 用户名或密码错误
			# <form method="post",action="/auth/login">
			# <input name="username">
			# <input name="password">
			# {self.xsrf_form_html()}
			# <button type="submit">登录admin</button>
			# </form>
			# """)
			self.render("login.html", title="登录", error="用户名或密码错误", success=None, mode="login")
			return

		if not UserRepository.can_access_front(username):
			self.set_status(403)
			self.render("login.html", title="登录", error="当前账号不属于前端普通用户角色，请使用普通用户账号登录", success=None, mode="login")
			return

		self.set_secure_cookie("username",username)
		# self.write(f"登录成功，欢迎{username}")
		self.redirect("/")


class RegisterHandler(BaseHandler):
	def get(self):
		self.render("login.html", title="注册", error=None, success=None, mode="register")

	def post(self):
		username = (self.get_body_argument("username", "") or "").strip()
		password = self.get_body_argument("password", "")
		confirm_password = self.get_body_argument("confirm_password", "")
		email = (self.get_body_argument("email", "") or "").strip()
		phone = (self.get_body_argument("phone", "") or "").strip()
		avatar_path = ""

		if not username or not password:
			self.set_status(400)
			self.render("login.html", title="注册", error="用户名和密码不能为空", success=None, mode="register")
			return
		if password != confirm_password:
			self.set_status(400)
			self.render("login.html", title="注册", error="两次输入的密码不一致", success=None, mode="register")
			return
		valid, message = UserRepository.validate_create_user(username, password, UserRepository.DEFAULT_FRONT_ROLE_CODE)
		if not valid:
			self.set_status(400)
			self.render("login.html", title="注册", error=message, success=None, mode="register")
			return

		avatar_files = self.request.files.get("avatar") or []
		if avatar_files:
			ok, avatar_error, avatar_path = _save_avatar_file(self, avatar_files[0])
			if not ok:
				self.set_status(400)
				self.render("login.html", title="注册", error=avatar_error, success=None, mode="register")
				return

		if not UserRepository.register_front_user(username, password, email=email, phone=phone, avatar_path=avatar_path):
			self.set_status(400)
			self.render(
				"login.html",
				title="注册",
				error="注册失败，请稍后重试",
				success=None,
				mode="register",
			)
			return

		self.set_secure_cookie("username", username)
		self.redirect("/")

class LogoutHandler(BaseHandler):
	def post(self):
		self.clear_cookie("username")
		self.redirect("/auth/login")
