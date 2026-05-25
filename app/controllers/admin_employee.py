import json

import tornado.web

from app.controllers.admin import AdminBaseHandler
from app.models.digital_employee import DigitalEmployeeRepository


class AdminEmployeeListHandler(AdminBaseHandler):
    @tornado.web.authenticated
    def get(self):
        self.render("admin/employee/list.html", title="数字员工", username=self.current_user)


class AdminEmployeeApiHandler(AdminBaseHandler):
    def _write_json(self, data):
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(data, ensure_ascii=False))

    @tornado.web.authenticated
    def get(self):
        action = self.get_argument("action", "list")
        if action == "detail":
            employee_id = int(self.get_argument("id", 0))
            data = DigitalEmployeeRepository.get_employee_by_id(employee_id)
            if not data:
                self._write_json({"code": 1, "msg": "数字员工不存在"})
                return
            self._write_json({"code": 0, "msg": "", "data": data})
            return

        if action == "options":
            self._write_json({"code": 0, "msg": "", "data": DigitalEmployeeRepository.get_employee_options()})
            return

        page = int(self.get_argument("page", 1))
        limit = int(self.get_argument("limit", 20))
        keyword = (self.get_argument("keyword", "") or "").strip()
        result = DigitalEmployeeRepository.get_employee_list(page=page, page_size=limit, keyword=keyword)
        self._write_json({"code": 0, "msg": "", "count": result["total"], "data": result["list"]})

    @tornado.web.authenticated
    def post(self):
        action = self.get_argument("action", "")
        if action == "delete":
            employee_id = int(self.get_body_argument("id", 0))
            success, message = DigitalEmployeeRepository.delete_employee(employee_id)
            self._write_json({"code": 0 if success else 1, "msg": message})
            return

        payload = {
            "name": self.get_body_argument("name", ""),
            "alias": self.get_body_argument("alias", ""),
            "code": self.get_body_argument("code", ""),
            "category": self.get_body_argument("category", "AI"),
            "model_id": self.get_body_argument("model_id", ""),
            "endpoint_id": self.get_body_argument("endpoint_id", ""),
            "prompt": self.get_body_argument("prompt", ""),
            "api_param_name": self.get_body_argument("api_param_name", ""),
            "api_params_json": self.get_body_argument("api_params_json", "{}"),
            "response_template": self.get_body_argument("response_template", ""),
            "default_user_input": self.get_body_argument("default_user_input", ""),
            "description": self.get_body_argument("description", ""),
            "sort": self.get_body_argument("sort", "0"),
            "status": self.get_body_argument("status", "1"),
        }

        if action == "add":
            success, message = DigitalEmployeeRepository.save_employee(payload)
            self._write_json({"code": 0 if success else 1, "msg": message})
            return

        if action == "update":
            employee_id = int(self.get_body_argument("id", 0))
            success, message = DigitalEmployeeRepository.save_employee(payload, employee_id=employee_id)
            self._write_json({"code": 0 if success else 1, "msg": message})
            return

        self._write_json({"code": 1, "msg": "未知操作"})
