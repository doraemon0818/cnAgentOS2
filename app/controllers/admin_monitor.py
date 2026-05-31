"""
监控仪表盘控制器
提供系统监控、任务统计、告警管理功能
"""
import json
import tornado.web
from datetime import datetime, timedelta

from app.controllers.admin import AdminBaseHandler
from app.models.scheduler import ScheduledTask, TaskLog
from app.models.workflow import Workflow, WorkflowLog
from app.models.report_generator import ReportGenerator


class AdminMonitorDashboardHandler(AdminBaseHandler):
    """监控仪表盘页面"""
    
    def _write_json(self, data):
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(data, ensure_ascii=False))
    
    @tornado.web.authenticated
    def get(self):
        self.render(
            "admin/monitor/dashboard.html",
            title="监控仪表盘"
        )


class AdminMonitorStatsHandler(AdminBaseHandler):
    """监控统计 API"""
    
    def _write_json(self, data):
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(data, ensure_ascii=False))
    
    @tornado.web.authenticated
    def get(self):
        action = self.get_argument("action", "")
        
        if action == "overview":
            # 获取总体统计
            tasks = ScheduledTask.get_all_tasks()
            workflows = Workflow.get_all_workflows()
            
            # 任务统计
            total_tasks = len(tasks)
            enabled_tasks = sum(1 for t in tasks if t['enabled'])
            total_task_runs = sum(t['run_count'] for t in tasks)
            task_success_count = sum(t['success_count'] for t in tasks)
            task_success_rate = round(task_success_count / total_task_runs * 100, 2) if total_task_runs > 0 else 0
            
            # 工作流统计
            total_workflows = len(workflows)
            enabled_workflows = sum(1 for w in workflows if w['enabled'])
            total_wf_runs = sum(w['run_count'] for w in workflows)
            wf_success_count = sum(w['success_count'] for w in workflows)
            wf_success_rate = round(wf_success_count / total_wf_runs * 100, 2) if total_wf_runs > 0 else 0
            
            # 今日执行
            today = datetime.now().strftime('%Y-%m-%d')
            today_task_logs = TaskLog.get_logs_by_date(today)
            today_wf_logs = WorkflowLog.get_logs_by_date(today)
            
            # 获取项目实际数据统计
            from app.models.db import get_connection
            conn = get_connection()
            
            # 瞭望数据
            surveillance_total = conn.execute('select count(*) as cnt from surveillance_records').fetchone()['cnt']
            surveillance_sources = conn.execute('select count(*) as cnt from surveillance_sources').fetchone()['cnt']
            surveillance_deep = conn.execute('select count(*) as cnt from surveillance_deep_tasks').fetchone()['cnt']
            
            # 关键词分布
            keyword_rows = conn.execute('select keyword, count(*) as cnt from surveillance_records group by keyword order by cnt desc limit 5').fetchall()
            keyword_stats = [{'keyword': r['keyword'], 'count': r['cnt']} for r in keyword_rows]
            
            # API 接口
            api_total = conn.execute('select count(*) as cnt from api_endpoints').fetchone()['cnt']
            api_enabled = conn.execute('select count(*) as cnt from api_endpoints where status = 1').fetchone()['cnt']
            
            # 数字员工
            employee_total = conn.execute('select count(*) as cnt from digital_employees').fetchone()['cnt']
            employee_enabled = conn.execute('select count(*) as cnt from digital_employees where status = 1').fetchone()['cnt']
            
            # 数字员工列表
            employee_rows = conn.execute('select id, name, category, status from digital_employees').fetchall()
            employee_list = [{'id': r['id'], 'name': r['name'], 'category': r['category'], 'status': r['status']} for r in employee_rows]
            
            # IM 数据
            im_servers = conn.execute('select count(*) as cnt from im_chat_servers').fetchone()['cnt']
            im_tools = conn.execute('select count(*) as cnt from im_ai_tools').fetchone()['cnt']
            im_conversations = conn.execute('select count(*) as cnt from im_conversations').fetchone()['cnt']
            im_messages = conn.execute('select count(*) as cnt from im_private_messages').fetchone()['cnt'] + conn.execute('select count(*) as cnt from im_group_messages').fetchone()['cnt']
            
            # 舆情分析
            opinion_total = conn.execute('select count(*) as cnt from public_opinion_analysis').fetchone()['cnt']
            
            # 用户聊天
            chat_sessions = conn.execute('select count(*) as cnt from user_chat_sessions').fetchone()['cnt']
            chat_messages = conn.execute('select count(*) as cnt from user_chat_messages').fetchone()['cnt']
            
            # 报表
            reports = ReportGenerator.get_report_list()
            
            conn.close()
            
            self._write_json({
                "code": 0,
                "msg": "ok",
                "data": {
                    "tasks": {
                        "total": total_tasks,
                        "enabled": enabled_tasks,
                        "total_runs": total_task_runs,
                        "success_rate": task_success_rate,
                        "today_runs": len(today_task_logs)
                    },
                    "workflows": {
                        "total": total_workflows,
                        "enabled": enabled_workflows,
                        "total_runs": total_wf_runs,
                        "success_rate": wf_success_rate,
                        "today_runs": len(today_wf_logs)
                    },
                    "surveillance": {
                        "total_records": surveillance_total,
                        "sources": surveillance_sources,
                        "deep_tasks": surveillance_deep,
                        "keywords": keyword_stats
                    },
                    "api": {
                        "total": api_total,
                        "enabled": api_enabled
                    },
                    "employees": {
                        "total": employee_total,
                        "enabled": employee_enabled,
                        "list": employee_list
                    },
                    "im": {
                        "servers": im_servers,
                        "tools": im_tools,
                        "conversations": im_conversations,
                        "messages": im_messages
                    },
                    "opinion": {
                        "total": opinion_total
                    },
                    "chat": {
                        "sessions": chat_sessions,
                        "messages": chat_messages
                    },
                    "reports": {
                        "total": len(reports)
                    }
                }
            })
        
        elif action == "recent_tasks":
            # 获取最近执行的任务
            logs = TaskLog.get_all_logs(10)
            self._write_json({
                "code": 0,
                "msg": "ok",
                "data": {"logs": logs}
            })
        
        elif action == "recent_workflows":
            # 获取最近执行的工作流
            logs = WorkflowLog.get_logs(None, 10)
            self._write_json({
                "code": 0,
                "msg": "ok",
                "data": {"logs": logs}
            })
        
        elif action == "reports":
            # 获取报表列表
            reports = ReportGenerator.get_report_list()
            self._write_json({
                "code": 0,
                "msg": "ok",
                "data": {"reports": reports}
            })
        
        elif action == "alerts":
            # 获取告警信息
            alerts = self._get_alerts()
            self._write_json({
                "code": 0,
                "msg": "ok",
                "data": {"alerts": alerts}
            })
        
        else:
            self._write_json({"code": 1, "msg": "未知操作"})
    
    def _get_alerts(self):
        """获取告警信息"""
        alerts = []
        
        # 检查失败的任务
        tasks = ScheduledTask.get_all_tasks()
        for task in tasks:
            if task['fail_count'] > 0:
                fail_rate = task['fail_count'] / (task['run_count'] + 1) * 100
                if fail_rate > 30:
                    alerts.append({
                        "id": f"task_{task['id']}",
                        "type": "warning",
                        "title": f"任务高失败率",
                        "message": f"任务 '{task['name']}' 失败率 {round(fail_rate, 1)}%",
                        "time": task['last_run_time'] or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    })
        
        # 检查长时间未执行的任务
        now = datetime.now()
        for task in tasks:
            if task['enabled'] and task['last_run_time']:
                last_run = datetime.strptime(task['last_run_time'], '%Y-%m-%d %H:%M:%S')
                if (now - last_run).days > 7:
                    alerts.append({
                        "id": f"task_stale_{task['id']}",
                        "type": "info",
                        "title": "任务长时间未执行",
                        "message": f"任务 '{task['name']}' 最近执行: {task['last_run_time']}",
                        "time": task['last_run_time']
                    })
        
        # 检查工作流失败
        workflows = Workflow.get_all_workflows()
        for wf in workflows:
            if wf['fail_count'] > 0:
                fail_rate = wf['fail_count'] / (wf['run_count'] + 1) * 100
                if fail_rate > 30:
                    alerts.append({
                        "id": f"wf_{wf['id']}",
                        "type": "error",
                        "title": f"工作流高失败率",
                        "message": f"工作流 '{wf['name']}' 失败率 {round(fail_rate, 1)}%",
                        "time": wf['last_run_time'] or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    })
        
        return alerts


