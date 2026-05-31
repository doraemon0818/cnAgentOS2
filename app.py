# 程序的主入口
# 承担服务器容器+程序作用
# 服务器容器：提供http容器服务，程序放置于该容器中运行
# 程序：本体-智能瞭望与智能问数系统 B/s架构
import os
import tornado.ioloop
import tornado.web
from tornado.httpserver import HTTPServer

# from app.controllers.base import BaseHandler
# 引入auth-controller层
from app.controllers.auth import LoginHandler,LogoutHandler,RegisterHandler
from app.controllers.chat import UserChatBootstrapHandler,UserChatSessionHandler,UserChatStreamHandler,ImageProxyHandler
from app.controllers.im import IMApiHandler, IMIndexHandler, IMStreamHandler, IMUploadHandler
from app.controllers.home import IndexHandler
# 引入admin-controller层
from app.controllers.admin import AdminLoginHandler,AdminLogoutHandler,AdminIndexHandler,AdminWelcomeHandler,AdminStatsHandler
from app.controllers.admin_im import AdminIMApiHandler, AdminIMListHandler
from app.controllers.admin_user import AdminUserListHandler,AdminUserApiHandler
from app.controllers.admin_function import AdminFunctionListHandler,AdminFunctionApiHandler
from app.controllers.admin_role import AdminRoleListHandler,AdminRoleApiHandler
from app.controllers.admin_permission import AdminPermissionListHandler,AdminPermissionApiHandler
from app.controllers.admin_model import AdminModelListHandler,AdminModelApiHandler,AdminModelTestHandler,AdminModelStreamHandler
from app.controllers.admin_interface import (
	AdminInterfaceListHandler,
	AdminInterfaceApiHandler,
	AdminInterfaceTestHandler,
	AdminInterfaceServiceHandler,
)
from app.controllers.admin_employee import AdminEmployeeListHandler,AdminEmployeeApiHandler
from app.controllers.admin_surveillance import (
	AdminSurveillanceSourceListHandler,
	AdminSurveillanceCollectHandler,
	AdminWarehouseListHandler,
	AdminSurveillanceSourceApiHandler,
	AdminSurveillanceCollectApiHandler,
	AdminWarehouseApiHandler,
	AdminWarehouseDeepCollectStreamHandler,
)
from app.controllers.admin_data_screen import (
	AdminDataScreenHandler,
	AdminDataScreenApiHandler,
	AdminOpinionListHandler,
	AdminOpinionApiHandler,
	AdminOpinionAnalyzeStreamHandler,
)
from app.controllers.employee import EmployeeOptionsHandler,EmployeeChatHandler,EmployeeStreamHandler,WeatherImageHandler
from app.controllers.database import DatabaseConfigHandler, DatabaseTestHandler, DatabaseMigrateHandler, AdminDatabaseHandler
from app.controllers.admin_scheduler import AdminSchedulerListHandler, AdminSchedulerApiHandler
from app.controllers.admin_workflow import AdminWorkflowListHandler, AdminWorkflowApiHandler, AdminWorkflowStatsHandler
from app.controllers.admin_monitor import AdminMonitorDashboardHandler, AdminMonitorStatsHandler, AdminReportDownloadHandler, AdminReportDeleteHandler
# 引入db-auth层
from app.models.db import init_db

# class HealthHandler(tornado.web.RequestHandler):
# 	def get(self):
# 		self.write({"status":"ok"})

# class LoginHandler(tornado.web.RequestHandler):
# 	def get(self):
# 		self.write(f"""<h3>模拟登录验证测试BaseHandler</h3>"
# 			<form method="post">

# 			{self.xsrf_form_html()}
# 			<button type="submit">登录admin</button>
# 			</form>
# 			""")
# 	def post(self):
# 		next_url = self.get_argument("next","/private")
# 		self.set_secure_cookie("username","admin")
# 		# 写完安全的cookie以后，跳转到目标地址
# 		self.redirect(next_url)

# class PrivateHandler(BaseHandler):
# 	@tornado.web.authenticated
# 	def get(self):
# 		self.write(self.current_user)

