import json

import tornado.web

from app.controllers.base import BaseHandler
from app.models.digital_employee import DigitalEmployeeRepository
from app.models.model_engine import ModelEngineRepository
from app.models.user import UserRepository
from app.models.user_chat import AskDataService, UserChatSessionRepository


class UserChatBaseHandler(BaseHandler):
    def _write_json(self, data):
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(data, ensure_ascii=False))

    def _get_current_user_row(self):
        username = self.current_user
        if not username:
            return None
        if not UserRepository.can_access_front(username):
            return None
        row = UserRepository.get_user_by_username(username)
        return dict(row) if row else None


class UserChatBootstrapHandler(UserChatBaseHandler):
    @tornado.web.authenticated
    def get(self):
        user_row = self._get_current_user_row()
        if not user_row:
            self.set_status(403)
            self._write_json({"code": 1, "msg": "当前账号没有前端访问权限"})
            return
        self._write_json(
            {
                "code": 0,
                "msg": "ok",
                "data": {
                    "user": {
                        "id": user_row["id"],
                        "username": user_row["username"],
                        "role": user_row["role"],
                        "role_code": user_row.get("role_code") or "",
                    },
                    "models": ModelEngineRepository.get_model_options(),
                    "employees": DigitalEmployeeRepository.get_employee_options(),
                    "sessions": UserChatSessionRepository.list_sessions(user_row["id"]),
                },
            }
        )


class UserChatSessionHandler(UserChatBaseHandler):
    @tornado.web.authenticated
    def get(self):
        user_row = self._get_current_user_row()
        if not user_row:
            self.set_status(403)
            self._write_json({"code": 1, "msg": "当前账号没有前端访问权限"})
            return

        session_id = int(self.get_argument("session_id", 0) or 0)
        if not session_id:
            self._write_json({"code": 0, "msg": "ok", "data": {"sessions": UserChatSessionRepository.list_sessions(user_row["id"])}})
            return

        session, messages = UserChatSessionRepository.get_messages(user_row["id"], session_id)
        if not session:
            self._write_json({"code": 1, "msg": "会话不存在或无权访问"})
            return
        self._write_json({"code": 0, "msg": "ok", "data": {"session": session, "messages": messages}})

    @tornado.web.authenticated
    def post(self):
        user_row = self._get_current_user_row()
        if not user_row:
            self.set_status(403)
            self._write_json({"code": 1, "msg": "当前账号没有前端访问权限"})
            return

        action = (self.get_body_argument("action", "") or "").strip()
        if action != "delete":
            self._write_json({"code": 1, "msg": "未知操作"})
            return

        session_id = int(self.get_body_argument("session_id", 0) or 0)
        if not session_id:
            self._write_json({"code": 1, "msg": "会话ID不能为空"})
            return

        success = UserChatSessionRepository.delete_session(user_row["id"], session_id)
        if not success:
            self._write_json({"code": 1, "msg": "会话不存在或无权删除"})
            return
        self._write_json({"code": 0, "msg": "历史会话已删除", "data": {"sessions": UserChatSessionRepository.list_sessions(user_row["id"])}})


class UserChatStreamHandler(UserChatBaseHandler):
    @tornado.web.authenticated
    async def get(self):
        user_row = self._get_current_user_row()
        if not user_row:
            self.set_status(403)
            self.write("data: " + json.dumps({"type": "error", "message": "当前账号没有前端访问权限"}, ensure_ascii=False) + "\n\n")
            return

        message = (self.get_argument("message", "") or "").strip()
        session_id = int(self.get_argument("session_id", 0) or 0)
        model_id = int(self.get_argument("model_id", 0) or 0)
        if not message:
            self.set_status(400)
            self.write("data: " + json.dumps({"type": "error", "message": "消息内容不能为空"}, ensure_ascii=False) + "\n\n")
            return

        self.set_header("Content-Type", "text/event-stream; charset=utf-8")
        self.set_header("Cache-Control", "no-cache")
        self.set_header("Connection", "keep-alive")
        await self.flush()

        try:
            async for item in AskDataService.stream_chat(
                user_id=user_row["id"],
                username=user_row["username"],
                message=message,
                session_id=session_id if session_id > 0 else None,
                model_id=model_id if model_id > 0 else None,
            ):
                self.write("data: " + json.dumps(item, ensure_ascii=False) + "\n\n")
                await self.flush()
        except Exception as exc:
            self.write("data: " + json.dumps({"type": "error", "message": str(exc)}, ensure_ascii=False) + "\n\n")
            await self.flush()