class AdminReportDownloadHandler(AdminBaseHandler):
    """报表下载"""
    
    @tornado.web.authenticated
    def get(self):
        try:
            filename = self.get_argument("filename", "")
            if not filename:
                self.set_status(400)
                self.write("文件名不能为空")
                return
            
            import os
            from urllib.parse import quote
            from app.models.report_generator import ReportGenerator
            
            filepath = ReportGenerator.get_report_path(filename)
            
            if not os.path.exists(filepath):
                self.set_status(404)
                self.write("文件不存在")
                return
            
            # 设置响应头
            if filename.endswith('.pdf'):
                content_type = 'application/pdf'
            elif filename.endswith('.xlsx'):
                content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            else:
                content_type = 'application/octet-stream'
            
            # 对文件名进行URL编码以支持中文
            encoded_filename = quote(filename.encode('utf-8'))
            
            self.set_header('Content-Type', content_type)
            self.set_header('Content-Disposition', f'attachment; filename*=UTF-8\'\'{encoded_filename}')
            self.set_header('Content-Length', os.path.getsize(filepath))
            
            # 读取文件内容并发送
            with open(filepath, 'rb') as f:
                self.write(f.read())
            self.finish()
        except Exception as e:
            self.set_status(500)
            self.write(f"下载失败: {str(e)}")


class AdminReportDeleteHandler(AdminBaseHandler):
    """报表删除"""
    
    def _write_json(self, data):
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(data, ensure_ascii=False))
    
    @tornado.web.authenticated
    def post(self):
        filename = self.get_body_argument("filename", "")
        if not filename:
            self._write_json({"code": 1, "msg": "文件名不能为空"})
            return
        
        import os
        from app.models.report_generator import ReportGenerator
        
        filepath = ReportGenerator.get_report_path(filename)
        
        if not os.path.exists(filepath):
            self._write_json({"code": 1, "msg": "文件不存在"})
            return
        
        try:
            os.remove(filepath)
            self._write_json({"code": 0, "msg": "删除成功"})
        except Exception as e:
            self._write_json({"code": 1, "msg": f"删除失败：{str(e)}"})