def make_app():
	# return tornado.web.Application([
	# 		("/abc",HealthHandler),
	# 		("/login.jsp",HealthHandler),

	# 	],debug=True)
	# return tornado.web.Application([
	# 	(r"/",LoginHandler),
	# 	(r"/abc",HealthHandler),
	# 	(r"/private",PrivateHandler)
	# 	],
	# 	cookie_secret = "demo-cookie-secret-change-me",
	# 	login_url = "/",
	# 	xsrf_cookies = True,
	# 	debug = True
	# 	)
	base_url = os.path.dirname(os.path.abspath(__file__))
	settings = dict(
		# 预留view层的内容配置
		template_path=os.path.join(base_url,"app","templates"),
		static_path=os.path.join(base_url,"app","static"),
		cookie_secret = "demo-cookie-secret-change-me",
		login_url = "/auth/login",
		xsrf_cookies = True,
		debug = True,
		autoreload=True
	)
	return tornado.web.Application([
		(r"/",IndexHandler),
		(r"/auth/login",LoginHandler),
		(r"/auth/register",RegisterHandler),
		(r"/auth/logout",LogoutHandler),
		(r"/api/chat/bootstrap",UserChatBootstrapHandler),
		(r"/api/chat/session",UserChatSessionHandler),
		(r"/api/chat/stream",UserChatStreamHandler),
		(r"/im",IMIndexHandler),
		(r"/api/im",IMApiHandler),
		(r"/api/im/stream",IMStreamHandler),
		(r"/api/im/upload",IMUploadHandler),
		(r"/api/employee/options",EmployeeOptionsHandler),
		(r"/api/employee/chat",EmployeeChatHandler),
		(r"/api/employee/stream",EmployeeStreamHandler),
		(r"/api/weather/image",WeatherImageHandler),
		(r"/api/image/proxy",ImageProxyHandler),
		(r"/api/database/config",DatabaseConfigHandler),
		(r"/api/database/test",DatabaseTestHandler),
		(r"/api/database/migrate",DatabaseMigrateHandler),
		(r"/admin/scheduler/list",AdminSchedulerListHandler),
		(r"/admin/scheduler/api",AdminSchedulerApiHandler),
		(r"/admin/workflow/list",AdminWorkflowListHandler),
		(r"/admin/workflow/api",AdminWorkflowApiHandler),
		(r"/admin/workflow/stats",AdminWorkflowStatsHandler),
		(r"/admin/monitor",AdminMonitorDashboardHandler),
		(r"/admin/monitor/api",AdminMonitorStatsHandler),
		(r"/admin/monitor/download",AdminReportDownloadHandler),
		(r"/admin/monitor/delete",AdminReportDeleteHandler),
		(r"/admin/database",AdminDatabaseHandler),
		(r"/admin/login",AdminLoginHandler),
		(r"/admin/logout",AdminLogoutHandler),
		(r"/admin",AdminIndexHandler),
		(r"/admin/welcome",AdminWelcomeHandler),
		(r"/admin/api/stats",AdminStatsHandler),
		(r"/admin/user/list",AdminUserListHandler),
		(r"/admin/api/user",AdminUserApiHandler),
		(r"/admin/function/list",AdminFunctionListHandler),
		(r"/admin/api/function",AdminFunctionApiHandler),
		(r"/admin/role/list",AdminRoleListHandler),
		(r"/admin/api/role",AdminRoleApiHandler),
		(r"/admin/permission/list",AdminPermissionListHandler),
		(r"/admin/api/permission",AdminPermissionApiHandler),
		(r"/admin/model/list",AdminModelListHandler),
		(r"/admin/api/model",AdminModelApiHandler),
		(r"/admin/api/model/test",AdminModelTestHandler),
		(r"/admin/api/model/stream",AdminModelStreamHandler),
		(r"/admin/interface/list",AdminInterfaceListHandler),
		(r"/admin/api/interface",AdminInterfaceApiHandler),
		(r"/admin/api/interface/test",AdminInterfaceTestHandler),
		(r"/admin/api/interface/service",AdminInterfaceServiceHandler),
		(r"/admin/employee/list",AdminEmployeeListHandler),
		(r"/admin/api/employee",AdminEmployeeApiHandler),
		(r"/admin/im/list",AdminIMListHandler),
		(r"/admin/api/im",AdminIMApiHandler),
		(r"/admin/surveillance/source/list",AdminSurveillanceSourceListHandler),
		(r"/admin/surveillance/collect",AdminSurveillanceCollectHandler),
		(r"/admin/api/surveillance/source",AdminSurveillanceSourceApiHandler),
		(r"/admin/api/surveillance/collect",AdminSurveillanceCollectApiHandler),
		(r"/admin/warehouse/list",AdminWarehouseListHandler),
		(r"/admin/api/warehouse",AdminWarehouseApiHandler),
		(r"/admin/api/warehouse/deep/stream",AdminWarehouseDeepCollectStreamHandler),
		(r"/admin/data/screen",AdminDataScreenHandler),
		(r"/admin/api/data/screen",AdminDataScreenApiHandler),
		(r"/admin/opinion/list",AdminOpinionListHandler),
		(r"/admin/api/opinion",AdminOpinionApiHandler),
		(r"/admin/api/opinion/analyze/stream",AdminOpinionAnalyzeStreamHandler),
		],
		**settings

		)

if __name__=="__main__":
	# 启动服务之前，检查并初始化数据库表
	init_db()
	app = make_app()
	server = HTTPServer(app)
	server.bind(10086)
	# 自动CPU核心数
	server.start()

	print("======= Server 启动成功 ======= 端口：10086 ======",flush=True)
	tornado.ioloop.IOLoop.current().start()
