import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from app.models.db import get_connection


class ScheduledTask:
    @staticmethod
    def init_table():
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scheduled_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                task_type TEXT NOT NULL,
                cron_expression TEXT NOT NULL,
                config TEXT NOT NULL,
                enabled INTEGER DEFAULT 1,
                last_run_time TEXT,
                next_run_time TEXT,
                run_count INTEGER DEFAULT 0,
                success_count INTEGER DEFAULT 0,
                fail_count INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        conn.commit()
        conn.close()
    
    @staticmethod
    def create_task(name, task_type, cron_expression, config, enabled=1):
        conn = get_connection()
        cursor = conn.cursor()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute(
            'INSERT INTO scheduled_tasks (name, task_type, cron_expression, config, enabled, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (name, task_type, cron_expression, json.dumps(config, ensure_ascii=False), enabled, now, now)
        )
        task_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return task_id
    
    @staticmethod
    def update_task(task_id, **kwargs):
        conn = get_connection()
        cursor = conn.cursor()
        fields = []
        values = []
        for key, value in kwargs.items():
            if key == 'config' and isinstance(value, dict):
                value = json.dumps(value, ensure_ascii=False)
            fields.append(f"{key} = ?")
            values.append(value)
        if 'updated_at' not in kwargs:
            fields.append("updated_at = ?")
            values.append(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        values.append(task_id)
        sql = f"UPDATE scheduled_tasks SET {', '.join(fields)} WHERE id = ?"
        cursor.execute(sql, values)
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success
    
    @staticmethod
    def delete_task(task_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM scheduled_tasks WHERE id = ?", (task_id,))
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success
    
    @staticmethod
    def get_task(task_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM scheduled_tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            task = dict(row)
            task['config'] = json.loads(task['config'])
            return task
        return None
    
    @staticmethod
    def get_all_tasks():
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM scheduled_tasks ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()
        tasks = []
        for row in rows:
            task = dict(row)
            task['config'] = json.loads(task['config'])
            tasks.append(task)
        return tasks
    
    @staticmethod
    def get_enabled_tasks():
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM scheduled_tasks WHERE enabled = 1 ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()
        tasks = []
        for row in rows:
            task = dict(row)
            task['config'] = json.loads(task['config'])
            tasks.append(task)
        return tasks
    
    @staticmethod
    def update_run_stats(task_id, success, next_run_time=None):
        conn = get_connection()
        cursor = conn.cursor()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if success:
            cursor.execute(
                'UPDATE scheduled_tasks SET last_run_time = ?, run_count = run_count + 1, success_count = success_count + 1, updated_at = ? WHERE id = ?',
                (now, now, task_id)
            )
        else:
            cursor.execute(
                'UPDATE scheduled_tasks SET last_run_time = ?, run_count = run_count + 1, fail_count = fail_count + 1, updated_at = ? WHERE id = ?',
                (now, now, task_id)
            )
        if next_run_time:
            cursor.execute('UPDATE scheduled_tasks SET next_run_time = ? WHERE id = ?', (next_run_time, task_id))
        conn.commit()
        conn.close()


class TaskLog:
    @staticmethod
    def init_table():
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS task_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                task_name TEXT NOT NULL,
                task_type TEXT NOT NULL,
                status TEXT NOT NULL,
                message TEXT,
                start_time TEXT NOT NULL,
                end_time TEXT,
                duration_seconds REAL,
                data_count INTEGER DEFAULT 0,
                extra_data TEXT,
                created_at TEXT NOT NULL
            )
        ''')
        conn.commit()
        conn.close()
    
    @staticmethod
    def create_log(task_id, task_name, task_type, status, message="", start_time=None, end_time=None, duration_seconds=0, data_count=0, extra_data=None):
        conn = get_connection()
        cursor = conn.cursor()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        try:
            # 尝试使用新的表结构（包含 extra_data 列）
            cursor.execute(
                'INSERT INTO task_logs (task_id, task_name, task_type, status, message, start_time, end_time, duration_seconds, data_count, extra_data, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (task_id, task_name, task_type, status, message, start_time or now, end_time or now, duration_seconds, data_count, extra_data, now)
            )
        except sqlite3.OperationalError:
            # 如果表结构不包含 extra_data 列，使用旧的插入语句
            cursor.execute(
                'INSERT INTO task_logs (task_id, task_name, task_type, status, message, start_time, end_time, duration_seconds, data_count, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (task_id, task_name, task_type, status, message, start_time or now, end_time or now, duration_seconds, data_count, now)
            )
        log_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return log_id
    
    @staticmethod
    def get_logs(task_id=None, limit=100):
        conn = get_connection()
        cursor = conn.cursor()
        if task_id:
            cursor.execute('SELECT * FROM task_logs WHERE task_id = ? ORDER BY created_at DESC LIMIT ?', (task_id, limit))
        else:
            cursor.execute('SELECT * FROM task_logs ORDER BY created_at DESC LIMIT ?', (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    @staticmethod
    def get_recent_logs(days=7):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM task_logs WHERE created_at >= datetime(\'now\', ?) ORDER BY created_at DESC', (f'-{days} days',))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    @staticmethod
    def get_logs_by_date(date_str):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM task_logs WHERE date(created_at) = ? ORDER BY created_at DESC', (date_str,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    @staticmethod
    def get_all_logs(limit=10):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM task_logs ORDER BY created_at DESC LIMIT ?', (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
