import json
import tornado.web
from app.controllers.base import BaseHandler
from app.models.function import FunctionRepository
from app.models.user import UserRepository
from app.models.db import get_connection

class AdminLoginHandler(BaseHandler):
    def get(self):
        self.render("login.html", title="管理后台登录", error=None, success=None, mode="admin")

    def post(self):
        username = (self.get_body_argument("username", "") or "").strip()
        password = self.get_body_argument("password", "")
        
        if not username or not password:
            self.set_status(400)
            self.render("login.html", title="管理后台登录", error="用户名或密码不能为空", success=None, mode="admin")
            return

        if not UserRepository.verify_user(username, password):
            self.set_status(401)
            self.render("login.html", title="管理后台登录", error="用户名或密码错误", success=None, mode="admin")
            return

        if not UserRepository.can_access_admin(username):
            self.set_status(403)
            self.render("login.html", title="管理后台登录", error="当前账号没有后台管理权限", success=None, mode="admin")
            return

        self.set_secure_cookie("admin_username", username)
        self.redirect("/admin")

class AdminLogoutHandler(BaseHandler):
    def post(self):
        self.clear_cookie("admin_username")
        self.redirect("/admin/login")

class AdminBaseHandler(BaseHandler):
    def get_current_user(self):
        username = self.get_secure_cookie("admin_username")
        if not username:
            return None
        return username.decode('utf-8')

class AdminIndexHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        self.render(
            "admin/index.html",
            title="管理后台",
            username=self.current_user,
            menus=FunctionRepository.get_menu_tree(),
        )

class AdminWelcomeHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        self.render("admin/welcome.html", title="欢迎页")

class AdminStatsHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        with get_connection() as conn:
            user_count = conn.execute("select count(*) as total from users").fetchone()["total"]
            employee_count = conn.execute("select count(*) as total from digital_employees where status=1").fetchone()["total"]
            source_count = conn.execute("select count(*) as total from surveillance_sources where status=1").fetchone()["total"]
            model_usage = conn.execute(
                "select coalesce(sum(total_tokens),0) as total_tokens, count(*) as total_calls from model_usage_logs"
            ).fetchone()
        
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps({
            "code": 0,
            "msg": "",
            "data": {
                "user_count": user_count,
                "employee_count": employee_count,
                "model_calls": model_usage["total_calls"],
                "source_count": source_count
            }
        }, ensure_ascii=False))
