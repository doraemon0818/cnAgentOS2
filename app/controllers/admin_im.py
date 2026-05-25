import json
import os

import tornado.web

from app.controllers.admin import AdminBaseHandler
from app.models.im import IMRepository
from app.models.user import UserRepository


def _parse_ids(ids_text: str):
    return [int(item) for item in (ids_text or "").split(",") if item.strip().isdigit()]


class AdminIMListHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        self.render("admin/im/list.html", title="智能聊天管理", username=self.current_user)


class AdminIMApiHandler(AdminBaseHandler):
    def _write_json(self, data):
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(data, ensure_ascii=False))

    def _get_admin_user_id(self):
        row = UserRepository.get_user_by_username(self.current_user or "")
        return int(row["id"]) if row else 0

    @tornado.web.authenticated
    def get(self):
        action = (self.get_argument("action", "") or "").strip()
        try:
            if action == "meta":
                self._write_json({"code": 0, "msg": "ok", "data": IMRepository.get_admin_meta()})
                return

            if action == "group_list":
                page = int(self.get_argument("page", 1) or 1)
                limit = int(self.get_argument("limit", 20) or 20)
                keyword = (self.get_argument("keyword", "") or "").strip()
                result = IMRepository.list_group_admin(page=page, page_size=limit, keyword=keyword)
                self._write_json({"code": 0, "msg": "", "count": result["total"], "data": result["list"]})
                return

            if action == "group_detail":
                group_id = int(self.get_argument("id", 0) or 0)
                data = IMRepository.get_group_admin_detail(group_id)
                if not data:
                    self._write_json({"code": 1, "msg": "群聊不存在"})
                    return
                self._write_json({"code": 0, "msg": "ok", "data": data})
                return

            if action == "file_list":
                page = int(self.get_argument("page", 1) or 1)
                limit = int(self.get_argument("limit", 20) or 20)
                keyword = (self.get_argument("keyword", "") or "").strip()
                result = IMRepository.list_files(page=page, page_size=limit, keyword=keyword)
                self._write_json({"code": 0, "msg": "", "count": result["total"], "data": result["list"]})
                return

            if action == "server_list":
                page = int(self.get_argument("page", 1) or 1)
                limit = int(self.get_argument("limit", 20) or 20)
                keyword = (self.get_argument("keyword", "") or "").strip()
                result = IMRepository.list_servers(page=page, page_size=limit, keyword=keyword)
                self._write_json({"code": 0, "msg": "", "count": result["total"], "data": result["list"]})
                return

            if action == "server_detail":
                server_id = int(self.get_argument("id", 0) or 0)
                data = IMRepository.get_server_detail(server_id)
                if not data:
                    self._write_json({"code": 1, "msg": "聊天服务器不存在"})
                    return
                self._write_json({"code": 0, "msg": "ok", "data": data})
                return

            if action == "tool_list":
                page = int(self.get_argument("page", 1) or 1)
                limit = int(self.get_argument("limit", 20) or 20)
                keyword = (self.get_argument("keyword", "") or "").strip()
                result = IMRepository.list_tools(page=page, page_size=limit, keyword=keyword)
                self._write_json({"code": 0, "msg": "", "count": result["total"], "data": result["list"]})
                return

            if action == "tool_detail":
                tool_id = int(self.get_argument("id", 0) or 0)
                data = IMRepository.get_tool_detail(tool_id)
                if not data:
                    self._write_json({"code": 1, "msg": "AI工具不存在"})
                    return
                self._write_json({"code": 0, "msg": "ok", "data": data})
                return

            self._write_json({"code": 1, "msg": "未知操作"})
        except Exception as exc:
            self._write_json({"code": 1, "msg": str(exc)})

    @tornado.web.authenticated
    def post(self):
        action = (self.get_argument("action", "") or "").strip()
        try:
            if action == "group_notice":
                group_id = int(self.get_body_argument("group_id", 0) or 0)
                title = self.get_body_argument("title", "")
                content = self.get_body_argument("content", "")
                success, message = IMRepository.save_group_notice(group_id, title, content, self._get_admin_user_id())
                self._write_json({"code": 0 if success else 1, "msg": message})
                return

            if action == "group_status":
                group_id = int(self.get_body_argument("group_id", 0) or 0)
                status = int(self.get_body_argument("status", 1) or 1)
                success, message = IMRepository.update_group_status(group_id, status)
                self._write_json({"code": 0 if success else 1, "msg": message})
                return

            if action == "file_delete":
                file_ids = [int(self.get_body_argument("id", 0) or 0)]
                project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                success, message = IMRepository.delete_files(file_ids, project_root)
                self._write_json({"code": 0 if success else 1, "msg": message})
                return

            if action == "file_batch_delete":
                file_ids = _parse_ids(self.get_body_argument("ids", ""))
                project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                success, message = IMRepository.delete_files(file_ids, project_root)
                self._write_json({"code": 0 if success else 1, "msg": message})
                return

            if action == "server_save":
                server_id = int(self.get_body_argument("id", 0) or 0) or None
                payload = {
                    "name": self.get_body_argument("name", ""),
                    "code": self.get_body_argument("code", ""),
                    "protocol": self.get_body_argument("protocol", "polling"),
                    "base_url": self.get_body_argument("base_url", ""),
                    "health_url": self.get_body_argument("health_url", ""),
                    "weight": self.get_body_argument("weight", "100"),
                    "priority": self.get_body_argument("priority", "1"),
                    "status": self.get_body_argument("status", "1"),
                    "remark": self.get_body_argument("remark", ""),
                }
                success, message = IMRepository.save_server(payload, server_id=server_id)
                self._write_json({"code": 0 if success else 1, "msg": message})
                return

            if action == "server_delete":
                server_id = int(self.get_body_argument("id", 0) or 0)
                success, message = IMRepository.delete_server(server_id)
                self._write_json({"code": 0 if success else 1, "msg": message})
                return

            if action == "tool_save":
                tool_id = int(self.get_body_argument("id", 0) or 0) or None
                payload = {
                    "name": self.get_body_argument("name", ""),
                    "code": self.get_body_argument("code", ""),
                    "tool_type": self.get_body_argument("tool_type", "endpoint"),
                    "endpoint_id": self.get_body_argument("endpoint_id", ""),
                    "description": self.get_body_argument("description", ""),
                    "config_json": self.get_body_argument("config_json", "{}"),
                    "status": self.get_body_argument("status", "1"),
                }
                employee_ids = _parse_ids(self.get_body_argument("employee_ids", ""))
                success, message = IMRepository.save_tool(payload, tool_id=tool_id, employee_ids=employee_ids)
                self._write_json({"code": 0 if success else 1, "msg": message})
                return

            if action == "tool_delete":
                tool_id = int(self.get_body_argument("id", 0) or 0)
                success, message = IMRepository.delete_tool(tool_id)
                self._write_json({"code": 0 if success else 1, "msg": message})
                return

            self._write_json({"code": 1, "msg": "未知操作"})
        except Exception as exc:
            self._write_json({"code": 1, "msg": str(exc)})
