import json
import tornado.web
from app.controllers.admin import AdminBaseHandler
from app.models.role import RoleRepository
from app.models.user import UserRepository

class AdminUserListHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        self.render("admin/user/list.html", title="用户列表", username=self.current_user)

class AdminUserApiHandler(AdminBaseHandler):
    def _write_json(self, data):
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(data, ensure_ascii=False))

    @tornado.web.authenticated
    def get(self):
        action = self.get_argument("action", "")

        if action == "role_options":
            self._write_json({
                "code": 0,
                "msg": "",
                "data": RoleRepository.get_role_options(active_only=True)
            })
            return

        page = int(self.get_argument("page", 1))
        limit = int(self.get_argument("limit", 20))
        keyword = (self.get_argument("keyword", "") or "").strip()

        result = UserRepository.get_user_list(page=page, page_size=limit, keyword=keyword)

        self._write_json({
            "code": 0,
            "msg": "",
            "count": result["total"],
            "data": result["list"]
        })

    @tornado.web.authenticated
    def post(self):
        action = self.get_argument("action", "")

        if action == "add":
            username = (self.get_body_argument("username", "") or "").strip()
            password = self.get_body_argument("password", "")
            email = (self.get_body_argument("email", "") or "").strip()
            phone = (self.get_body_argument("phone", "") or "").strip()
            role = (self.get_body_argument("role", "") or "").strip()

            if not username or not password:
                self._write_json({"code": 1, "msg": "用户名和密码不能为空"})
                return

            valid, message = UserRepository.validate_create_user(username, password, role)
            if not valid:
                self._write_json({"code": 1, "msg": message})
                return

            success = UserRepository.create_user(username, password, email, phone, role)
            if success:
                self._write_json({"code": 0, "msg": "新增成功"})
            else:
                self._write_json({"code": 1, "msg": "新增失败，请稍后重试"})

        elif action == "update":
            user_id = int(self.get_body_argument("id", 0))
            email = (self.get_body_argument("email", "") or "").strip()
            phone = (self.get_body_argument("phone", "") or "").strip()
            role = (self.get_body_argument("role", "") or "").strip()
            status = int(self.get_body_argument("status", -1))

            if not user_id:
                self._write_json({"code": 1, "msg": "用户ID不能为空"})
                return

            success = UserRepository.update_user(user_id, email, phone, role, status)
            if success:
                self._write_json({"code": 0, "msg": "修改成功"})
            else:
                self._write_json({"code": 1, "msg": "修改失败，系统用户不可修改或角色无效"})

        elif action == "change_password":
            user_id = int(self.get_body_argument("id", 0))
            password = self.get_body_argument("password", "")

            if not user_id or not password:
                self._write_json({"code": 1, "msg": "用户ID和新密码不能为空"})
                return

            success = UserRepository.update_password(user_id, password)
            if success:
                self._write_json({"code": 0, "msg": "密码修改成功"})
            else:
                self._write_json({"code": 1, "msg": "密码修改失败"})

        elif action == "delete":
            user_id = int(self.get_body_argument("id", 0))
            if not user_id:
                self._write_json({"code": 1, "msg": "用户ID不能为空"})
                return

            success = UserRepository.delete_user(user_id)
            if success:
                self._write_json({"code": 0, "msg": "删除成功"})
            else:
                self._write_json({"code": 1, "msg": "删除失败，系统用户不可删除"})

        elif action == "batch_delete":
            ids_str = self.get_body_argument("ids", "")
            if not ids_str:
                self._write_json({"code": 1, "msg": "请选择要删除的用户"})
                return

            user_ids = [int(x) for x in ids_str.split(",") if x.isdigit()]
            if not user_ids:
                self._write_json({"code": 1, "msg": "用户ID格式错误"})
                return

            result = UserRepository.batch_delete_user(user_ids)
            message = f"成功删除{result['deleted']}个用户"
            if result["skipped_system"] > 0:
                message += f"，已自动跳过{result['skipped_system']}个系统用户"
            self._write_json({"code": 0, "msg": message})

        else:
            self._write_json({"code": 1, "msg": "未知操作"})
