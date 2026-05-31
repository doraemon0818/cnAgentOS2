import json
import tornado.web
from datetime import datetime
from typing import Dict, Any

from app.controllers.admin import AdminBaseHandler
from app.models.scheduler import ScheduledTask, TaskLog
from app.models.scheduler_engine import get_scheduler


class AdminSchedulerListHandler(AdminBaseHandler):
    """定时任务列表页面"""
    
    @tornado.web.authenticated
    def get(self):
        self.render(
            "admin/scheduler/list.html",
            title="定时任务管理"
        )


class AdminSchedulerApiHandler(AdminBaseHandler):
    """定时任务 API 接口"""
    
    def _write_json(self, data):
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(data, ensure_ascii=False))
    
    @tornado.web.authenticated
    def get(self):
        """获取任务列表"""
        action = self.get_argument("action", "")
        
        if action == "list":
            tasks = ScheduledTask.get_all_tasks()
            self._write_json({
                "code": 0,
                "msg": "ok",
                "data": {
                    "tasks": tasks,
                    "count": len(tasks)
                }
            })
        
        elif action == "info":
            task_id = int(self.get_argument("task_id", 0))
            if not task_id:
                self._write_json({"code": 1, "msg": "任务 ID 不能为空"})
                return
            
            task = ScheduledTask.get_task(task_id)
            if not task:
                self._write_json({"code": 1, "msg": "任务不存在"})
                return
            
            self._write_json({
                "code": 0,
                "msg": "ok",
                "data": task
            })
        
        elif action == "logs":
            task_id = int(self.get_argument("task_id", 0))
            limit = int(self.get_argument("limit", 100))
            logs = TaskLog.get_logs(task_id if task_id else None, limit)
            self._write_json({
                "code": 0,
                "msg": "ok",
                "data": {
                    "logs": logs,
                    "count": len(logs)
                }
            })
        
        elif action == "jobs":
            scheduler = get_scheduler()
            jobs = scheduler.get_all_jobs()
            self._write_json({
                "code": 0,
                "msg": "ok",
                "data": {
                    "jobs": jobs,
                    "count": len(jobs)
                }
            })
        
        else:
            self._write_json({"code": 1, "msg": "未知操作"})
    
    @tornado.web.authenticated
    def post(self):
        """创建或更新任务"""
        action = self.get_body_argument("action", "")
        
        if action == "create":
            name = self.get_body_argument("name", "").strip()
            task_type = self.get_body_argument("task_type", "").strip()
            cron_expression = self.get_body_argument("cron_expression", "").strip()
            config_json = self.get_body_argument("config", "{}")
            enabled = int(self.get_body_argument("enabled", 1))
            
            if not name:
                self._write_json({"code": 1, "msg": "任务名称不能为空"})
                return
            
            if not task_type:
                self._write_json({"code": 1, "msg": "任务类型不能为空"})
                return
            
            if not cron_expression:
                self._write_json({"code": 1, "msg": "Cron 表达式不能为空"})
                return
            
            try:
                config = json.loads(config_json)
            except:
                self._write_json({"code": 1, "msg": "配置 JSON 格式错误"})
                return
            
            # 创建任务
            task_id = ScheduledTask.create_task(
                name=name,
                task_type=task_type,
                cron_expression=cron_expression,
                config=config,
                enabled=enabled
            )
            
            # 添加到调度器
            if enabled:
                task = ScheduledTask.get_task(task_id)
                if task:
                    get_scheduler().add_task(task)
            
            self._write_json({
                "code": 0,
                "msg": "任务创建成功",
                "data": {"task_id": task_id}
            })
        
        elif action == "update":
            task_id = int(self.get_body_argument("task_id", 0))
            if not task_id:
                self._write_json({"code": 1, "msg": "任务 ID 不能为空"})
                return
            
            name = self.get_body_argument("name", "").strip()
            task_type = self.get_body_argument("task_type", "").strip()
            cron_expression = self.get_body_argument("cron_expression", "").strip()
            config_json = self.get_body_argument("config", "{}")
            enabled = int(self.get_body_argument("enabled", 1))
            
            if not name:
                self._write_json({"code": 1, "msg": "任务名称不能为空"})
                return
            
            try:
                config = json.loads(config_json)
            except:
                self._write_json({"code": 1, "msg": "配置 JSON 格式错误"})
                return
            
            # 更新任务
            ScheduledTask.update_task(
                task_id=task_id,
                name=name,
                task_type=task_type,
                cron_expression=cron_expression,
                config=config,
                enabled=enabled
            )
            
            # 更新调度器
            task = ScheduledTask.get_task(task_id)
            if task:
                get_scheduler().update_task(task)
            
            self._write_json({
                "code": 0,
                "msg": "任务更新成功"
            })
        
        elif action == "delete":
            task_id = int(self.get_body_argument("task_id", 0))
            if not task_id:
                self._write_json({"code": 1, "msg": "任务 ID 不能为空"})
                return
            
            # 从调度器移除
            get_scheduler().remove_task(task_id)
            
            # 删除任务
            success = ScheduledTask.delete_task(task_id)
            if success:
                self._write_json({"code": 0, "msg": "任务删除成功"})
            else:
                self._write_json({"code": 1, "msg": "任务不存在"})
        
        elif action == "toggle":
            task_id = int(self.get_body_argument("task_id", 0))
            if not task_id:
                self._write_json({"code": 1, "msg": "任务 ID 不能为空"})
                return
            
            task = ScheduledTask.get_task(task_id)
            if not task:
                self._write_json({"code": 1, "msg": "任务不存在"})
                return
            
            new_enabled = 0 if task['enabled'] else 1
            ScheduledTask.update_task(task_id=task_id, enabled=new_enabled)
            
            if new_enabled:
                get_scheduler().add_task(task)
            else:
                get_scheduler().remove_task(task_id)
            
            self._write_json({
                "code": 0,
                "msg": "任务状态已更新",
                "data": {"enabled": new_enabled}
            })
        
        elif action == "run_now":
            task_id = int(self.get_body_argument("task_id", 0))
            if not task_id:
                self._write_json({"code": 1, "msg": "任务 ID 不能为空"})
                return
            
            task = ScheduledTask.get_task(task_id)
            if not task:
                self._write_json({"code": 1, "msg": "任务不存在"})
                return
            
            # 立即执行任务（异步）
            tornado.ioloop.IOLoop.current().spawn_callback(
                self._execute_task_now,
                task_id,
                task['task_type'],
                task['config']
            )
            
            self._write_json({
                "code": 0,
                "msg": "任务已触发执行"
            })
        
        else:
            self._write_json({"code": 1, "msg": "未知操作"})
    
    async def _execute_task_now(self, task_id: int, task_type: str, config: Dict[str, Any]):
        """立即执行任务"""
        from app.models.scheduler_engine import TaskExecutor
        
        try:
            if task_type == 'surveillance_collect':
                await TaskExecutor.execute_surveillance_collect(task_id, config)
            elif task_type == 'deep_collect':
                await TaskExecutor.execute_deep_collect(task_id, config)
            elif task_type == 'surveillance':
                await TaskExecutor.execute_surveillance_collect(task_id, config)
            elif task_type == 'report':
                await TaskExecutor.execute_report_task(task_id, config)
            elif task_type == 'cleanup':
                await TaskExecutor.execute_cleanup_task(task_id, config)
            elif task_type == 'sync':
                await TaskExecutor.execute_sync_task(task_id, config)
            else:
                await TaskExecutor.execute_generic_task(task_id, task_type, config)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"立即执行任务 {task_id} 失败：{e}")


class AdminSchedulerLogHandler(AdminBaseHandler):
    """任务日志处理"""
    
    def _write_json(self, data):
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(data, ensure_ascii=False))
    
    @tornado.web.authenticated
    def get(self):
        action = self.get_argument("action", "")
        
        if action == "recent":
            days = int(self.get_argument("days", 7))
            logs = TaskLog.get_recent_logs(days)
            self._write_json({
                "code": 0,
                "msg": "ok",
                "data": {
                    "logs": logs,
                    "count": len(logs)
                }
            })
        else:
            self._write_json({"code": 1, "msg": "未知操作"})
