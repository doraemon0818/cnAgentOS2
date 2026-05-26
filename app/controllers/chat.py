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


class ImageProxyHandler(BaseHandler):
    async def get(self):
        import urllib.parse
        url = urllib.parse.unquote(self.get_argument("url", ""))
        print(f"[ImageProxy] Request received, URL: {url[:100]}...")
        if not url or not url.startswith("http"):
            self.set_status(400)
            self.write("Invalid URL")
            return
        allowed_domains = [
            "p2.music.126.net",
            "p1.music.126.net",
            "music.126.net",
            "music.163.com",
        ]
        from urllib.parse import urlparse
        parsed = urlparse(url)
        print(f"[ImageProxy] Parsed domain: {parsed.netloc}")
        if parsed.netloc not in allowed_domains:
            self.set_status(403)
            self.write(f"Domain not allowed: {parsed.netloc}")
            return
        try:
            import requests
            headers = {
                "Referer": "https://music.163.com/",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache"
            }
            print(f"[ImageProxy] Fetching image from: {url[:80]}...")
            response = requests.get(
                url,
                headers=headers,
                timeout=15,
                verify=False,
                allow_redirects=True
            )
            print(f"[ImageProxy] Response status: {response.status_code}")
            if response.status_code != 200:
                self.set_status(response.status_code)
                self.write(f"Failed to fetch image: {response.status_code}")
                return
            content_type = response.headers.get("Content-Type", "image/jpeg")
            self.set_header("Content-Type", content_type)
            self.set_header("Cache-Control", "public, max-age=86400")
            image_data = response.content
            print(f"[ImageProxy] Success! Image size: {len(image_data)} bytes, Content-Type: {content_type}")
            self.write(image_data)
        except Exception as exc:
            import traceback
            print(f"[ImageProxy] Error: {exc}")
            traceback.print_exc()
            self.set_status(500)
            self.write(f"Proxy error: {str(exc)}")
