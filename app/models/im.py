import asyncio
import hashlib
import json
import os
import re
import secrets
from typing import Dict, List, Optional

from app.models.api_endpoint import ApiEndpointRepository
from app.models.db import get_connection
from app.models.digital_employee import DigitalEmployeeRepository
from app.models.user import UserRepository


def _safe_json_loads(value, default):
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def _normalize_pair(user_id: int, other_id: int):
    user_low_id = min(int(user_id), int(other_id))
    user_high_id = max(int(user_id), int(other_id))
    return user_low_id, user_high_id


def _clip_text(text: str, limit: int = 120):
    content = (text or "").strip()
    return content if len(content) <= limit else content[: limit - 1] + "..."


def _content_preview(content_type: str, content_text: str, extra: Optional[Dict] = None):
    extra = extra or {}
    if content_type == "file":
        file_name = extra.get("file_name") or content_text or "文件"
        return f"[文件] {file_name}"
    if content_type == "emoji":
        return f"[表情] {content_text}"
    if content_type == "notice":
        return f"[公告] {_clip_text(content_text, 80)}"
    return _clip_text(content_text, 80)


class IMRepository:
    CHAT_PRIVATE = "private"
    CHAT_GROUP = "group"
    CHAT_EMPLOYEE = "employee"

    MEMBER_USER = "user"
    MEMBER_EMPLOYEE = "employee"

    SENDER_USER = "user"
    SENDER_EMPLOYEE = "employee"
    SENDER_SYSTEM = "system"

    CONTENT_TEXT = "text"
    CONTENT_EMOJI = "emoji"
    CONTENT_FILE = "file"
    CONTENT_NOTICE = "notice"

    FRIEND_PENDING = 0
    FRIEND_ACCEPTED = 1
    FRIEND_REJECTED = 2
    FRIEND_DELETED = -1

    EMPLOYEE_MENTION_RE = re.compile(r"@([^\s@：:]+)")

    @staticmethod
    def _front_role_filter_sql():
        placeholders = ",".join(["?"] * len(UserRepository.FRONT_ROLE_CODES))
        return placeholders, list(UserRepository.FRONT_ROLE_CODES)

    @staticmethod
    def _get_user_basic(conn, user_id: int):
        row = conn.execute(
            """
            select u.id,u.username,u.role,u.avatar_path,u.status,coalesce(r.code,'') as role_code
            from users u
            left join roles r on r.name = u.role
            where u.id=?
            """,
            (user_id,),
        ).fetchone()
        if not row:
            return None
        item = dict(row)
        item["avatar_url"] = UserRepository.build_avatar_url(item.get("avatar_path"))
        return item

    @staticmethod
    def _get_employee_basic(conn, employee_id: int):
        row = conn.execute(
            """
            select id,name,alias,code,category,status,description
            from digital_employees
            where id=?
            """,
            (employee_id,),
        ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def _get_file_dict(conn, file_id: Optional[int]):
        if not file_id:
            return None
        row = conn.execute(
            """
            select id,original_name,storage_name,file_ext,mime_type,size_bytes,relative_path,upload_user_id,create_at
            from im_files
            where id=?
            """,
            (file_id,),
        ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def get_file_record_by_hash(file_hash: str):
        with get_connection() as conn:
            row = conn.execute(
                """
                select id,original_name,storage_name,file_ext,mime_type,size_bytes,relative_path,upload_user_id,create_at
                from im_files
                where file_hash=?
                limit 1
                """,
                ((file_hash or "").strip(),),
            ).fetchone()
        if not row:
            return None
        data = dict(row)
        data["file_url"] = "/static/" + data["relative_path"].replace("\\", "/")
        return data

    @staticmethod
    def _conversation_member_exists(conn, conversation_id: int, user_id: int):
        row = conn.execute(
            """
            select 1
            from im_conversation_members
            where conversation_id=? and user_id=? and member_type=? and status=1
            limit 1
            """,
            (conversation_id, user_id, IMRepository.MEMBER_USER),
        ).fetchone()
        return bool(row)

    @staticmethod
    def _load_conversation_row(conn, conversation_id: int):
        row = conn.execute(
            """
            select id,chat_type,name,owner_user_id,group_id,employee_id,private_key,last_message_preview,last_sender_name,
                   last_message_type,last_message_at,status,create_at,update_at
            from im_conversations
            where id=?
            """,
            (conversation_id,),
        ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def _mark_conversation_read(conn, conversation_id: int, user_id: int):
        conn.execute(
            """
            update im_conversation_members
            set last_read_at=datetime('now')
            where conversation_id=? and user_id=? and member_type=? and status=1
            """,
            (conversation_id, user_id, IMRepository.MEMBER_USER),
        )

    @staticmethod
    def mark_conversation_read(user_id: int, conversation_id: int):
        with get_connection() as conn:
            if not IMRepository._conversation_member_exists(conn, int(conversation_id), int(user_id)):
                return False
            IMRepository._mark_conversation_read(conn, int(conversation_id), int(user_id))
        return True

    @staticmethod
    def _count_unread_messages(conn, conversation_id: int, current_user_id: int, chat_type: str, last_read_at: str):
        last_read_at = (last_read_at or "").strip()
        sender_type = IMRepository.SENDER_USER
        if chat_type in (IMRepository.CHAT_PRIVATE, IMRepository.CHAT_EMPLOYEE):
            row = conn.execute(
                """
                select count(*) as total
                from im_private_messages
                where conversation_id=?
                  and not (sender_type=? and coalesce(sender_user_id, 0)=?)
                  and (?='' or create_at>?)
                """,
                (conversation_id, sender_type, int(current_user_id), last_read_at, last_read_at),
            ).fetchone()
            return int(row["total"] if row else 0)
        if chat_type == IMRepository.CHAT_GROUP:
            row = conn.execute(
                """
                select count(*) as total
                from im_group_messages
                where conversation_id=?
                  and not (sender_type=? and coalesce(sender_user_id, 0)=?)
                  and (?='' or create_at>?)
                """,
                (conversation_id, sender_type, int(current_user_id), last_read_at, last_read_at),
            ).fetchone()
            return int(row["total"] if row else 0)
        return 0

    @staticmethod
    def _hydrate_conversation(conn, row: Dict, current_user_id: int):
        item = dict(row)
        item["display_name"] = item.get("name") or "未命名会话"
        item["subtitle"] = ""
        item["target_user_id"] = None
        item["target_employee_id"] = item.get("employee_id")
        item["member_count"] = 0
        item["notice"] = ""
        item["group_status"] = item.get("status", 1)
        member_row = conn.execute(
            """
            select role,status,joined_at,coalesce(last_read_at,'') as last_read_at
            from im_conversation_members
            where conversation_id=? and user_id=? and member_type=?
            limit 1
            """,
            (item["id"], current_user_id, IMRepository.MEMBER_USER),
        ).fetchone()
        item["last_read_at"] = member_row["last_read_at"] if member_row else ""

        if item["chat_type"] == IMRepository.CHAT_PRIVATE:
            other_row = conn.execute(
                """
                select u.id,u.username,u.role,u.avatar_path,u.status
                from im_conversation_members m
                join users u on u.id = m.user_id
                where m.conversation_id=? and m.member_type=? and u.id<>?
                limit 1
                """,
                (item["id"], IMRepository.MEMBER_USER, current_user_id),
            ).fetchone()
            if other_row:
                item["display_name"] = other_row["username"]
                item["subtitle"] = f"私聊 · {other_row['role']}"
                item["target_user_id"] = other_row["id"]
                item["target_avatar_url"] = UserRepository.build_avatar_url(other_row["avatar_path"])
            item["member_count"] = 2

        elif item["chat_type"] == IMRepository.CHAT_EMPLOYEE:
            employee = IMRepository._get_employee_basic(conn, int(item.get("employee_id") or 0))
            if employee:
                item["display_name"] = employee["name"]
                item["subtitle"] = f"数字员工 · {employee['category']}"
                item["target_employee_id"] = employee["id"]
            item["member_count"] = 2

        elif item["chat_type"] == IMRepository.CHAT_GROUP:
            group_row = conn.execute(
                """
                select id,name,notice,status,owner_user_id
                from im_groups
                where conversation_id=?
                """,
                (item["id"],),
            ).fetchone()
            if group_row:
                item["group_id"] = group_row["id"]
                item["display_name"] = group_row["name"]
                item["notice"] = group_row["notice"] or ""
                item["group_status"] = group_row["status"]
            count_row = conn.execute(
                "select count(*) as total from im_conversation_members where conversation_id=? and status=1",
                (item["id"],),
            ).fetchone()
            item["member_count"] = int(count_row["total"] if count_row else 0)
            item["subtitle"] = f"群聊 · {item['member_count']} 人"

        item["last_message_preview"] = item.get("last_message_preview") or ""
        item["last_sender_name"] = item.get("last_sender_name") or ""
        item["last_message_type"] = item.get("last_message_type") or IMRepository.CONTENT_TEXT
        item["last_message_at"] = item.get("last_message_at") or item.get("update_at") or item.get("create_at")
        item["unread_count"] = IMRepository._count_unread_messages(
            conn,
            int(item["id"]),
            int(current_user_id),
            item["chat_type"],
            item.get("last_read_at", ""),
        )
        return item

    @staticmethod
    def _update_conversation_preview(
        conn,
        conversation_id: int,
        sender_name: str,
        content_type: str,
        content_text: str,
        extra: Optional[Dict] = None,
    ):
        preview = _content_preview(content_type, content_text, extra=extra)
        conn.execute(
            """
            update im_conversations
            set last_message_preview=?,last_sender_name=?,last_message_type=?,last_message_at=datetime('now'),update_at=datetime('now')
            where id=?
            """,
            (preview, sender_name, content_type, conversation_id),
        )

    @staticmethod
    def _get_friendship_row(conn, user_id: int, other_user_id: int):
        row = conn.execute(
            """
            select id,user_low_id,user_high_id,status,requester_user_id,target_user_id,action_user_id,action_at,create_at,update_at
            from im_friendships
            where user_low_id=? and user_high_id=?
            limit 1
            """,
            _normalize_pair(user_id, other_user_id),
        ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def _get_friendship_map(conn, user_id: int):
        rows = conn.execute(
            """
            select id,user_low_id,user_high_id,status,requester_user_id,target_user_id,action_user_id,action_at,create_at,update_at
            from im_friendships
            where user_low_id=? or user_high_id=?
            """,
            (int(user_id), int(user_id)),
        ).fetchall()
        mapping = {}
        for row in rows:
            item = dict(row)
            other_id = item["user_high_id"] if int(item["user_low_id"]) == int(user_id) else item["user_low_id"]
            mapping[int(other_id)] = item
        return mapping

    @staticmethod
    def _friend_relation_from_row(row: Optional[Dict], current_user_id: int):
        if not row:
            return "none"
        status = int(row.get("status") or 0)
        requester_user_id = int(row.get("requester_user_id") or 0)
        target_user_id = int(row.get("target_user_id") or 0)
        if status == IMRepository.FRIEND_ACCEPTED:
            return "friend"
        if status == IMRepository.FRIEND_PENDING:
            if requester_user_id == int(current_user_id):
                return "pending_outgoing"
            if target_user_id == int(current_user_id):
                return "pending_incoming"
            return "pending"
        return "none"

    @staticmethod
    def _sync_private_conversation_members(conn, conversation_id: int, user_id: int, other_user_id: int):
        for member_user_id, role in ((int(user_id), "owner"), (int(other_user_id), "member")):
            row = conn.execute(
                """
                select id
                from im_conversation_members
                where conversation_id=? and member_type=? and user_id=?
                limit 1
                """,
                (conversation_id, IMRepository.MEMBER_USER, member_user_id),
            ).fetchone()
            if row:
                conn.execute(
                    """
                    update im_conversation_members
                    set role=?,status=1
                    where id=?
                    """,
                    (role, row["id"]),
                )
            else:
                conn.execute(
                    """
                    insert into im_conversation_members(conversation_id,member_type,user_id,employee_id,role,status,joined_at)
                    values(?,?,?,?,?,?,datetime('now'))
                    """,
                    (conversation_id, IMRepository.MEMBER_USER, member_user_id, None, role, 1),
                )

    @staticmethod
    def _deactivate_private_conversation(conn, user_id: int, other_user_id: int):
        private_key = f"user:{min(user_id, other_user_id)}:{max(user_id, other_user_id)}"
        row = conn.execute(
            "select id from im_conversations where chat_type=? and private_key=? limit 1",
            (IMRepository.CHAT_PRIVATE, private_key),
        ).fetchone()
        if not row:
            return
        conversation_id = int(row["id"])
        conn.execute(
            "update im_conversations set status=-1,update_at=datetime('now') where id=?",
            (conversation_id,),
        )
        conn.execute(
            """
            update im_conversation_members
            set status=0
            where conversation_id=? and member_type=?
            """,
            (conversation_id, IMRepository.MEMBER_USER),
        )

    @staticmethod
    def list_friends(user_id: int, keyword: str = ""):
        user_id = int(user_id)
        sql = """
            select u.id,u.username,u.role,u.avatar_path,u.status,coalesce(r.code,'') as role_code,f.create_at as friendship_at
            from im_friendships f
            join users u on u.id = case when f.user_low_id=? then f.user_high_id else f.user_low_id end
            left join roles r on r.name = u.role
            where (f.user_low_id=? or f.user_high_id=?) and f.status=1
        """
        params: List = [user_id, user_id, user_id]
        if keyword:
            sql += " and (u.username like ? or u.role like ?)"
            like_value = f"%{keyword}%"
            params.extend([like_value, like_value])
        sql += " order by u.username asc"
        with get_connection() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
        data = []
        for row in rows:
            item = dict(row)
            item["is_online"] = 1
            item["avatar_url"] = UserRepository.build_avatar_url(item.get("avatar_path"))
            data.append(item)
        return data

    @staticmethod
    def search_users(user_id: int, keyword: str):
        keyword = (keyword or "").strip()
        if not keyword:
            return []
        placeholders, role_codes = IMRepository._front_role_filter_sql()
        with get_connection() as conn:
            friendship_map = IMRepository._get_friendship_map(conn, int(user_id))
            rows = conn.execute(
                f"""
                select u.id,u.username,u.role,u.avatar_path,u.status,coalesce(r.code,'') as role_code
                from users u
                left join roles r on r.name = u.role
                where u.id<>?
                  and u.status=1
                  and coalesce(r.code,'') in ({placeholders})
                  and u.username like ?
                order by u.username asc
                limit 30
                """,
                tuple([user_id] + role_codes + [f"%{keyword}%"]),
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            friendship_row = friendship_map.get(int(item["id"]))
            relation_status = IMRepository._friend_relation_from_row(friendship_row, int(user_id))
            item["is_friend"] = 1 if relation_status == "friend" else 0
            item["relation_status"] = relation_status
            item["friendship_status"] = int(friendship_row.get("status") or 0) if friendship_row else None
            item["is_online"] = 1
            item["avatar_url"] = UserRepository.build_avatar_url(item.get("avatar_path"))
            result.append(item)
        return result

    @staticmethod
    def add_friend(user_id: int, friend_user_id: int):
        user_id = int(user_id)
        friend_user_id = int(friend_user_id)
        if user_id == friend_user_id:
            return False, "不能添加自己为好友"

        with get_connection() as conn:
            target = IMRepository._get_user_basic(conn, friend_user_id)
            if not target:
                return False, "目标用户不存在"
            if not UserRepository.can_access_front(target["username"]):
                return False, "目标用户不属于前端用户"

            row = IMRepository._get_friendship_row(conn, user_id, friend_user_id)
            if row:
                status = int(row["status"] or 0)
                if status == IMRepository.FRIEND_ACCEPTED:
                    return True, "已是好友"
                if status == IMRepository.FRIEND_PENDING:
                    if int(row.get("requester_user_id") or 0) == user_id:
                        return True, "好友申请已发送，等待对方同意"
                    return False, "对方已向你发来申请，请先在申请列表中处理"
                conn.execute(
                    """
                    update im_friendships
                    set status=?,
                        requester_user_id=?,
                        target_user_id=?,
                        action_user_id=0,
                        action_at='',
                        update_at=datetime('now')
                    where id=?
                    """,
                    (IMRepository.FRIEND_PENDING, user_id, friend_user_id, row["id"]),
                )
            else:
                user_low_id, user_high_id = _normalize_pair(user_id, friend_user_id)
                conn.execute(
                    """
                    insert into im_friendships(
                        user_low_id,user_high_id,status,requester_user_id,target_user_id,action_user_id,action_at,create_at,update_at
                    )
                    values(?,?,?,?,?,?,?,datetime('now'),datetime('now'))
                    """,
                    (user_low_id, user_high_id, IMRepository.FRIEND_PENDING, user_id, friend_user_id, 0, ""),
                )
        return True, "好友申请已发送"

    @staticmethod
    def list_friend_requests(user_id: int):
        user_id = int(user_id)
        with get_connection() as conn:
            rows = conn.execute(
                """
                select id,user_low_id,user_high_id,status,requester_user_id,target_user_id,action_user_id,action_at,create_at,update_at
                from im_friendships
                where status=? and (requester_user_id=? or target_user_id=?)
                order by update_at desc,id desc
                """,
                (IMRepository.FRIEND_PENDING, user_id, user_id),
            ).fetchall()
            incoming = []
            outgoing = []
            for row in rows:
                item = dict(row)
                is_incoming = int(item.get("target_user_id") or 0) == user_id
                other_user_id = int(item["requester_user_id"] if is_incoming else item["target_user_id"])
                other_user = IMRepository._get_user_basic(conn, other_user_id)
                if not other_user:
                    continue
                payload = {
                    "id": int(item["id"]),
                    "user_id": other_user_id,
                    "username": other_user["username"],
                    "role": other_user.get("role") or "",
                    "avatar_url": other_user.get("avatar_url") or "",
                    "create_at": item.get("create_at") or "",
                    "update_at": item.get("update_at") or "",
                    "direction": "incoming" if is_incoming else "outgoing",
                    "relation_status": "pending_incoming" if is_incoming else "pending_outgoing",
                }
                if is_incoming:
                    incoming.append(payload)
                else:
                    outgoing.append(payload)
        return {"incoming": incoming, "outgoing": outgoing}

    @staticmethod
    def approve_friend_request(user_id: int, requester_user_id: int):
        user_id = int(user_id)
        requester_user_id = int(requester_user_id)
        with get_connection() as conn:
            row = IMRepository._get_friendship_row(conn, user_id, requester_user_id)
            if not row or int(row.get("status") or 0) != IMRepository.FRIEND_PENDING:
                return False, "好友申请不存在或已处理"
            if int(row.get("target_user_id") or 0) != user_id or int(row.get("requester_user_id") or 0) != requester_user_id:
                return False, "无权处理该好友申请"
            conn.execute(
                """
                update im_friendships
                set status=?,
                    action_user_id=?,
                    action_at=datetime('now'),
                    update_at=datetime('now')
                where id=?
                """,
                (IMRepository.FRIEND_ACCEPTED, user_id, row["id"]),
            )
        return True, "已同意好友申请"

    @staticmethod
    def reject_friend_request(user_id: int, requester_user_id: int):
        user_id = int(user_id)
        requester_user_id = int(requester_user_id)
        with get_connection() as conn:
            row = IMRepository._get_friendship_row(conn, user_id, requester_user_id)
            if not row or int(row.get("status") or 0) != IMRepository.FRIEND_PENDING:
                return False, "好友申请不存在或已处理"
            if int(row.get("target_user_id") or 0) != user_id or int(row.get("requester_user_id") or 0) != requester_user_id:
                return False, "无权处理该好友申请"
            conn.execute(
                """
                update im_friendships
                set status=?,
                    action_user_id=?,
                    action_at=datetime('now'),
                    update_at=datetime('now')
                where id=?
                """,
                (IMRepository.FRIEND_REJECTED, user_id, row["id"]),
            )
        return True, "已拒绝好友申请"

    @staticmethod
    def remove_friend(user_id: int, friend_user_id: int):
        user_id = int(user_id)
        friend_user_id = int(friend_user_id)
        if user_id == friend_user_id:
            return False, "不能删除自己"
        with get_connection() as conn:
            row = IMRepository._get_friendship_row(conn, user_id, friend_user_id)
            if not row or int(row.get("status") or 0) != IMRepository.FRIEND_ACCEPTED:
                return False, "当前不是好友关系"
            conn.execute(
                """
                update im_friendships
                set status=?,
                    requester_user_id=?,
                    target_user_id=?,
                    action_user_id=?,
                    action_at=datetime('now'),
                    update_at=datetime('now')
                where id=?
                """,
                (IMRepository.FRIEND_DELETED, user_id, friend_user_id, user_id, row["id"]),
            )
            IMRepository._deactivate_private_conversation(conn, user_id, friend_user_id)
        return True, "已删除好友"

    @staticmethod
    def _ensure_private_conversation(conn, user_id: int, other_user_id: int):
        friend_row = IMRepository._get_friendship_row(conn, user_id, other_user_id)
        if not friend_row or int(friend_row.get("status") or 0) != IMRepository.FRIEND_ACCEPTED:
            raise RuntimeError("仅支持与好友发起私聊，请先添加好友")

        private_key = f"user:{min(user_id, other_user_id)}:{max(user_id, other_user_id)}"
        row = conn.execute(
            "select id,status from im_conversations where chat_type=? and private_key=? limit 1",
            (IMRepository.CHAT_PRIVATE, private_key),
        ).fetchone()
        if row:
            conversation_id = int(row["id"])
            if int(row["status"] or 0) != 1:
                conn.execute(
                    "update im_conversations set status=1,update_at=datetime('now') where id=?",
                    (conversation_id,),
                )
            IMRepository._sync_private_conversation_members(conn, conversation_id, user_id, other_user_id)
            return conversation_id

        cursor = conn.execute(
            """
            insert into im_conversations(
                chat_type,name,owner_user_id,private_key,last_message_at,status,create_at,update_at
            ) values(?,?,?,?,datetime('now'),1,datetime('now'),datetime('now'))
            """,
            (IMRepository.CHAT_PRIVATE, "", user_id, private_key),
        )
        conversation_id = cursor.lastrowid
        IMRepository._sync_private_conversation_members(conn, int(conversation_id), user_id, other_user_id)
        return int(conversation_id)

    @staticmethod
    def _ensure_employee_conversation(conn, user_id: int, employee_id: int):
        employee = IMRepository._get_employee_basic(conn, employee_id)
        if not employee or int(employee.get("status") or 0) != 1:
            raise RuntimeError("数字员工不存在或未启用")

        private_key = f"employee:{user_id}:{employee_id}"
        row = conn.execute(
            "select id from im_conversations where chat_type=? and private_key=? limit 1",
            (IMRepository.CHAT_EMPLOYEE, private_key),
        ).fetchone()
        if row:
            return int(row["id"])

        cursor = conn.execute(
            """
            insert into im_conversations(
                chat_type,name,owner_user_id,employee_id,private_key,last_message_at,status,create_at,update_at
            ) values(?,?,?,?,?,datetime('now'),1,datetime('now'),datetime('now'))
            """,
            (IMRepository.CHAT_EMPLOYEE, employee["name"], user_id, employee_id, private_key),
        )
        conversation_id = cursor.lastrowid
        conn.execute(
            """
            insert into im_conversation_members(conversation_id,member_type,user_id,employee_id,role,status,joined_at)
            values(?,?,?,?,?,?,datetime('now'))
            """,
            (conversation_id, IMRepository.MEMBER_USER, user_id, None, "owner", 1),
        )
        conn.execute(
            """
            insert into im_conversation_members(conversation_id,member_type,user_id,employee_id,role,status,joined_at)
            values(?,?,?,?,?,?,datetime('now'))
            """,
            (conversation_id, IMRepository.MEMBER_EMPLOYEE, None, employee_id, "assistant", 1),
        )
        return int(conversation_id)

    @staticmethod
    def open_private_conversation(user_id: int, target_user_id: int):
        with get_connection() as conn:
            conversation_id = IMRepository._ensure_private_conversation(conn, int(user_id), int(target_user_id))
            row = IMRepository._load_conversation_row(conn, conversation_id)
            return IMRepository._hydrate_conversation(conn, row, int(user_id))

    @staticmethod
    def open_employee_conversation(user_id: int, employee_id: int):
        with get_connection() as conn:
            conversation_id = IMRepository._ensure_employee_conversation(conn, int(user_id), int(employee_id))
            row = IMRepository._load_conversation_row(conn, conversation_id)
            return IMRepository._hydrate_conversation(conn, row, int(user_id))

    @staticmethod
    def create_group(user_id: int, name: str, member_user_ids: List[int], member_employee_ids: List[int]):
        name = (name or "").strip()
        if len(name) < 2:
            return False, "群名称至少 2 个字符", None

        user_id = int(user_id)
        member_user_ids = {int(item) for item in member_user_ids if str(item).strip()}
        member_employee_ids = {int(item) for item in member_employee_ids if str(item).strip()}
        member_user_ids.add(user_id)

        friend_ids = {item["id"] for item in IMRepository.list_friends(user_id)}
        invalid_users = [item for item in member_user_ids if item != user_id and item not in friend_ids]
        if invalid_users:
            return False, "群成员必须从好友中选择", None

        with get_connection() as conn:
            cursor = conn.execute(
                """
                insert into im_conversations(
                    chat_type,name,owner_user_id,last_message_at,status,create_at,update_at
                ) values(?,?,?,datetime('now'),1,datetime('now'),datetime('now'))
                """,
                (IMRepository.CHAT_GROUP, name, user_id),
            )
            conversation_id = cursor.lastrowid
            group_cursor = conn.execute(
                """
                insert into im_groups(conversation_id,name,owner_user_id,notice,status,create_at,update_at)
                values(?,?,?,'',1,datetime('now'),datetime('now'))
                """,
                (conversation_id, name, user_id),
            )
            group_id = group_cursor.lastrowid
            conn.execute("update im_conversations set group_id=? where id=?", (group_id, conversation_id))

            for member_id in sorted(member_user_ids):
                conn.execute(
                    """
                    insert into im_conversation_members(conversation_id,member_type,user_id,employee_id,role,status,joined_at)
                    values(?,?,?,?,?,?,datetime('now'))
                    """,
                    (
                        conversation_id,
                        IMRepository.MEMBER_USER,
                        member_id,
                        None,
                        "owner" if member_id == user_id else "member",
                        1,
                    ),
                )
            for employee_id in sorted(member_employee_ids):
                employee = IMRepository._get_employee_basic(conn, employee_id)
                if not employee or int(employee.get("status") or 0) != 1:
                    continue
                conn.execute(
                    """
                    insert into im_conversation_members(conversation_id,member_type,user_id,employee_id,role,status,joined_at)
                    values(?,?,?,?,?,?,datetime('now'))
                    """,
                    (conversation_id, IMRepository.MEMBER_EMPLOYEE, None, employee_id, "assistant", 1),
                )

            row = IMRepository._load_conversation_row(conn, conversation_id)
            return True, "群聊创建成功", IMRepository._hydrate_conversation(conn, row, user_id)

    @staticmethod
    def list_conversations(user_id: int):
        user_id = int(user_id)
        with get_connection() as conn:
            rows = conn.execute(
                """
                select c.id,c.chat_type,c.name,c.owner_user_id,c.group_id,c.employee_id,c.private_key,c.last_message_preview,
                       c.last_sender_name,c.last_message_type,c.last_message_at,c.status,c.create_at,c.update_at
                from im_conversations c
                join im_conversation_members m on m.conversation_id = c.id
                where m.user_id=? and m.member_type=? and m.status=1 and c.status<>-1
                order by coalesce(nullif(c.last_message_at,''), c.update_at) desc, c.id desc
                """,
                (user_id, IMRepository.MEMBER_USER),
            ).fetchall()
            return [IMRepository._hydrate_conversation(conn, dict(row), user_id) for row in rows]

    @staticmethod
    def get_group_members(user_id: int, conversation_id: int):
        with get_connection() as conn:
            if not IMRepository._conversation_member_exists(conn, conversation_id, user_id):
                raise RuntimeError("无权查看该群聊成员")
            conv = IMRepository._load_conversation_row(conn, conversation_id)
            if not conv or conv["chat_type"] != IMRepository.CHAT_GROUP:
                return []
            rows = conn.execute(
                """
                select member_type,user_id,employee_id,role,status,joined_at
                from im_conversation_members
                where conversation_id=? and status=1
                order by id asc
                """,
                (conversation_id,),
            ).fetchall()
            members = []
            for row in rows:
                item = dict(row)
                if item["member_type"] == IMRepository.MEMBER_USER and item.get("user_id"):
                    user_row = IMRepository._get_user_basic(conn, int(item["user_id"]))
                    if user_row:
                        item["name"] = user_row["username"]
                elif item["member_type"] == IMRepository.MEMBER_EMPLOYEE and item.get("employee_id"):
                    employee_row = IMRepository._get_employee_basic(conn, int(item["employee_id"]))
                    if employee_row:
                        item["name"] = employee_row["name"]
                        item["alias"] = employee_row["alias"]
                members.append(item)
            return members

    @staticmethod
    def _serialize_message(conn, row: Dict, chat_type: str):
        item = dict(row)
        item["extra"] = _safe_json_loads(item.get("extra_json"), {})
        file_row = IMRepository._get_file_dict(conn, item.get("file_id"))
        if file_row:
            item["file"] = file_row
            item["extra"].setdefault("file_name", file_row["original_name"])
            item["extra"].setdefault("file_url", "/static/" + file_row["relative_path"].replace("\\", "/"))
            item["extra"].setdefault("file_size", file_row["size_bytes"])
        else:
            item["file"] = None
        if item.get("sender_type") == IMRepository.SENDER_USER and item.get("sender_user_id"):
            user_row = IMRepository._get_user_basic(conn, int(item["sender_user_id"]))
            item["sender_name"] = user_row["username"] if user_row else "用户"
            item["sender_avatar_url"] = user_row.get("avatar_url", "") if user_row else ""
        elif item.get("sender_type") == IMRepository.SENDER_EMPLOYEE and item.get("sender_employee_id"):
            employee_row = IMRepository._get_employee_basic(conn, int(item["sender_employee_id"]))
            item["sender_name"] = employee_row["name"] if employee_row else "数字员工"
            item["sender_avatar_url"] = ""
        else:
            item["sender_name"] = "系统"
            item["sender_avatar_url"] = ""
        item["chat_type"] = chat_type
        return item

    @staticmethod
    def get_conversation_detail(user_id: int, conversation_id: int, limit: int = 200):
        user_id = int(user_id)
        with get_connection() as conn:
            if not IMRepository._conversation_member_exists(conn, conversation_id, user_id):
                raise RuntimeError("会话不存在或无权访问")
            row = IMRepository._load_conversation_row(conn, conversation_id)
            if not row:
                raise RuntimeError("会话不存在")
            messages: List[Dict] = []
            if row["chat_type"] in (IMRepository.CHAT_PRIVATE, IMRepository.CHAT_EMPLOYEE):
                msg_rows = conn.execute(
                    """
                    select id,conversation_id,sender_type,sender_user_id,sender_employee_id,receiver_user_id,receiver_employee_id,
                           content_type,content_text,file_id,extra_json,create_at
                    from im_private_messages
                    where conversation_id=?
                    order by id asc
                    limit ?
                    """,
                    (conversation_id, limit),
                ).fetchall()
                messages = [IMRepository._serialize_message(conn, dict(msg), row["chat_type"]) for msg in msg_rows]
            elif row["chat_type"] == IMRepository.CHAT_GROUP:
                msg_rows = conn.execute(
                    """
                    select id,conversation_id,group_id,sender_type,sender_user_id,sender_employee_id,
                           content_type,content_text,file_id,extra_json,create_at
                    from im_group_messages
                    where conversation_id=?
                    order by id asc
                    limit ?
                    """,
                    (conversation_id, limit),
                ).fetchall()
                messages = [IMRepository._serialize_message(conn, dict(msg), row["chat_type"]) for msg in msg_rows]

            IMRepository._mark_conversation_read(conn, conversation_id, user_id)
            conversation = IMRepository._hydrate_conversation(conn, IMRepository._load_conversation_row(conn, conversation_id), user_id)
            payload = {
                "conversation": conversation,
                "messages": messages,
            }
            if row["chat_type"] == IMRepository.CHAT_GROUP:
                payload["members"] = IMRepository.get_group_members(user_id, conversation_id)
            return payload

    @staticmethod
    def get_stream_state(user_id: int):
        conversations = IMRepository.list_conversations(int(user_id))
        marker_payload = [
            {
                "id": item["id"],
                "last_message_at": item.get("last_message_at", ""),
                "last_sender_name": item.get("last_sender_name", ""),
                "last_message_preview": item.get("last_message_preview", ""),
                "unread_count": int(item.get("unread_count") or 0),
                "group_status": int(item.get("group_status") or 0),
            }
            for item in conversations
        ]
        marker = hashlib.sha256(
            json.dumps(marker_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        return {
            "marker": marker,
            "unread_total": sum(int(item.get("unread_count") or 0) for item in conversations),
            "conversation_count": len(conversations),
        }

    @staticmethod
    def save_file_record(file_hash: str, original_name: str, mime_type: str, size_bytes: int, relative_path: str, upload_user_id: int):
        file_hash = (file_hash or "").strip()
        with get_connection() as conn:
            row = conn.execute(
                "select id from im_files where file_hash=? limit 1",
                (file_hash,),
            ).fetchone()
            if row:
                return int(row["id"])
            storage_name = os.path.basename(relative_path)
            _, ext = os.path.splitext(original_name or storage_name)
            cursor = conn.execute(
                """
                insert into im_files(file_hash,original_name,storage_name,file_ext,mime_type,size_bytes,relative_path,upload_user_id,create_at)
                values(?,?,?,?,?,?,?,?,datetime('now'))
                """,
                (file_hash, original_name, storage_name, ext.lower(), mime_type, int(size_bytes or 0), relative_path, int(upload_user_id)),
            )
            return int(cursor.lastrowid)

    @staticmethod
    def _prepare_message_payload(content_type: str, content_text: str, file_id: Optional[int], extra: Optional[Dict]):
        extra = dict(extra or {})
        content_text = (content_text or "").strip()
        return content_type or IMRepository.CONTENT_TEXT, content_text, int(file_id or 0) or None, extra

    @staticmethod
    def _build_employee_reply_extra(employee: Dict, employee_result: Dict):
        extra = {
            "employee_alias": employee["alias"],
            "prompt_tokens": employee_result.get("prompt_tokens", 0),
            "completion_tokens": employee_result.get("completion_tokens", 0),
            "total_tokens": employee_result.get("total_tokens", 0),
            "response_ms": employee_result.get("response_ms", 0),
        }
        if employee_result.get("error_message"):
            extra["error_message"] = employee_result.get("error_message")
        payload = employee_result.get("payload")
        if payload is not None:
            extra["payload"] = payload
            if isinstance(payload, dict) and ("天气" in employee.get("alias", "") or "天气" in employee.get("name", "")):
                weather_payload = payload.get("data") if isinstance(payload.get("data"), dict) else payload
                if isinstance(weather_payload, dict):
                    extra["weather_card"] = weather_payload
        return extra

    @staticmethod
    async def _async_employee_reply_safe(alias: str, message: str, timeout_seconds: int = 20):
        try:
            return await asyncio.wait_for(DigitalEmployeeRepository.chat_once(message), timeout=float(timeout_seconds))
        except Exception as exc:
            return {
                "content": f"@{alias} 暂时未响应，请稍后重试。",
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "response_ms": 0,
                "error_message": str(exc),
            }

    @staticmethod
    def send_message(
        user_id: int,
        username: str,
        content_type: str,
        content_text: str,
        conversation_id: Optional[int] = None,
        target_user_id: Optional[int] = None,
        target_employee_id: Optional[int] = None,
        file_id: Optional[int] = None,
        extra: Optional[Dict] = None,
    ):
        user_id = int(user_id)
        content_type, content_text, file_id, extra = IMRepository._prepare_message_payload(content_type, content_text, file_id, extra)
        if not content_text and not file_id:
            raise RuntimeError("消息内容不能为空")

        with get_connection() as conn:
            if conversation_id:
                row = IMRepository._load_conversation_row(conn, int(conversation_id))
                if not row:
                    raise RuntimeError("会话不存在")
                if not IMRepository._conversation_member_exists(conn, int(conversation_id), user_id):
                    raise RuntimeError("无权操作该会话")
                conversation_id = int(conversation_id)
            elif target_user_id:
                conversation_id = IMRepository._ensure_private_conversation(conn, user_id, int(target_user_id))
                row = IMRepository._load_conversation_row(conn, conversation_id)
            elif target_employee_id:
                conversation_id = IMRepository._ensure_employee_conversation(conn, user_id, int(target_employee_id))
                row = IMRepository._load_conversation_row(conn, conversation_id)
            else:
                raise RuntimeError("缺少会话目标")

            chat_type = row["chat_type"]
            file_row = IMRepository._get_file_dict(conn, file_id)
            if file_row:
                extra.setdefault("file_name", file_row["original_name"])
                extra.setdefault("file_url", "/static/" + file_row["relative_path"].replace("\\", "/"))
                extra.setdefault("file_size", file_row["size_bytes"])
                if not content_text:
                    content_text = file_row["original_name"]

            if chat_type in (IMRepository.CHAT_PRIVATE, IMRepository.CHAT_EMPLOYEE):
                receiver_user_id = None
                receiver_employee_id = None
                if chat_type == IMRepository.CHAT_PRIVATE:
                    member_row = conn.execute(
                        """
                        select user_id
                        from im_conversation_members
                        where conversation_id=? and member_type=? and user_id<>?
                        limit 1
                        """,
                        (conversation_id, IMRepository.MEMBER_USER, user_id),
                    ).fetchone()
                    receiver_user_id = member_row["user_id"] if member_row else None
                else:
                    receiver_employee_id = row.get("employee_id")

                cursor = conn.execute(
                    """
                    insert into im_private_messages(
                        conversation_id,sender_type,sender_user_id,sender_employee_id,receiver_user_id,receiver_employee_id,
                        content_type,content_text,file_id,extra_json,create_at
                    ) values(?,?,?,?,?,?,?,?,?,?,datetime('now'))
                    """,
                    (
                        conversation_id,
                        IMRepository.SENDER_USER,
                        user_id,
                        None,
                        receiver_user_id,
                        receiver_employee_id,
                        content_type,
                        content_text,
                        file_id,
                        json.dumps(extra, ensure_ascii=False),
                    ),
                )
                message_row = conn.execute(
                    """
                    select id,conversation_id,sender_type,sender_user_id,sender_employee_id,receiver_user_id,receiver_employee_id,
                           content_type,content_text,file_id,extra_json,create_at
                    from im_private_messages
                    where id=?
                    """,
                    (cursor.lastrowid,),
                ).fetchone()
                IMRepository._update_conversation_preview(conn, conversation_id, username, content_type, content_text, extra=extra)
                result = {
                    "conversation": IMRepository._hydrate_conversation(conn, row, user_id),
                    "messages": [IMRepository._serialize_message(conn, dict(message_row), chat_type)],
                }

                if chat_type == IMRepository.CHAT_EMPLOYEE and row.get("employee_id"):
                    employee = IMRepository._get_employee_basic(conn, int(row["employee_id"]))
                    if employee:
                        if content_type == IMRepository.CONTENT_FILE:
                            request_text = f"用户发送了一个文件：{content_text}"
                        elif content_type == IMRepository.CONTENT_EMOJI:
                            request_text = f"用户发送了表情：{content_text}"
                        else:
                            request_text = content_text
                        reply = IMRepository._call_employee_reply(employee["alias"], request_text)
                        reply_extra = {"employee_alias": employee["alias"]}
                        reply_cursor = conn.execute(
                            """
                            insert into im_private_messages(
                                conversation_id,sender_type,sender_user_id,sender_employee_id,receiver_user_id,receiver_employee_id,
                                content_type,content_text,file_id,extra_json,create_at
                            ) values(?,?,?,?,?,?,?,?,?,?,datetime('now'))
                            """,
                            (
                                conversation_id,
                                IMRepository.SENDER_EMPLOYEE,
                                None,
                                employee["id"],
                                user_id,
                                None,
                                IMRepository.CONTENT_TEXT,
                                reply,
                                None,
                                json.dumps(reply_extra, ensure_ascii=False),
                            ),
                        )
                        reply_row = conn.execute(
                            """
                            select id,conversation_id,sender_type,sender_user_id,sender_employee_id,receiver_user_id,receiver_employee_id,
                                   content_type,content_text,file_id,extra_json,create_at
                            from im_private_messages
                            where id=?
                            """,
                            (reply_cursor.lastrowid,),
                        ).fetchone()
                        IMRepository._update_conversation_preview(conn, conversation_id, employee["name"], IMRepository.CONTENT_TEXT, reply, extra=reply_extra)
                        result["messages"].append(IMRepository._serialize_message(conn, dict(reply_row), chat_type))

                IMRepository._mark_conversation_read(conn, conversation_id, user_id)
                result["conversation"] = IMRepository._hydrate_conversation(conn, IMRepository._load_conversation_row(conn, conversation_id), user_id)
                return result

            if chat_type != IMRepository.CHAT_GROUP:
                raise RuntimeError("不支持的会话类型")

            group_row = conn.execute(
                "select id,name,status from im_groups where conversation_id=?",
                (conversation_id,),
            ).fetchone()
            if not group_row or int(group_row["status"] or 0) != 1:
                raise RuntimeError("群聊不存在或已停用")

            cursor = conn.execute(
                """
                insert into im_group_messages(
                    conversation_id,group_id,sender_type,sender_user_id,sender_employee_id,content_type,content_text,file_id,extra_json,create_at
                ) values(?,?,?,?,?,?,?,?,?,datetime('now'))
                """,
                (
                    conversation_id,
                    group_row["id"],
                    IMRepository.SENDER_USER,
                    user_id,
                    None,
                    content_type,
                    content_text,
                    file_id,
                    json.dumps(extra, ensure_ascii=False),
                ),
            )
            message_row = conn.execute(
                """
                select id,conversation_id,group_id,sender_type,sender_user_id,sender_employee_id,content_type,content_text,file_id,extra_json,create_at
                from im_group_messages
                where id=?
                """,
                (cursor.lastrowid,),
            ).fetchone()
            IMRepository._update_conversation_preview(conn, conversation_id, username, content_type, content_text, extra=extra)
            result = {
                "conversation": IMRepository._hydrate_conversation(conn, row, user_id),
                "messages": [IMRepository._serialize_message(conn, dict(message_row), chat_type)],
            }

            employee_reply = IMRepository._handle_group_employee_reply(
                conn=conn,
                user_id=user_id,
                conversation_id=conversation_id,
                group_id=group_row["id"],
                content_text=content_text,
            )
            if employee_reply:
                result["messages"].append(employee_reply)
            result["conversation"] = IMRepository._hydrate_conversation(conn, IMRepository._load_conversation_row(conn, conversation_id), user_id)
            return result

    @staticmethod
    def _call_employee_reply(alias: str, user_text: str):
        return IMRepository._sync_employee_reply(alias, user_text)

    @staticmethod
    def _sync_employee_reply(alias: str, user_text: str):
        import asyncio

        coroutine = DigitalEmployeeRepository.chat_once(f"@{alias} {user_text}".strip())
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # 当前调用链主要在异步 Handler 内，避免在模型层里嵌套事件循环。
            raise RuntimeError("请使用异步聊天接口发送数字员工消息")
        result = asyncio.run(coroutine)
        return result["content"]

    @staticmethod
    def _handle_group_employee_reply(conn, user_id: int, conversation_id: int, group_id: int, content_text: str):
        aliases = []
        for match in IMRepository.EMPLOYEE_MENTION_RE.finditer(content_text or ""):
            aliases.append(match.group(1).strip())
        if not aliases:
            return None

        employee_rows = conn.execute(
            """
            select de.id,de.name,de.alias,de.code
            from im_conversation_members m
            join digital_employees de on de.id = m.employee_id
            where m.conversation_id=? and m.member_type=? and m.status=1 and de.status=1
            order by m.id asc
            """,
            (conversation_id, IMRepository.MEMBER_EMPLOYEE),
        ).fetchall()
        employee_map = {row["alias"]: dict(row) for row in employee_rows}
        selected = None
        for alias in aliases:
            if alias in employee_map:
                selected = employee_map[alias]
                break
        if not selected:
            return None

        try:
            reply_text = IMRepository._sync_employee_reply(selected["alias"], content_text)
        except Exception as exc:
            reply_text = f"数字员工响应失败：{exc}"

        extra = {"employee_alias": selected["alias"]}
        cursor = conn.execute(
            """
            insert into im_group_messages(
                conversation_id,group_id,sender_type,sender_user_id,sender_employee_id,content_type,content_text,file_id,extra_json,create_at
            ) values(?,?,?,?,?,?,?,?,?,datetime('now'))
            """,
            (
                conversation_id,
                group_id,
                IMRepository.SENDER_EMPLOYEE,
                None,
                selected["id"],
                IMRepository.CONTENT_TEXT,
                reply_text,
                None,
                json.dumps(extra, ensure_ascii=False),
            ),
        )
        reply_row = conn.execute(
            """
            select id,conversation_id,group_id,sender_type,sender_user_id,sender_employee_id,content_type,content_text,file_id,extra_json,create_at
            from im_group_messages
            where id=?
            """,
            (cursor.lastrowid,),
        ).fetchone()
        IMRepository._update_conversation_preview(conn, conversation_id, selected["name"], IMRepository.CONTENT_TEXT, reply_text, extra=extra)
        return IMRepository._serialize_message(conn, dict(reply_row), IMRepository.CHAT_GROUP)

    @staticmethod
    def list_group_admin(page: int = 1, page_size: int = 20, keyword: str = ""):
        offset = (page - 1) * page_size
        params: List = []
        where_sql = ""
        if keyword:
            like_value = f"%{keyword}%"
            where_sql = "where g.name like ? or owner.username like ? or coalesce(g.notice,'') like ?"
            params.extend([like_value, like_value, like_value])

        sql = f"""
            select g.id,g.conversation_id,g.name,g.notice,g.status,g.create_at,g.update_at,
                   owner.username as owner_name,
                   (select count(*) from im_conversation_members m where m.conversation_id=g.conversation_id and m.status=1) as member_count,
                   (select count(*) from im_group_messages gm where gm.group_id=g.id) as message_count
            from im_groups g
            left join users owner on owner.id = g.owner_user_id
            {where_sql}
            order by g.id desc
            limit ? offset ?
        """
        count_sql = f"select count(*) as total from im_groups g left join users owner on owner.id = g.owner_user_id {where_sql}"
        with get_connection() as conn:
            rows = conn.execute(sql, tuple(params + [page_size, offset])).fetchall()
            total = conn.execute(count_sql, tuple(params)).fetchone()["total"]
        return {"list": [dict(row) for row in rows], "total": total}

    @staticmethod
    def get_group_admin_detail(group_id: int):
        with get_connection() as conn:
            row = conn.execute(
                """
                select g.id,g.conversation_id,g.name,g.notice,g.status,g.owner_user_id,g.create_at,g.update_at,
                       owner.username as owner_name
                from im_groups g
                left join users owner on owner.id = g.owner_user_id
                where g.id=?
                """,
                (group_id,),
            ).fetchone()
            if not row:
                return None
            data = dict(row)
            data["members"] = IMRepository.get_group_members(data["owner_user_id"], data["conversation_id"])
            return data

    @staticmethod
    def save_group_notice(group_id: int, title: str, content: str, publish_user_id: int):
        title = (title or "").strip()
        content = (content or "").strip()
        if not title or not content:
            return False, "公告标题和内容不能为空"
        with get_connection() as conn:
            group_row = conn.execute("select conversation_id from im_groups where id=?", (group_id,)).fetchone()
            if not group_row:
                return False, "群聊不存在"
            conn.execute(
                "update im_groups set notice=?,update_at=datetime('now') where id=?",
                (content, group_id),
            )
            conn.execute(
                """
                insert into im_announcements(group_id,title,content,status,published_by,create_at,update_at)
                values(?,?,?,?,?,datetime('now'),datetime('now'))
                """,
                (group_id, title, content, 1, publish_user_id),
            )
            extra = {"title": title}
            conn.execute(
                """
                insert into im_group_messages(
                    conversation_id,group_id,sender_type,sender_user_id,sender_employee_id,content_type,content_text,file_id,extra_json,create_at
                ) values(?,?,?,?,?,?,?,?,?,datetime('now'))
                """,
                (group_row["conversation_id"], group_id, IMRepository.SENDER_SYSTEM, publish_user_id, None, IMRepository.CONTENT_NOTICE, content, None, json.dumps(extra, ensure_ascii=False)),
            )
            IMRepository._update_conversation_preview(conn, group_row["conversation_id"], "系统公告", IMRepository.CONTENT_NOTICE, content, extra=extra)
        return True, "群公告已发布"

    @staticmethod
    def update_group_status(group_id: int, status: int):
        with get_connection() as conn:
            row = conn.execute("select conversation_id from im_groups where id=?", (group_id,)).fetchone()
            if not row:
                return False, "群聊不存在"
            conn.execute("update im_groups set status=?,update_at=datetime('now') where id=?", (int(status), group_id))
            conn.execute("update im_conversations set status=?,update_at=datetime('now') where id=?", (int(status), row["conversation_id"]))
        return True, "群状态更新成功"

    @staticmethod
    def list_files(page: int = 1, page_size: int = 20, keyword: str = ""):
        offset = (page - 1) * page_size
        params: List = []
        where_sql = ""
        if keyword:
            like_value = f"%{keyword}%"
            where_sql = "where f.original_name like ? or u.username like ? or f.mime_type like ?"
            params.extend([like_value, like_value, like_value])
        sql = f"""
            select f.id,f.original_name,f.storage_name,f.file_ext,f.mime_type,f.size_bytes,f.relative_path,f.upload_user_id,f.create_at,
                   u.username as upload_username,
                   (
                     coalesce((select count(*) from im_private_messages pm where pm.file_id=f.id),0) +
                     coalesce((select count(*) from im_group_messages gm where gm.file_id=f.id),0)
                   ) as ref_count
            from im_files f
            left join users u on u.id = f.upload_user_id
            {where_sql}
            order by f.id desc
            limit ? offset ?
        """
        count_sql = f"select count(*) as total from im_files f left join users u on u.id = f.upload_user_id {where_sql}"
        with get_connection() as conn:
            rows = conn.execute(sql, tuple(params + [page_size, offset])).fetchall()
            total = conn.execute(count_sql, tuple(params)).fetchone()["total"]
        data = []
        for row in rows:
            item = dict(row)
            item["file_url"] = "/static/" + item["relative_path"].replace("\\", "/")
            data.append(item)
        return {"list": data, "total": total}

    @staticmethod
    def delete_files(file_ids: List[int], project_root: str):
        deleted_count = 0
        with get_connection() as conn:
            for file_id in [int(item) for item in file_ids if str(item).strip()]:
                row = conn.execute("select relative_path from im_files where id=?", (file_id,)).fetchone()
                if not row:
                    continue
                conn.execute("delete from im_files where id=?", (file_id,))
                deleted_count += 1
                file_path = os.path.join(project_root, "app", "static", row["relative_path"])
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except OSError:
                        pass
        return True, f"已删除 {deleted_count} 个文件"

    @staticmethod
    def list_servers(page: int = 1, page_size: int = 20, keyword: str = ""):
        offset = (page - 1) * page_size
        params: List = []
        where_sql = ""
        if keyword:
            like_value = f"%{keyword}%"
            where_sql = "where name like ? or code like ? or base_url like ? or remark like ?"
            params.extend([like_value, like_value, like_value, like_value])
        sql = f"""
            select id,name,code,protocol,base_url,health_url,weight,priority,status,last_health_status,last_error,remark,create_at,update_at
            from im_chat_servers
            {where_sql}
            order by priority asc, weight desc, id desc
            limit ? offset ?
        """
        count_sql = f"select count(*) as total from im_chat_servers {where_sql}"
        with get_connection() as conn:
            rows = conn.execute(sql, tuple(params + [page_size, offset])).fetchall()
            total = conn.execute(count_sql, tuple(params)).fetchone()["total"]
        return {"list": [dict(row) for row in rows], "total": total}

    @staticmethod
    def get_server_detail(server_id: int):
        with get_connection() as conn:
            row = conn.execute(
                """
                select id,name,code,protocol,base_url,health_url,weight,priority,status,last_health_status,last_error,remark,create_at,update_at
                from im_chat_servers
                where id=?
                """,
                (server_id,),
            ).fetchone()
        return dict(row) if row else None

    @staticmethod
    def save_server(data: Dict, server_id: Optional[int] = None):
        name = (data.get("name") or "").strip()
        code = (data.get("code") or "").strip()
        protocol = (data.get("protocol") or "polling").strip()
        base_url = (data.get("base_url") or "").strip()
        health_url = (data.get("health_url") or "").strip()
        weight = int(data.get("weight") or 100)
        priority = int(data.get("priority") or 1)
        status = int(data.get("status") or 1)
        remark = (data.get("remark") or "").strip()
        if not name or not code:
            return False, "服务器名称和编码不能为空"
        with get_connection() as conn:
            duplicate_sql = "select id from im_chat_servers where (name=? or code=?)"
            params = [name, code]
            if server_id:
                duplicate_sql += " and id<>?"
                params.append(int(server_id))
            duplicate = conn.execute(duplicate_sql, tuple(params)).fetchone()
            if duplicate:
                return False, "服务器名称或编码已存在"
            payload = (name, code, protocol, base_url, health_url, weight, priority, status, remark)
            if server_id:
                conn.execute(
                    """
                    update im_chat_servers
                    set name=?,code=?,protocol=?,base_url=?,health_url=?,weight=?,priority=?,status=?,remark=?,update_at=datetime('now')
                    where id=?
                    """,
                    payload + (int(server_id),),
                )
            else:
                conn.execute(
                    """
                    insert into im_chat_servers(
                        name,code,protocol,base_url,health_url,weight,priority,status,last_health_status,last_error,remark,create_at,update_at
                    ) values(?,?,?,?,?,?,?,?, 'unknown','',?,datetime('now'),datetime('now'))
                    """,
                    payload,
                )
        return True, "保存成功"

    @staticmethod
    def delete_server(server_id: int):
        with get_connection() as conn:
            conn.execute("delete from im_chat_servers where id=?", (int(server_id),))
        return True, "删除成功"

    @staticmethod
    def list_tools(page: int = 1, page_size: int = 20, keyword: str = ""):
        offset = (page - 1) * page_size
        params: List = []
        where_sql = ""
        if keyword:
            like_value = f"%{keyword}%"
            where_sql = "where t.name like ? or t.code like ? or t.description like ?"
            params.extend([like_value, like_value, like_value])
        sql = f"""
            select t.id,t.name,t.code,t.tool_type,t.endpoint_id,t.description,t.config_json,t.status,t.create_at,t.update_at,
                   ae.name as endpoint_name,
                   (select count(*) from im_employee_tools et where et.tool_id=t.id) as bind_count
            from im_ai_tools t
            left join api_endpoints ae on ae.id = t.endpoint_id
            {where_sql}
            order by t.id desc
            limit ? offset ?
        """
        count_sql = f"select count(*) as total from im_ai_tools t {where_sql}"
        with get_connection() as conn:
            rows = conn.execute(sql, tuple(params + [page_size, offset])).fetchall()
            total = conn.execute(count_sql, tuple(params)).fetchone()["total"]
        data = []
        for row in rows:
            item = dict(row)
            item["config"] = _safe_json_loads(item.get("config_json"), {})
            data.append(item)
        return {"list": data, "total": total}

    @staticmethod
    def get_tool_detail(tool_id: int):
        with get_connection() as conn:
            row = conn.execute(
                """
                select id,name,code,tool_type,endpoint_id,description,config_json,status,create_at,update_at
                from im_ai_tools
                where id=?
                """,
                (int(tool_id),),
            ).fetchone()
            if not row:
                return None
            data = dict(row)
            bind_rows = conn.execute(
                "select employee_id,role_scope from im_employee_tools where tool_id=? order by id asc",
                (int(tool_id),),
            ).fetchall()
            data["employee_ids"] = [row["employee_id"] for row in bind_rows]
            data["bindings"] = [dict(item) for item in bind_rows]
            return data

    @staticmethod
    def save_tool(data: Dict, tool_id: Optional[int] = None, employee_ids: Optional[List[int]] = None):
        name = (data.get("name") or "").strip()
        code = (data.get("code") or "").strip()
        tool_type = (data.get("tool_type") or "endpoint").strip()
        description = (data.get("description") or "").strip()
        config_json = (data.get("config_json") or "{}").strip() or "{}"
        endpoint_id = data.get("endpoint_id")
        endpoint_id = int(endpoint_id) if str(endpoint_id or "").strip() else None
        status = int(data.get("status") or 1)
        employee_ids = [int(item) for item in (employee_ids or []) if str(item).strip()]
        if not name or not code:
            return False, "工具名称和编码不能为空"
        try:
            json.loads(config_json)
        except json.JSONDecodeError:
            return False, "工具配置 JSON 格式错误"
        with get_connection() as conn:
            duplicate_sql = "select id from im_ai_tools where (name=? or code=?)"
            params = [name, code]
            if tool_id:
                duplicate_sql += " and id<>?"
                params.append(int(tool_id))
            duplicate = conn.execute(duplicate_sql, tuple(params)).fetchone()
            if duplicate:
                return False, "工具名称或编码已存在"
            if endpoint_id:
                endpoint_row = conn.execute("select id from api_endpoints where id=?", (endpoint_id,)).fetchone()
                if not endpoint_row:
                    return False, "绑定接口不存在"
            payload = (name, code, tool_type, endpoint_id, description, config_json, status)
            if tool_id:
                conn.execute(
                    """
                    update im_ai_tools
                    set name=?,code=?,tool_type=?,endpoint_id=?,description=?,config_json=?,status=?,update_at=datetime('now')
                    where id=?
                    """,
                    payload + (int(tool_id),),
                )
                current_tool_id = int(tool_id)
            else:
                cursor = conn.execute(
                    """
                    insert into im_ai_tools(name,code,tool_type,endpoint_id,description,config_json,status,create_at,update_at)
                    values(?,?,?,?,?,?,?,datetime('now'),datetime('now'))
                    """,
                    payload,
                )
                current_tool_id = int(cursor.lastrowid)

            conn.execute("delete from im_employee_tools where tool_id=?", (current_tool_id,))
            for employee_id in employee_ids:
                conn.execute(
                    """
                    insert into im_employee_tools(employee_id,tool_id,role_scope,create_at)
                    values(?,?,?,datetime('now'))
                    """,
                    (employee_id, current_tool_id, "all"),
                )
        return True, "保存成功"

    @staticmethod
    def delete_tool(tool_id: int):
        with get_connection() as conn:
            conn.execute("delete from im_employee_tools where tool_id=?", (int(tool_id),))
            conn.execute("delete from im_ai_tools where id=?", (int(tool_id),))
        return True, "删除成功"

    @staticmethod
    def get_admin_meta():
        return {
            "employees": DigitalEmployeeRepository.get_employee_options(),
            "endpoints": ApiEndpointRepository.get_endpoint_options(),
        }


class IMAsyncService:
    @staticmethod
    async def _deliver_employee_reply_async(
        conversation_id: int,
        trigger_user_id: int,
        employee: Dict,
        request_text: str,
        chat_type: str,
        group_id: Optional[int] = None,
    ):
        employee_result = await IMRepository._async_employee_reply_safe(employee["alias"], request_text)
        reply_text = employee_result["content"]
        reply_extra = IMRepository._build_employee_reply_extra(employee, employee_result)
        with get_connection() as conn:
            row = IMRepository._load_conversation_row(conn, int(conversation_id))
            if not row or int(row.get("status") or 0) != 1:
                return
            if chat_type == IMRepository.CHAT_EMPLOYEE:
                conn.execute(
                    """
                    insert into im_private_messages(
                        conversation_id,sender_type,sender_user_id,sender_employee_id,receiver_user_id,receiver_employee_id,
                        content_type,content_text,file_id,extra_json,create_at
                    ) values(?,?,?,?,?,?,?,?,?,?,datetime('now'))
                    """,
                    (
                        int(conversation_id),
                        IMRepository.SENDER_EMPLOYEE,
                        None,
                        employee["id"],
                        int(trigger_user_id),
                        None,
                        IMRepository.CONTENT_TEXT,
                        reply_text,
                        None,
                        json.dumps(reply_extra, ensure_ascii=False),
                    ),
                )
            elif chat_type == IMRepository.CHAT_GROUP:
                current_group_id = int(group_id or row.get("group_id") or 0)
                if not current_group_id:
                    group_row = conn.execute(
                        "select id,status from im_groups where conversation_id=?",
                        (int(conversation_id),),
                    ).fetchone()
                    if not group_row or int(group_row["status"] or 0) != 1:
                        return
                    current_group_id = int(group_row["id"])
                conn.execute(
                    """
                    insert into im_group_messages(
                        conversation_id,group_id,sender_type,sender_user_id,sender_employee_id,content_type,content_text,file_id,extra_json,create_at
                    ) values(?,?,?,?,?,?,?,?,?,datetime('now'))
                    """,
                    (
                        int(conversation_id),
                        current_group_id,
                        IMRepository.SENDER_EMPLOYEE,
                        None,
                        employee["id"],
                        IMRepository.CONTENT_TEXT,
                        reply_text,
                        None,
                        json.dumps(reply_extra, ensure_ascii=False),
                    ),
                )
            else:
                return
            IMRepository._update_conversation_preview(conn, int(conversation_id), employee["name"], IMRepository.CONTENT_TEXT, reply_text, extra=reply_extra)

    @staticmethod
    async def send_message(
        user_id: int,
        username: str,
        content_type: str,
        content_text: str,
        conversation_id: Optional[int] = None,
        target_user_id: Optional[int] = None,
        target_employee_id: Optional[int] = None,
        file_id: Optional[int] = None,
        extra: Optional[Dict] = None,
    ):
        user_id = int(user_id)
        content_type, content_text, file_id, extra = IMRepository._prepare_message_payload(content_type, content_text, file_id, extra)
        if not content_text and not file_id:
            raise RuntimeError("消息内容不能为空")

        with get_connection() as conn:
            if conversation_id:
                row = IMRepository._load_conversation_row(conn, int(conversation_id))
                if not row:
                    raise RuntimeError("会话不存在")
                if not IMRepository._conversation_member_exists(conn, int(conversation_id), user_id):
                    raise RuntimeError("无权操作该会话")
                conversation_id = int(conversation_id)
            elif target_user_id:
                conversation_id = IMRepository._ensure_private_conversation(conn, user_id, int(target_user_id))
                row = IMRepository._load_conversation_row(conn, conversation_id)
            elif target_employee_id:
                conversation_id = IMRepository._ensure_employee_conversation(conn, user_id, int(target_employee_id))
                row = IMRepository._load_conversation_row(conn, conversation_id)
            else:
                raise RuntimeError("缺少会话目标")

            chat_type = row["chat_type"]
            file_row = IMRepository._get_file_dict(conn, file_id)
            if file_row:
                extra.setdefault("file_name", file_row["original_name"])
                extra.setdefault("file_url", "/static/" + file_row["relative_path"].replace("\\", "/"))
                extra.setdefault("file_size", file_row["size_bytes"])
                if not content_text:
                    content_text = file_row["original_name"]

            if chat_type in (IMRepository.CHAT_PRIVATE, IMRepository.CHAT_EMPLOYEE):
                receiver_user_id = None
                receiver_employee_id = None
                if chat_type == IMRepository.CHAT_PRIVATE:
                    member_row = conn.execute(
                        """
                        select user_id
                        from im_conversation_members
                        where conversation_id=? and member_type=? and user_id<>?
                        limit 1
                        """,
                        (conversation_id, IMRepository.MEMBER_USER, user_id),
                    ).fetchone()
                    receiver_user_id = member_row["user_id"] if member_row else None
                else:
                    receiver_employee_id = row.get("employee_id")

                cursor = conn.execute(
                    """
                    insert into im_private_messages(
                        conversation_id,sender_type,sender_user_id,sender_employee_id,receiver_user_id,receiver_employee_id,
                        content_type,content_text,file_id,extra_json,create_at
                    ) values(?,?,?,?,?,?,?,?,?,?,datetime('now'))
                    """,
                    (
                        conversation_id,
                        IMRepository.SENDER_USER,
                        user_id,
                        None,
                        receiver_user_id,
                        receiver_employee_id,
                        content_type,
                        content_text,
                        file_id,
                        json.dumps(extra, ensure_ascii=False),
                    ),
                )
                message_row = conn.execute(
                    """
                    select id,conversation_id,sender_type,sender_user_id,sender_employee_id,receiver_user_id,receiver_employee_id,
                           content_type,content_text,file_id,extra_json,create_at
                    from im_private_messages
                    where id=?
                    """,
                    (cursor.lastrowid,),
                ).fetchone()
                IMRepository._update_conversation_preview(conn, conversation_id, username, content_type, content_text, extra=extra)
                result = {
                    "conversation": IMRepository._hydrate_conversation(conn, row, user_id),
                    "messages": [IMRepository._serialize_message(conn, dict(message_row), chat_type)],
                }

                if chat_type == IMRepository.CHAT_EMPLOYEE and row.get("employee_id"):
                    employee = IMRepository._get_employee_basic(conn, int(row["employee_id"]))
                    if employee:
                        if content_type == IMRepository.CONTENT_FILE:
                            request_text = f"用户发送了一个文件：{content_text}"
                        elif content_type == IMRepository.CONTENT_EMOJI:
                            request_text = f"用户发送了表情：{content_text}"
                        else:
                            request_text = content_text
                        asyncio.create_task(
                            IMAsyncService._deliver_employee_reply_async(
                                conversation_id=conversation_id,
                                trigger_user_id=user_id,
                                employee=employee,
                                request_text=f"@{employee['alias']} {request_text}".strip(),
                                chat_type=chat_type,
                            )
                        )
                        result["employee_pending"] = True
                        result["pending_employee_alias"] = employee["alias"]

                result["conversation"] = IMRepository._hydrate_conversation(conn, IMRepository._load_conversation_row(conn, conversation_id), user_id)
                return result

            if chat_type != IMRepository.CHAT_GROUP:
                raise RuntimeError("不支持的会话类型")

            group_row = conn.execute(
                "select id,name,status from im_groups where conversation_id=?",
                (conversation_id,),
            ).fetchone()
            if not group_row or int(group_row["status"] or 0) != 1:
                raise RuntimeError("群聊不存在或已停用")

            cursor = conn.execute(
                """
                insert into im_group_messages(
                    conversation_id,group_id,sender_type,sender_user_id,sender_employee_id,content_type,content_text,file_id,extra_json,create_at
                ) values(?,?,?,?,?,?,?,?,?,datetime('now'))
                """,
                (
                    conversation_id,
                    group_row["id"],
                    IMRepository.SENDER_USER,
                    user_id,
                    None,
                    content_type,
                    content_text,
                    file_id,
                    json.dumps(extra, ensure_ascii=False),
                ),
            )
            message_row = conn.execute(
                """
                select id,conversation_id,group_id,sender_type,sender_user_id,sender_employee_id,content_type,content_text,file_id,extra_json,create_at
                from im_group_messages
                where id=?
                """,
                (cursor.lastrowid,),
            ).fetchone()
            IMRepository._update_conversation_preview(conn, conversation_id, username, content_type, content_text, extra=extra)
            result = {
                "conversation": IMRepository._hydrate_conversation(conn, row, user_id),
                "messages": [IMRepository._serialize_message(conn, dict(message_row), chat_type)],
            }

            employee_rows = conn.execute(
                """
                select de.id,de.name,de.alias
                from im_conversation_members m
                join digital_employees de on de.id = m.employee_id
                where m.conversation_id=? and m.member_type=? and m.status=1 and de.status=1
                order by m.id asc
                """,
                (conversation_id, IMRepository.MEMBER_EMPLOYEE),
            ).fetchall()
            alias_map = {row["alias"]: dict(row) for row in employee_rows}
            matched_alias = None
            for match in IMRepository.EMPLOYEE_MENTION_RE.finditer(content_text or ""):
                alias = match.group(1).strip()
                if alias in alias_map:
                    matched_alias = alias
                    break
            if matched_alias:
                employee = alias_map[matched_alias]
                asyncio.create_task(
                    IMAsyncService._deliver_employee_reply_async(
                        conversation_id=conversation_id,
                        trigger_user_id=user_id,
                        employee=employee,
                        request_text=(content_text or "").strip(),
                        chat_type=chat_type,
                        group_id=group_row["id"],
                    )
                )
                result["employee_pending"] = True
                result["pending_employee_alias"] = employee["alias"]

            IMRepository._mark_conversation_read(conn, conversation_id, user_id)
            result["conversation"] = IMRepository._hydrate_conversation(conn, IMRepository._load_conversation_row(conn, conversation_id), user_id)
            return result

    @staticmethod
    def get_bootstrap(user_id: int, username: str):
        conversations = IMRepository.list_conversations(user_id)
        user_row = UserRepository.get_user_by_username(username)
        avatar_url = ""
        role_name = ""
        if user_row:
            avatar_url = UserRepository.build_avatar_url(user_row["avatar_path"])
            role_name = user_row["role"] or ""
        return {
            "user": {"id": user_id, "username": username, "avatar_url": avatar_url, "role": role_name},
            "friends": IMRepository.list_friends(user_id),
            "friend_requests": IMRepository.list_friend_requests(user_id),
            "employees": DigitalEmployeeRepository.get_employee_options(),
            "conversations": conversations,
            "unread_total": sum(int(item.get("unread_count") or 0) for item in conversations),
            "servers": IMRepository.list_servers(page=1, page_size=20)["list"],
        }
