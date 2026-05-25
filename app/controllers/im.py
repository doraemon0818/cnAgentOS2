import hashlib
import json
import os
import secrets

import tornado.gen
import tornado.iostream
import tornado.web

from app.controllers.base import BaseHandler
from app.models.im import IMAsyncService, IMRepository
from app.models.user import UserRepository


class IMBaseHandler(BaseHandler):
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


class IMIndexHandler(IMBaseHandler):
    @tornado.web.authenticated
    def get(self):
        user_row = self._get_current_user_row()
        if not user_row:
            self.clear_cookie("username")
            self.redirect("/auth/login")
            return
        self.render(
            "im.html",
            title="智能聊天",
            username=user_row["username"],
            role=user_row.get("role") or "普通用户",
        )


class IMApiHandler(IMBaseHandler):
    @tornado.web.authenticated
    def get(self):
        user_row = self._get_current_user_row()
        if not user_row:
            self.set_status(403)
            self._write_json({"code": 1, "msg": "当前账号没有前端访问权限"})
            return

        action = (self.get_argument("action", "bootstrap") or "").strip()
        try:
            if action == "bootstrap":
                self._write_json({"code": 0, "msg": "ok", "data": IMAsyncService.get_bootstrap(user_row["id"], user_row["username"])})
                return

            if action == "detail":
                conversation_id = int(self.get_argument("conversation_id", 0) or 0)
                data = IMRepository.get_conversation_detail(user_row["id"], conversation_id)
                self._write_json({"code": 0, "msg": "ok", "data": data})
                return

            if action == "search_users":
                keyword = (self.get_argument("keyword", "") or "").strip()
                self._write_json({"code": 0, "msg": "ok", "data": IMRepository.search_users(user_row["id"], keyword)})
                return

            if action == "open_private":
                target_user_id = int(self.get_argument("target_user_id", 0) or 0)
                data = IMRepository.open_private_conversation(user_row["id"], target_user_id)
                self._write_json({"code": 0, "msg": "ok", "data": data})
                return

            if action == "open_employee":
                employee_id = int(self.get_argument("employee_id", 0) or 0)
                data = IMRepository.open_employee_conversation(user_row["id"], employee_id)
                self._write_json({"code": 0, "msg": "ok", "data": data})
                return

            if action == "group_members":
                conversation_id = int(self.get_argument("conversation_id", 0) or 0)
                data = IMRepository.get_group_members(user_row["id"], conversation_id)
                self._write_json({"code": 0, "msg": "ok", "data": data})
                return

            self._write_json({"code": 1, "msg": "未知操作"})
        except Exception as exc:
            self._write_json({"code": 1, "msg": str(exc)})

    @tornado.web.authenticated
    async def post(self):
        user_row = self._get_current_user_row()
        if not user_row:
            self.set_status(403)
            self._write_json({"code": 1, "msg": "当前账号没有前端访问权限"})
            return

        action = (self.get_argument("action", "") or "").strip()
        try:
            if action == "add_friend":
                target_user_id = int(self.get_body_argument("target_user_id", 0) or 0)
                success, message = IMRepository.add_friend(user_row["id"], target_user_id)
                self._write_json({"code": 0 if success else 1, "msg": message})
                return

            if action == "approve_friend":
                requester_user_id = int(self.get_body_argument("requester_user_id", 0) or 0)
                success, message = IMRepository.approve_friend_request(user_row["id"], requester_user_id)
                self._write_json({"code": 0 if success else 1, "msg": message})
                return

            if action == "reject_friend":
                requester_user_id = int(self.get_body_argument("requester_user_id", 0) or 0)
                success, message = IMRepository.reject_friend_request(user_row["id"], requester_user_id)
                self._write_json({"code": 0 if success else 1, "msg": message})
                return

            if action == "remove_friend":
                friend_user_id = int(self.get_body_argument("friend_user_id", 0) or 0)
                success, message = IMRepository.remove_friend(user_row["id"], friend_user_id)
                self._write_json({"code": 0 if success else 1, "msg": message})
                return

            if action == "create_group":
                name = (self.get_body_argument("name", "") or "").strip()
                member_user_ids = [int(item) for item in (self.get_body_argument("member_user_ids", "") or "").split(",") if item.strip().isdigit()]
                member_employee_ids = [int(item) for item in (self.get_body_argument("member_employee_ids", "") or "").split(",") if item.strip().isdigit()]
                success, message, data = IMRepository.create_group(user_row["id"], name, member_user_ids, member_employee_ids)
                self._write_json({"code": 0 if success else 1, "msg": message, "data": data})
                return

            if action == "send_message":
                conversation_id = int(self.get_body_argument("conversation_id", 0) or 0) or None
                target_user_id = int(self.get_body_argument("target_user_id", 0) or 0) or None
                target_employee_id = int(self.get_body_argument("target_employee_id", 0) or 0) or None
                content_type = (self.get_body_argument("content_type", "text") or "text").strip()
                content_text = self.get_body_argument("content_text", "")
                file_id = int(self.get_body_argument("file_id", 0) or 0) or None
                extra_json = (self.get_body_argument("extra_json", "") or "").strip()
                try:
                    extra = json.loads(extra_json) if extra_json else {}
                except json.JSONDecodeError:
                    self._write_json({"code": 1, "msg": "extra_json 格式错误"})
                    return
                data = await IMAsyncService.send_message(
                    user_id=user_row["id"],
                    username=user_row["username"],
                    content_type=content_type,
                    content_text=content_text,
                    conversation_id=conversation_id,
                    target_user_id=target_user_id,
                    target_employee_id=target_employee_id,
                    file_id=file_id,
                    extra=extra,
                )
                self._write_json({"code": 0, "msg": "ok", "data": data})
                return

            self._write_json({"code": 1, "msg": "未知操作"})
        except Exception as exc:
            self._write_json({"code": 1, "msg": str(exc)})


