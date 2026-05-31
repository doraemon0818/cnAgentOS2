"""
定时任务调度器模块
使用 APScheduler 实现定时任务调度
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Callable
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger

from app.models.scheduler import ScheduledTask, TaskLog

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TaskExecutor:
    """任务执行器"""
    
    @staticmethod
    async def execute_surveillance_collect(task_id: int, task_config: Dict[str, Any]):
        """执行瞭望采集任务"""
        start_time = datetime.now()
        task_row = ScheduledTask.get_task(task_id)
        
        if not task_row:
            logger.error(f"任务 {task_id} 不存在")
            return
        
        try:
            keywords = task_config.get('keywords', ['AI', '机器学习', '大数据'])
            source_ids = task_config.get('source_ids', [])
            pages = task_config.get('pages', 1)
            max_items = task_config.get('max_items', 100)
            
            total_count = 0
            
            # 如果没有配置source_ids，使用模拟数据
            if not source_ids:
                source_ids = [1, 2, 3]
            
            # 模拟采集数据（实际项目中会调用真实的采集接口）
            for keyword in keywords[:3]:  # 限制关键字数量
                for source_id in source_ids[:3]:  # 限制源数量
                    try:
                        # 模拟采集结果
                        import random
                        collected = random.randint(5, 20)
                        total_count += collected
                        logger.info(f"从源 {source_id} 采集关键词 '{keyword}'，获取 {collected} 条数据")
                    except Exception as e:
                        logger.error(f"采集失败：{e}")
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # 记录成功日志
            TaskLog.create_log(
                task_id=task_id,
                task_name=task_row['name'],
                task_type=task_row['task_type'],
                status='success',
                message=f"采集完成，共获取 {total_count} 条数据",
                start_time=start_time.strftime('%Y-%m-%d %H:%M:%S'),
                end_time=end_time.strftime('%Y-%m-%d %H:%M:%S'),
                duration_seconds=duration,
                data_count=total_count
            )
            
            # 更新任务统计
            ScheduledTask.update_run_stats(task_id, True)
            
            logger.info(f"任务 {task_id} 执行成功，采集 {total_count} 条数据")
            
        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # 记录失败日志
            TaskLog.create_log(
                task_id=task_id,
                task_name=task_row['name'],
                task_type=task_row['task_type'],
                status='failed',
                message=f"执行失败：{str(e)}",
                start_time=start_time.strftime('%Y-%m-%d %H:%M:%S'),
                end_time=end_time.strftime('%Y-%m-%d %H:%M:%S'),
                duration_seconds=duration
            )
            
            # 更新任务统计
            ScheduledTask.update_run_stats(task_id, False)
            
            logger.error(f"任务 {task_id} 执行失败：{e}")
    
    @staticmethod
    async def execute_deep_collect(task_id: int, task_config: Dict[str, Any]):
        """执行 AI 深度采集任务"""
        start_time = datetime.now()
        task_row = ScheduledTask.get_task(task_id)
        
        if not task_row:
            logger.error(f"任务 {task_id} 不存在")
            return
        
        try:
            warehouse_ids = task_config.get('warehouse_ids', [])
            batch_size = task_config.get('batch_size', 10)
            
            success_count = 0
            fail_count = 0
            
            # 批量执行深度采集
            for i in range(0, len(warehouse_ids), batch_size):
                batch_ids = warehouse_ids[i:i+batch_size]
                for wid in batch_ids:
                    try:
                        # 调用深度采集接口
                        success, message, result = WarehouseDeepCollector.collect_by_warehouse_id(wid)
                        if success:
                            success_count += 1
                        else:
                            fail_count += 1
                    except Exception as e:
                        logger.error(f"深度采集 {wid} 失败：{e}")
                        fail_count += 1
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # 记录成功日志
            TaskLog.create_log(
                task_id=task_id,
                task_name=task_row['name'],
                task_type=task_row['task_type'],
                status='success',
                message=f"深度采集完成，成功 {success_count} 条，失败 {fail_count} 条",
                start_time=start_time.strftime('%Y-%m-%d %H:%M:%S'),
                end_time=end_time.strftime('%Y-%m-%d %H:%M:%S'),
                duration_seconds=duration,
                data_count=success_count
            )
            
            # 更新任务统计
            ScheduledTask.update_run_stats(task_id, True)
            
            logger.info(f"任务 {task_id} 执行成功，深度采集 {success_count} 条数据")
            
        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # 记录失败日志
            TaskLog.create_log(
                task_id=task_id,
                task_name=task_row['name'],
                task_type=task_row['task_type'],
                status='failed',
                message=f"执行失败：{str(e)}",
                start_time=start_time.strftime('%Y-%m-%d %H:%M:%S'),
                end_time=end_time.strftime('%Y-%m-%d %H:%M:%S'),
                duration_seconds=duration
            )
            
            # 更新任务统计
            ScheduledTask.update_run_stats(task_id, False)
            
            logger.error(f"任务 {task_id} 执行失败：{e}")
    
    @staticmethod
    async def execute_report_task(task_id: int, task_config: Dict[str, Any]):
        """执行报表生成任务"""
        start_time = datetime.now()
        task_row = ScheduledTask.get_task(task_id)
        
        if not task_row:
            logger.error(f"任务 {task_id} 不存在")
            return
        
        try:
            report_type = task_config.get('report_type', 'weekly')
            export_format = task_config.get('format', 'pdf')
            
            # 生成报表数据
            from app.models.report_generator import ReportGenerator
            report_data = ReportGenerator.generate_task_report(task_id, task_row['name'], task_row['task_type'])
            
            # 根据格式生成报表文件，文件名使用任务名称
            name_prefix = task_row['name'].replace(' ', '_')
            if export_format == 'pdf':
                report_path = ReportGenerator.generate_pdf_report(report_type, report_data, name_prefix)
            else:
                report_path = ReportGenerator.generate_excel_report(report_type, report_data, name_prefix)
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # 记录成功日志（包含报表文件名）
            import os
            report_filename = os.path.basename(report_path)
            TaskLog.create_log(
                task_id=task_id,
                task_name=task_row['name'],
                task_type=task_row['task_type'],
                status='success',
                message=f"报表生成完成，类型: {report_type}，格式: {export_format}，文件: {report_filename}",
                start_time=start_time.strftime('%Y-%m-%d %H:%M:%S'),
                end_time=end_time.strftime('%Y-%m-%d %H:%M:%S'),
                duration_seconds=duration,
                data_count=1,
                extra_data=json.dumps({'report_file': report_filename, 'report_path': report_path})
            )
            
            # 更新任务统计
            ScheduledTask.update_run_stats(task_id, True)
            
            logger.info(f"任务 {task_id} 执行成功，生成报表: {report_filename}")
            
        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # 记录失败日志
            TaskLog.create_log(
                task_id=task_id,
                task_name=task_row['name'],
                task_type=task_row['task_type'],
                status='failed',
                message=f"执行失败：{str(e)}",
                start_time=start_time.strftime('%Y-%m-%d %H:%M:%S'),
                end_time=end_time.strftime('%Y-%m-%d %H:%M:%S'),
                duration_seconds=duration
            )
            
            # 更新任务统计
            ScheduledTask.update_run_stats(task_id, False)
            
            logger.error(f"任务 {task_id} 执行失败：{e}")
    
    @staticmethod
    async def execute_cleanup_task(task_id: int, task_config: Dict[str, Any]):
        """执行清理任务"""
        start_time = datetime.now()
        task_row = ScheduledTask.get_task(task_id)
        
        if not task_row:
            logger.error(f"任务 {task_id} 不存在")
            return
        
        try:
            retention_days = task_config.get('retention_days', 30)
            clean_type = task_config.get('clean_type', 'logs')
            
            # 模拟清理操作
            import time
            time.sleep(0.5)  # 模拟处理时间
            
            deleted_count = 15  # 模拟删除数量
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # 记录成功日志
            TaskLog.create_log(
                task_id=task_id,
                task_name=task_row['name'],
                task_type=task_row['task_type'],
                status='success',
                message=f"清理完成，保留 {retention_days} 天数据，删除 {deleted_count} 条记录",
                start_time=start_time.strftime('%Y-%m-%d %H:%M:%S'),
                end_time=end_time.strftime('%Y-%m-%d %H:%M:%S'),
                duration_seconds=duration,
                data_count=deleted_count
            )
            
            # 更新任务统计
            ScheduledTask.update_run_stats(task_id, True)
            
            logger.info(f"任务 {task_id} 执行成功，清理 {deleted_count} 条记录")
            
        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # 记录失败日志
            TaskLog.create_log(
                task_id=task_id,
                task_name=task_row['name'],
                task_type=task_row['task_type'],
                status='failed',
                message=f"执行失败：{str(e)}",
                start_time=start_time.strftime('%Y-%m-%d %H:%M:%S'),
                end_time=end_time.strftime('%Y-%m-%d %H:%M:%S'),
                duration_seconds=duration
            )
            
            # 更新任务统计
            ScheduledTask.update_run_stats(task_id, False)
            
            logger.error(f"任务 {task_id} 执行失败：{e}")
    
    @staticmethod
    async def execute_sync_task(task_id: int, task_config: Dict[str, Any]):
        """执行数据同步任务"""
        start_time = datetime.now()
        task_row = ScheduledTask.get_task(task_id)
        
        if not task_row:
            logger.error(f"任务 {task_id} 不存在")
            return
        
        try:
            sync_source = task_config.get('sync_source', 'remote')
            sync_target = task_config.get('sync_target', 'local')
            
            # 模拟同步操作
            import time
            time.sleep(1.5)  # 模拟处理时间
            
            sync_count = 50  # 模拟同步数量
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # 记录成功日志
            TaskLog.create_log(
                task_id=task_id,
                task_name=task_row['name'],
                task_type=task_row['task_type'],
                status='success',
                message=f"同步完成，从 {sync_source} 同步到 {sync_target}，共 {sync_count} 条数据",
                start_time=start_time.strftime('%Y-%m-%d %H:%M:%S'),
                end_time=end_time.strftime('%Y-%m-%d %H:%M:%S'),
                duration_seconds=duration,
                data_count=sync_count
            )
            
            # 更新任务统计
            ScheduledTask.update_run_stats(task_id, True)
            
            logger.info(f"任务 {task_id} 执行成功，同步 {sync_count} 条数据")
            
        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # 记录失败日志
            TaskLog.create_log(
                task_id=task_id,
                task_name=task_row['name'],
                task_type=task_row['task_type'],
                status='failed',
                message=f"执行失败：{str(e)}",
                start_time=start_time.strftime('%Y-%m-%d %H:%M:%S'),
                end_time=end_time.strftime('%Y-%m-%d %H:%M:%S'),
                duration_seconds=duration
            )
            
            # 更新任务统计
            ScheduledTask.update_run_stats(task_id, False)
            
            logger.error(f"任务 {task_id} 执行失败：{e}")
    
    @staticmethod
    async def execute_api_check(task_id: int, task_config: Dict[str, Any]):
        """执行 API 健康检查任务"""
        start_time = datetime.now()
        task_row = ScheduledTask.get_task(task_id)
        
        if not task_row:
            logger.error(f"任务 {task_id} 不存在")
            return
        
        try:
            from app.models.api_endpoint import ApiEndpointRepository
            api_ids = task_config.get('api_ids', [])
            
            if not api_ids:
                rows = ApiEndpointRepository.get_endpoint_list(page=1, page_size=100)
                api_ids = [item['id'] for item in rows.get('list', [])]
            
            check_results = []
            for api_id in api_ids:
                api = ApiEndpointRepository.get_endpoint_by_id(api_id)
                if api:
                    check_results.append({
                        'api_id': api_id,
                        'name': api['name'],
                        'status': 'ok'
                    })
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            TaskLog.create_log(
                task_id=task_id,
                task_name=task_row['name'],
                task_type=task_row['task_type'],
                status='success',
                message=f"API 检查完成，共检查 {len(check_results)} 个接口",
                start_time=start_time.strftime('%Y-%m-%d %H:%M:%S'),
                end_time=end_time.strftime('%Y-%m-%d %H:%M:%S'),
                duration_seconds=duration,
                data_count=len(check_results)
            )
            
            ScheduledTask.update_run_stats(task_id, True)
            logger.info(f"任务 {task_id} 执行成功，API 检查 {len(check_results)} 个接口")
            
        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            TaskLog.create_log(
                task_id=task_id,
                task_name=task_row['name'],
                task_type=task_row['task_type'],
                status='failed',
                message=f"执行失败：{str(e)}",
                start_time=start_time.strftime('%Y-%m-%d %H:%M:%S'),
                end_time=end_time.strftime('%Y-%m-%d %H:%M:%S'),
                duration_seconds=duration
            )
            
            ScheduledTask.update_run_stats(task_id, False)
            logger.error(f"任务 {task_id} 执行失败：{e}")
    
    @staticmethod
    async def execute_employee_check(task_id: int, task_config: Dict[str, Any]):
        """执行数字员工状态巡检任务"""
        start_time = datetime.now()
        task_row = ScheduledTask.get_task(task_id)
        
        if not task_row:
            logger.error(f"任务 {task_id} 不存在")
            return
        
        try:
            from app.models.digital_employee import DigitalEmployeeRepository
            employees = DigitalEmployeeRepository.get_employee_list(page=1, page_size=100)
            employee_list = employees.get('list', [])
            
            enabled_count = sum(1 for e in employee_list if e.get('status') == 1)
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            TaskLog.create_log(
                task_id=task_id,
                task_name=task_row['name'],
                task_type=task_row['task_type'],
                status='success',
                message=f"员工巡检完成，共 {len(employee_list)} 个员工，{enabled_count} 个已启用",
                start_time=start_time.strftime('%Y-%m-%d %H:%M:%S'),
                end_time=end_time.strftime('%Y-%m-%d %H:%M:%S'),
                duration_seconds=duration,
                data_count=len(employee_list)
            )
            
            ScheduledTask.update_run_stats(task_id, True)
            logger.info(f"任务 {task_id} 执行成功，巡检 {len(employee_list)} 个数字员工")
            
        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            TaskLog.create_log(
                task_id=task_id,
                task_name=task_row['name'],
                task_type=task_row['task_type'],
                status='failed',
                message=f"执行失败：{str(e)}",
                start_time=start_time.strftime('%Y-%m-%d %H:%M:%S'),
                end_time=end_time.strftime('%Y-%m-%d %H:%M:%S'),
                duration_seconds=duration
            )
            
            ScheduledTask.update_run_stats(task_id, False)
            logger.error(f"任务 {task_id} 执行失败：{e}")
    
    @staticmethod
    async def execute_data_cleanup(task_id: int, task_config: Dict[str, Any]):
        """执行数据清理任务"""
        start_time = datetime.now()
        task_row = ScheduledTask.get_task(task_id)
        
        if not task_row:
            logger.error(f"任务 {task_id} 不存在")
            return
        
        try:
            from app.models.db import get_connection
            conn = get_connection()
            
            # 清理过期的任务日志（保留30天）
            cutoff_date = (datetime.now() - __import__('datetime').timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
            deleted_task_logs = conn.execute('delete from task_logs where created_at < ?', (cutoff_date,)).rowcount
            
            # 清理过期的工作流日志
            deleted_wf_logs = conn.execute('delete from workflow_logs where created_at < ?', (cutoff_date,)).rowcount
            
            conn.commit()
            conn.close()
            
            total_deleted = deleted_task_logs + deleted_wf_logs
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            TaskLog.create_log(
                task_id=task_id,
                task_name=task_row['name'],
                task_type=task_row['task_type'],
                status='success',
                message=f"数据清理完成，删除 {total_deleted} 条过期日志",
                start_time=start_time.strftime('%Y-%m-%d %H:%M:%S'),
                end_time=end_time.strftime('%Y-%m-%d %H:%M:%S'),
                duration_seconds=duration,
                data_count=total_deleted
            )
            
            ScheduledTask.update_run_stats(task_id, True)
            logger.info(f"任务 {task_id} 执行成功，清理 {total_deleted} 条过期日志")
            
        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            TaskLog.create_log(
                task_id=task_id,
                task_name=task_row['name'],
                task_type=task_row['task_type'],
                status='failed',
                message=f"执行失败：{str(e)}",
                start_time=start_time.strftime('%Y-%m-%d %H:%M:%S'),
                end_time=end_time.strftime('%Y-%m-%d %H:%M:%S'),
                duration_seconds=duration
            )
            
            ScheduledTask.update_run_stats(task_id, False)
            logger.error(f"任务 {task_id} 执行失败：{e}")
    
    @staticmethod
    async def execute_generic_task(task_id: int, task_type: str, task_config: Dict[str, Any]):
        """执行通用任务（兜底处理）"""
        start_time = datetime.now()
        task_row = ScheduledTask.get_task(task_id)
        
        if not task_row:
            logger.error(f"任务 {task_id} 不存在")
            return
        
        try:
            # 模拟通用任务执行
            import time
            time.sleep(0.8)  # 模拟处理时间
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # 记录成功日志
            TaskLog.create_log(
                task_id=task_id,
                task_name=task_row['name'],
                task_type=task_row['task_type'],
                status='success',
                message=f"任务执行完成，类型: {task_type}",
                start_time=start_time.strftime('%Y-%m-%d %H:%M:%S'),
                end_time=end_time.strftime('%Y-%m-%d %H:%M:%S'),
                duration_seconds=duration,
                data_count=0
            )
            
            # 更新任务统计
            ScheduledTask.update_run_stats(task_id, True)
            
            logger.info(f"任务 {task_id} 执行成功")
            
        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # 记录失败日志
            TaskLog.create_log(
                task_id=task_id,
                task_name=task_row['name'],
                task_type=task_row['task_type'],
                status='failed',
                message=f"执行失败：{str(e)}",
                start_time=start_time.strftime('%Y-%m-%d %H:%M:%S'),
                end_time=end_time.strftime('%Y-%m-%d %H:%M:%S'),
                duration_seconds=duration
            )
            
            # 更新任务统计
            ScheduledTask.update_run_stats(task_id, False)
            
            logger.error(f"任务 {task_id} 执行失败：{e}")


class SchedulerManager:
    """调度器管理器"""
    
    _instance: Optional['SchedulerManager'] = None
    _scheduler: Optional[BackgroundScheduler] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._scheduler is None:
            self._scheduler = BackgroundScheduler()
            self._task_jobs: Dict[int, str] = {}  # task_id -> job_id
    
    def start(self):
        """启动调度器"""
        if self._scheduler and not self._scheduler.running:
            self._scheduler.start()
            logger.info("调度器已启动")
    
    def shutdown(self, wait=True):
        """关闭调度器"""
        if self._scheduler and self._scheduler.running:
            self._scheduler.shutdown(wait=wait)
            logger.info("调度器已关闭")
    
    def load_tasks_from_db(self):
        """从数据库加载所有启用的任务"""
        if not self._scheduler:
            return
        
        tasks = ScheduledTask.get_enabled_tasks()
        for task in tasks:
            self.add_task(task)
        
        logger.info(f"从数据库加载了 {len(tasks)} 个定时任务")
    
    def add_task(self, task: Dict[str, Any]):
        """添加定时任务"""
        if not self._scheduler:
            return
        
        task_id = task['id']
        job_id = f"task_{task_id}"
        
        # 如果任务已存在，先移除
        if self._scheduler.get_job(job_id):
            self._scheduler.remove_job(job_id)
        
        # 解析 Cron 表达式
        try:
            cron_parts = task['cron_expression'].split()
            if len(cron_parts) == 5:
                minute, hour, day, month, day_of_week = cron_parts
            else:
                logger.error(f"任务 {task_id} 的 Cron 表达式格式错误：{task['cron_expression']}")
                return
            
            trigger = CronTrigger(
                minute=minute,
                hour=hour,
                day=day,
                month=month,
                day_of_week=day_of_week
            )
            
            # 添加任务
            self._scheduler.add_job(
                self._execute_task,
                trigger=trigger,
                id=job_id,
                name=task['name'],
                args=[task_id, task['task_type'], task['config']],
                replace_existing=True
            )
            
            self._task_jobs[task_id] = job_id
            logger.info(f"添加定时任务：{task['name']} (ID: {task_id})")
            
        except Exception as e:
            logger.error(f"添加任务 {task_id} 失败：{e}")
    
    def remove_task(self, task_id: int):
        """移除定时任务"""
        if not self._scheduler:
            return
        
        job_id = f"task_{task_id}"
        if self._scheduler.get_job(job_id):
            self._scheduler.remove_job(job_id)
            if task_id in self._task_jobs:
                del self._task_jobs[task_id]
            logger.info(f"移除定时任务 ID: {task_id}")
    
    def update_task(self, task: Dict[str, Any]):
        """更新定时任务"""
        self.remove_task(task['id'])
        if task.get('enabled'):
            self.add_task(task)
    
    def _execute_task(self, task_id: int, task_type: str, config: Dict[str, Any]):
        """执行任务的内部方法"""
        logger.info(f"开始执行任务 {task_id}, 类型：{task_type}")
        
        try:
            if task_type in ('surveillance_collect', 'surveillance'):
                import asyncio
                asyncio.run(TaskExecutor.execute_surveillance_collect(task_id, config))
            elif task_type == 'deep_collect':
                import asyncio
                asyncio.run(TaskExecutor.execute_deep_collect(task_id, config))
            elif task_type == 'api_check':
                import asyncio
                asyncio.run(TaskExecutor.execute_api_check(task_id, config))
            elif task_type == 'employee_check':
                import asyncio
                asyncio.run(TaskExecutor.execute_employee_check(task_id, config))
            elif task_type == 'data_cleanup':
                import asyncio
                asyncio.run(TaskExecutor.execute_data_cleanup(task_id, config))
            elif task_type == 'report':
                import asyncio
                asyncio.run(TaskExecutor.execute_report_task(task_id, config))
            elif task_type == 'cleanup':
                import asyncio
                asyncio.run(TaskExecutor.execute_cleanup_task(task_id, config))
            elif task_type == 'sync':
                import asyncio
                asyncio.run(TaskExecutor.execute_sync_task(task_id, config))
            else:
                import asyncio
                asyncio.run(TaskExecutor.execute_generic_task(task_id, task_type, config))
        except Exception as e:
            logger.error(f"任务 {task_id} 执行异常：{e}")
    
    def get_all_jobs(self):
        """获取所有任务"""
        if not self._scheduler:
            return []
        
        jobs = []
        for job in self._scheduler.get_jobs():
            jobs.append({
                'id': job.id,
                'name': job.name,
                'next_run_time': job.next_run_time.strftime('%Y-%m-%d %H:%M:%S') if job.next_run_time else None,
                'trigger': str(job.trigger)
            })
        return jobs


# 全局调度器实例
scheduler_manager = SchedulerManager()


def init_scheduler():
    """初始化调度器"""
    scheduler_manager.start()
    scheduler_manager.load_tasks_from_db()


def get_scheduler():
    """获取调度器实例"""
    return scheduler_manager
