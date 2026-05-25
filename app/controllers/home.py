import tornado.web

from app.controllers.base import BaseHandler
from app.models.user import UserRepository

class IndexHandler(BaseHandler):
	@tornado.web.authenticated
	def get(self):
		if not UserRepository.can_access_front(self.current_user):
			self.clear_cookie("username")
			self.redirect("/auth/login")
			return
		user_row = UserRepository.get_user_by_username(self.current_user)
		self.render(
			"index.html",
			title="智能问数",
			username=self.current_user,
			role=(user_row["role"] if user_row else "普通用户"),
		)