class IMUploadHandler(IMBaseHandler):
    @tornado.web.authenticated
    def post(self):
        user_row = self._get_current_user_row()
        if not user_row:
            self.set_status(403)
            self._write_json({"code": 1, "msg": "当前账号没有前端访问权限"})
            return

        files = self.request.files.get("file") or []
        if not files:
            self._write_json({"code": 1, "msg": "请选择文件"})
            return

        file_meta = files[0]
        body = file_meta.get("body") or b""
        if not body:
            self._write_json({"code": 1, "msg": "文件内容为空"})
            return

        original_name = file_meta.get("filename") or "upload.bin"
        content_type = file_meta.get("content_type") or "application/octet-stream"
        file_hash = hashlib.sha256(body).hexdigest()
        existing_file = IMRepository.get_file_record_by_hash(file_hash)
        if existing_file:
            self._write_json(
                {
                    "code": 0,
                    "msg": "上传成功",
                    "data": {
                        "file_id": existing_file["id"],
                        "file_name": existing_file["original_name"],
                        "file_url": existing_file["file_url"],
                        "file_size": existing_file["size_bytes"],
                        "mime_type": existing_file["mime_type"],
                    },
                }
            )
            return

        _, ext = os.path.splitext(original_name)
        safe_name = secrets.token_hex(12) + (ext or "")
        relative_dir = os.path.join("uploads", "im")
        abs_dir = os.path.join(self.settings["static_path"], relative_dir)
        os.makedirs(abs_dir, exist_ok=True)
        relative_path = os.path.join(relative_dir, safe_name)
        abs_path = os.path.join(self.settings["static_path"], relative_path)
        with open(abs_path, "wb") as fp:
            fp.write(body)

        file_id = IMRepository.save_file_record(
            file_hash=file_hash,
            original_name=original_name,
            mime_type=content_type,
            size_bytes=len(body),
            relative_path=relative_path,
            upload_user_id=user_row["id"],
        )
        self._write_json(
            {
                "code": 0,
                "msg": "上传成功",
                "data": {
                    "file_id": file_id,
                    "file_name": original_name,
                    "file_url": "/static/" + relative_path.replace("\\", "/"),
                    "file_size": len(body),
                    "mime_type": content_type,
                },
            }
        )


class IMStreamHandler(IMBaseHandler):
    @tornado.web.authenticated
    async def get(self):
        user_row = self._get_current_user_row()
        if not user_row:
            self.set_status(403)
            self.write("data: " + json.dumps({"type": "error", "message": "当前账号没有前端访问权限"}, ensure_ascii=False) + "\n\n")
            return

        self.set_header("Content-Type", "text/event-stream; charset=utf-8")
        self.set_header("Cache-Control", "no-cache")
        self.set_header("Connection", "keep-alive")
        await self.flush()

        last_marker = ""
        heartbeat = 0
        try:
            while True:
                state = IMRepository.get_stream_state(user_row["id"])
                if state["marker"] != last_marker:
                    self.write("data: " + json.dumps({"type": "update", "data": state}, ensure_ascii=False) + "\n\n")
                    await self.flush()
                    last_marker = state["marker"]
                heartbeat += 1
                if heartbeat >= 15:
                    self.write("data: " + json.dumps({"type": "ping"}, ensure_ascii=False) + "\n\n")
                    await self.flush()
                    heartbeat = 0
                await tornado.gen.sleep(1)
        except tornado.iostream.StreamClosedError:
            return
        except Exception as exc:
            try:
                self.write("data: " + json.dumps({"type": "error", "message": str(exc)}, ensure_ascii=False) + "\n\n")
                await self.flush()
            except Exception:
                return
