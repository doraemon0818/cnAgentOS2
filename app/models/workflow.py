import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from app.models.db import get_connection


class Workflow:
    @staticmethod
    def init_table():
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS workflows (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                workflow_type TEXT NOT NULL,
                nodes_config TEXT NOT NULL,
                trigger_type TEXT NOT NULL,
                trigger_config TEXT,
                enabled INTEGER DEFAULT 1,
                run_count INTEGER DEFAULT 0,
                success_count INTEGER DEFAULT 0,
                fail_count INTEGER DEFAULT 0,
                last_run_time TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        conn.commit()
        conn.close()
    
    @staticmethod
    def create_workflow(name, workflow_type, nodes_config, trigger_type='manual', trigger_config=None, description='', enabled=1):
        conn = get_connection()
        cursor = conn.cursor()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute(
            'INSERT INTO workflows (name, description, workflow_type, nodes_config, trigger_type, trigger_config, enabled, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (name, description, workflow_type, json.dumps(nodes_config, ensure_ascii=False), trigger_type, json.dumps(trigger_config or {}, ensure_ascii=False), enabled, now, now)
        )
        workflow_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return workflow_id
    
    @staticmethod
    def update_workflow(workflow_id, **kwargs):
        conn = get_connection()
        cursor = conn.cursor()
        fields = []
        values = []
        for key, value in kwargs.items():
            if key in ('nodes_config', 'trigger_config') and isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False)
            fields.append(f"{key} = ?")
            values.append(value)
        if 'updated_at' not in kwargs:
            fields.append("updated_at = ?")
            values.append(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        values.append(workflow_id)
        sql = f"UPDATE workflows SET {', '.join(fields)} WHERE id = ?"
        cursor.execute(sql, values)
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success
    
    @staticmethod
    def delete_workflow(workflow_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM workflows WHERE id = ?", (workflow_id,))
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success
    
    @staticmethod
    def get_workflow(workflow_id):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            wf = dict(row)
            wf['nodes_config'] = json.loads(wf['nodes_config'])
            wf['trigger_config'] = json.loads(wf['trigger_config'])
            return wf
        return None
    
    @staticmethod
    def get_all_workflows():
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM workflows ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()
        workflows = []
        for row in rows:
            wf = dict(row)
            wf['nodes_config'] = json.loads(wf['nodes_config'])
            wf['trigger_config'] = json.loads(wf['trigger_config'])
            workflows.append(wf)
        return workflows
    
    @staticmethod
    def get_enabled_workflows():
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM workflows WHERE enabled = 1 ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()
        workflows = []
        for row in rows:
            wf = dict(row)
            wf['nodes_config'] = json.loads(wf['nodes_config'])
            wf['trigger_config'] = json.loads(wf['trigger_config'])
            workflows.append(wf)
        return workflows
    
    @staticmethod
    def update_run_stats(workflow_id, success):
        conn = get_connection()
        cursor = conn.cursor()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if success:
            cursor.execute(
                'UPDATE workflows SET last_run_time = ?, run_count = run_count + 1, success_count = success_count + 1, updated_at = ? WHERE id = ?',
                (now, now, workflow_id)
            )
        else:
            cursor.execute(
                'UPDATE workflows SET last_run_time = ?, run_count = run_count + 1, fail_count = fail_count + 1, updated_at = ? WHERE id = ?',
                (now, now, workflow_id)
            )
        conn.commit()
        conn.close()


class WorkflowLog:
    @staticmethod
    def init_table():
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS workflow_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow_id INTEGER NOT NULL,
                workflow_name TEXT NOT NULL,
                workflow_type TEXT NOT NULL,
                status TEXT NOT NULL,
                message TEXT,
                node_results TEXT,
                start_time TEXT NOT NULL,
                end_time TEXT,
                duration_seconds REAL,
                created_at TEXT NOT NULL
            )
        ''')
        conn.commit()
        conn.close()
    
    @staticmethod
    def create_log(workflow_id, workflow_name, workflow_type, status, message="", node_results=None, start_time=None, end_time=None, duration_seconds=0):
        conn = get_connection()
        cursor = conn.cursor()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute(
            'INSERT INTO workflow_logs (workflow_id, workflow_name, workflow_type, status, message, node_results, start_time, end_time, duration_seconds, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (workflow_id, workflow_name, workflow_type, status, message, json.dumps(node_results or [], ensure_ascii=False), start_time or now, end_time or now, duration_seconds, now)
        )
        log_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return log_id
    
    @staticmethod
    def get_logs(workflow_id=None, limit=100):
        conn = get_connection()
        cursor = conn.cursor()
        if workflow_id:
            cursor.execute('SELECT * FROM workflow_logs WHERE workflow_id = ? ORDER BY created_at DESC LIMIT ?', (workflow_id, limit))
        else:
            cursor.execute('SELECT * FROM workflow_logs ORDER BY created_at DESC LIMIT ?', (limit,))
        rows = cursor.fetchall()
        conn.close()
        logs = []
        for row in rows:
            log = dict(row)
            log['node_results'] = json.loads(log['node_results']) if log['node_results'] else []
            logs.append(log)
        return logs
    
    @staticmethod
    def get_logs_by_date(date_str):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM workflow_logs WHERE date(created_at) = ? ORDER BY created_at DESC', (date_str,))
        rows = cursor.fetchall()
        conn.close()
        logs = []
        for row in rows:
            log = dict(row)
            log['node_results'] = json.loads(log['node_results']) if log['node_results'] else []
            logs.append(log)
        return logs
    
    @staticmethod
    def get_recent_logs(days=7):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM workflow_logs WHERE created_at >= datetime(\'now\', ?) ORDER BY created_at DESC', (f'-{days} days',))
        rows = cursor.fetchall()
        conn.close()
        logs = []
        for row in rows:
            log = dict(row)
            log['node_results'] = json.loads(log['node_results']) if log['node_results'] else []
            logs.append(log)
        return logs


class GestureRecord:
    @staticmethod
    def init_table():
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS gesture_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                gesture_type TEXT NOT NULL,
                action TEXT NOT NULL,
                user_id INTEGER,
                created_at TEXT NOT NULL
            )
        ''')
        conn.commit()
        conn.close()
    
    @staticmethod
    def record_gesture(gesture_type, action, user_id=None):
        conn = get_connection()
        cursor = conn.cursor()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute(
            'INSERT INTO gesture_records (gesture_type, action, user_id, created_at) VALUES (?, ?, ?, ?)',
            (gesture_type, action, user_id, now)
        )
        record_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return record_id
