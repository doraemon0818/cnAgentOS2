import tornado.web
from app.controllers.base import BaseHandler
from app.models.function import FunctionRepository
from app.models.user import UserRepository

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
