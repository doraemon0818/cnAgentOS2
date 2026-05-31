import json
import time
import tornado.web
from datetime import datetime
from typing import Dict, Any, List

from app.controllers.admin import AdminBaseHandler
from app.models.workflow import Workflow, WorkflowLog
from app.models.scheduler import ScheduledTask


class AdminWorkflowListHandler(AdminBaseHandler):
    """工作流列表页面"""
    
    @tornado.web.authenticated
    def get(self):
        self.render(
            "admin/workflow/list.html",
            title="工作流管理"
        )


class AdminWorkflowApiHandler(AdminBaseHandler):
    """工作流 API 接口"""
    
    def _write_json(self, data):
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(data, ensure_ascii=False))
    
    @tornado.web.authenticated
    def get(self):
        """获取工作流列表"""
        action = self.get_argument("action", "")
        
        if action == "list":
            workflows = Workflow.get_all_workflows()
            self._write_json({
                "code": 0,
                "msg": "ok",
                "data": {
                    "workflows": workflows,
                    "count": len(workflows)
                }
            })
        
        elif action == "info":
            workflow_id = int(self.get_argument("workflow_id", 0))
            if not workflow_id:
                self._write_json({"code": 1, "msg": "工作流 ID 不能为空"})
                return
            
            workflow = Workflow.get_workflow(workflow_id)
            if not workflow:
                self._write_json({"code": 1, "msg": "工作流不存在"})
                return
            
            self._write_json({
                "code": 0,
                "msg": "ok",
                "data": workflow
            })
        
        elif action == "logs":
            workflow_id = int(self.get_argument("workflow_id", 0))
            limit = int(self.get_argument("limit", 100))
            logs = WorkflowLog.get_logs(workflow_id if workflow_id else None, limit)
            self._write_json({
                "code": 0,
                "msg": "ok",
                "data": {
                    "logs": logs,
                    "count": len(logs)
                }
            })
        
        elif action == "templates":
            templates = self._get_workflow_templates()
            self._write_json({
                "code": 0,
                "msg": "ok",
                "data": {"templates": templates}
            })
        
        else:
            self._write_json({"code": 1, "msg": "未知操作"})
    
    @tornado.web.authenticated
    def post(self):
        """创建或更新工作流"""
        action = self.get_body_argument("action", "")
        
        if action == "create":
            name = self.get_body_argument("name", "").strip()
            workflow_type = self.get_body_argument("workflow_type", "").strip()
            nodes_json = self.get_body_argument("nodes_config", "[]")
            trigger_type = self.get_body_argument("trigger_type", "").strip()
            trigger_config_json = self.get_body_argument("trigger_config", "{}")
            description = self.get_body_argument("description", "").strip()
            enabled = int(self.get_body_argument("enabled", 1))
            
            if not name:
                self._write_json({"code": 1, "msg": "工作流名称不能为空"})
                return
            
            if not workflow_type:
                self._write_json({"code": 1, "msg": "工作流类型不能为空"})
                return
            
            try:
                nodes_config = json.loads(nodes_json)
                trigger_config = json.loads(trigger_config_json)
            except:
                self._write_json({"code": 1, "msg": "配置 JSON 格式错误"})
                return
            
            workflow_id = Workflow.create_workflow(
                name=name,
                workflow_type=workflow_type,
                nodes_config=nodes_config,
                trigger_type=trigger_type,
                trigger_config=trigger_config,
                description=description,
                enabled=enabled
            )
            
            self._write_json({
                "code": 0,
                "msg": "工作流创建成功",
                "data": {"workflow_id": workflow_id}
            })
        
        elif action == "update":
            workflow_id = int(self.get_body_argument("workflow_id", 0))
            if not workflow_id:
                self._write_json({"code": 1, "msg": "工作流 ID 不能为空"})
                return
            
            name = self.get_body_argument("name", "").strip()
            workflow_type = self.get_body_argument("workflow_type", "").strip()
            nodes_json = self.get_body_argument("nodes_config", "[]")
            trigger_type = self.get_body_argument("trigger_type", "").strip()
            trigger_config_json = self.get_body_argument("trigger_config", "{}")
            description = self.get_body_argument("description", "").strip()
            enabled = int(self.get_body_argument("enabled", 1))
            
            if not name:
                self._write_json({"code": 1, "msg": "工作流名称不能为空"})
                return
            
            try:
                nodes_config = json.loads(nodes_json)
                trigger_config = json.loads(trigger_config_json)
            except:
                self._write_json({"code": 1, "msg": "配置 JSON 格式错误"})
                return
            
            Workflow.update_workflow(
                workflow_id=workflow_id,
                name=name,
                workflow_type=workflow_type,
                nodes_config=nodes_config,
                trigger_type=trigger_type,
                trigger_config=trigger_config,
                description=description,
                enabled=enabled
            )
            
            self._write_json({
                "code": 0,
                "msg": "工作流更新成功"
            })
        
        elif action == "delete":
            workflow_id = int(self.get_body_argument("workflow_id", 0))
            if not workflow_id:
                self._write_json({"code": 1, "msg": "工作流 ID 不能为空"})
                return
            
            success = Workflow.delete_workflow(workflow_id)
            if success:
                self._write_json({"code": 0, "msg": "工作流删除成功"})
            else:
                self._write_json({"code": 1, "msg": "工作流不存在"})
        
        elif action == "toggle":
            workflow_id = int(self.get_body_argument("workflow_id", 0))
            if not workflow_id:
                self._write_json({"code": 1, "msg": "工作流 ID 不能为空"})
                return
            
            workflow = Workflow.get_workflow(workflow_id)
            if not workflow:
                self._write_json({"code": 1, "msg": "工作流不存在"})
                return
            
            new_enabled = 0 if workflow['enabled'] else 1
            Workflow.update_workflow(workflow_id=workflow_id, enabled=new_enabled)
            
            self._write_json({
                "code": 0,
                "msg": "工作流状态已更新",
                "data": {"enabled": new_enabled}
            })
        
        elif action == "run_now":
            workflow_id = int(self.get_body_argument("workflow_id", 0))
            if not workflow_id:
                self._write_json({"code": 1, "msg": "工作流 ID 不能为空"})
                return
            
            workflow = Workflow.get_workflow(workflow_id)
            if not workflow:
                self._write_json({"code": 1, "msg": "工作流不存在"})
                return
            
            tornado.ioloop.IOLoop.current().spawn_callback(
                self._execute_workflow_now,
                workflow_id,
                workflow
            )
            
            self._write_json({
                "code": 0,
                "msg": "工作流已触发执行"
            })
        
        else:
            self._write_json({"code": 1, "msg": "未知操作"})
    
    async def _execute_workflow_now(self, workflow_id: int, workflow: Dict[str, Any]):
        """立即执行工作流"""
        from app.models.workflow_engine import WorkflowEngine
        
        start_time = time.time()
        try:
            engine = WorkflowEngine()
            result = await engine.execute_workflow(workflow)
            
            duration = time.time() - start_time
            
            WorkflowLog.create_log(
                workflow_id=workflow_id,
                workflow_name=workflow['name'],
                workflow_type=workflow['workflow_type'],
                status='success' if result.get('success') else 'failed',
                message=result.get('message', ''),
                node_results=result.get('steps', []),
                start_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                duration_seconds=duration
            )
            
            Workflow.update_run_stats(workflow_id, result.get('success', False))
            
        except Exception as e:
            duration = time.time() - start_time
            WorkflowLog.create_log(
                workflow_id=workflow_id,
                workflow_name=workflow['name'],
                workflow_type=workflow['workflow_type'],
                status='failed',
                message=f"执行失败：{str(e)}",
                start_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                duration_seconds=duration
            )
            Workflow.update_run_stats(workflow_id, False)
    
    def _get_workflow_templates(self) -> List[Dict[str, Any]]:
        """获取工作流模板"""
        return [
            {
                "id": "template_1",
                "name": "自动采集 → AI 深度采集 → 数据入库",
                "description": "完整的自动化数据采集流程",
                "workflow_type": "data_pipeline",
                "nodes_config": [
                    {"id": "node_1", "type": "collect", "name": "瞭望采集", "config": {}},
                    {"id": "node_2", "type": "deep_collect", "name": "AI 深度采集", "config": {}},
                    {"id": "node_3", "type": "save", "name": "数据入库", "config": {}}
                ],
                "trigger_type": "manual",
                "trigger_config": {}
            },
            {
                "id": "template_2",
                "name": "接口健康检查",
                "description": "定时检查 API 接口可用性",
                "workflow_type": "health_check",
                "nodes_config": [
                    {"id": "node_1", "type": "check_api", "name": "检查接口", "config": {}},
                    {"id": "node_2", "type": "record_status", "name": "记录状态", "config": {}},
                    {"id": "node_3", "type": "notify", "name": "异常通知", "config": {}}
                ],
                "trigger_type": "cron",
                "trigger_config": {"cron_expression": "0 */30 * * * *"}
            },
            {
                "id": "template_3",
                "name": "模型服务巡检",
                "description": "定时测试模型连通性",
                "workflow_type": "model_check",
                "nodes_config": [
                    {"id": "node_1", "type": "test_model", "name": "测试模型", "config": {}},
                    {"id": "node_2", "type": "collect_stats", "name": "收集统计", "config": {}},
                    {"id": "node_3", "type": "generate_report", "name": "生成报表", "config": {}}
                ],
                "trigger_type": "cron",
                "trigger_config": {"cron_expression": "0 0 */6 * * *"}
            }
        ]


class AdminWorkflowStatsHandler(AdminBaseHandler):
    """工作流统计"""
    
    def _write_json(self, data):
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(data, ensure_ascii=False))
    
    @tornado.web.authenticated
    def get(self):
        action = self.get_argument("action", "")
        
        if action == "dashboard":
            workflows = Workflow.get_all_workflows()
            
            total_workflows = len(workflows)
            enabled_workflows = sum(1 for w in workflows if w['enabled'])
            total_runs = sum(w['run_count'] for w in workflows)
            total_success = sum(w['success_count'] for w in workflows)
            total_fail = sum(w['fail_count'] for w in workflows)
            
            success_rate = 0
            if total_runs > 0:
                success_rate = round(total_success / total_runs * 100, 2)
            
            self._write_json({
                "code": 0,
                "msg": "ok",
                "data": {
                    "total_workflows": total_workflows,
                    "enabled_workflows": enabled_workflows,
                    "total_runs": total_runs,
                    "total_success": total_success,
                    "total_fail": total_fail,
                    "success_rate": success_rate
                }
            })
        else:
            self._write_json({"code": 1, "msg": "未知操作"})
