"""
初始化示例数据 - 自动化模块
用于演示和测试定时任务、工作流、监控仪表盘功能
"""
import sys
import io
from datetime import datetime, timedelta
from app.models.db import get_connection, init_db

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def create_sample_data():
    """创建示例数据"""
    
    # 初始化数据库表
    init_db()
    
    conn = get_connection()
    cursor = conn.cursor()
    
    print("=" * 70)
    print("🚀 开始初始化示例数据...")
    print("=" * 70)
    
    now = datetime.now()
    
    # ============================================================
    # 1. 创建示例定时任务 (4个任务，匹配截图显示的数据)
    # ============================================================
    print("\n📋 [1/3] 创建定时任务...")
    
    scheduled_tasks = [
        {
            'name': '每日瞭望数据采集',
            'task_type': 'surveillance',
            'cron_expression': '0 0 2 * * *',
            'config': {
                'source_ids': [1, 2, 3],
                'collect_type': 'full',
                'timeout': 300,
                'retry_count': 3
            },
            'enabled': 1,
            'run_count': 2,
            'success_count': 2,
            'fail_count': 0,
            'last_run_time': (now - timedelta(hours=26)).strftime('%Y-%m-%d %H:%M:%S'),
            'created_at': (now - timedelta(days=1)).strftime('%Y-%m-%d %H:28:36')
        },
        {
            'name': '数据库自动备份',
            'task_type': 'backup',
            'cron_expression': '0 0 3 * * *',
            'config': {
                'backup_type': 'full',
                'keep_days': 30,
                'compress': True,
                'storage_path': '/backups/database/'
            },
            'enabled': 1,
            'run_count': 5,
            'success_count': 5,
            'fail_count': 0,
            'last_run_time': (now - timedelta(hours=22)).strftime('%Y-%m-%d %H:%M:%S'),
            'created_at': (now - timedelta(days=5)).strftime('%Y-%m-%d %H:%M:%S')
        },
        {
            'name': '系统日志清理',
            'task_type': 'cleanup',
            'cron_expression': '0 0 4 * * 0',
            'config': {
                'log_types': ['access', 'error', 'debug'],
                'retain_days': 90,
                'max_size_mb': 1000
            },
            'enabled': 1,
            'run_count': 12,
            'success_count': 11,
            'fail_count': 1,
            'last_run_time': (now - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S'),
            'created_at': (now - timedelta(days=84)).strftime('%Y-%m-%d %H:%M:%S')
        },
        {
            'name': '模型服务健康检查',
            'task_type': 'health_check',
            'cron_expression': '*/30 * * * * *',
            'config': {
                'check_items': ['response_time', 'accuracy', 'memory_usage'],
                'alert_threshold': {'response_time': 5000, 'memory_usage': 80},
                'notification': ['email', 'wechat']
            },
            'enabled': 1,
            'run_count': 288,
            'success_count': 286,
            'fail_count': 2,
            'last_run_time': (now - timedelta(minutes=15)).strftime('%Y-%m-%d %H:%M:%S'),
            'created_at': (now - timedelta(days=10)).strftime('%Y-%m-%d %H:%M:%S')
        }
    ]
    
    task_ids = []
    for task in scheduled_tasks:
        cursor.execute('''
            INSERT INTO scheduled_tasks 
            (name, task_type, cron_expression, config, enabled, run_count, success_count, fail_count, 
             last_run_time, created_at, updated_at) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            task['name'],
            task['task_type'],
            task['cron_expression'],
            str(task['config']),
            task['enabled'],
            task['run_count'],
            task['success_count'],
            task['fail_count'],
            task.get('last_run_time'),
            task['created_at'],
            task['created_at']
        ))
        task_id = cursor.lastrowid
        task_ids.append(task_id)
        status = '✅' if task['enabled'] else '⏸️'
        print(f"  {status} [{task_id}] {task['name']} ({task['task_type']})")
        print(f"      Cron: {task['cron_expression']} | 执行{task['run_count']}次 | 成功率{round(task['success_count']/task['run_count']*100, 1)}%")
    
    print(f"\n✅ 已创建 {len(task_ids)} 个定时任务")
    
    # ============================================================
    # 2. 创建示例工作流 (3个工作流)
    # ============================================================
    print("\n🔄 [2/3] 创建工作流...")
    
    workflows = [
        {
            'name': '舆情数据自动处理流程',
            'description': '自动完成数据采集→清洗→分析→入库的全流程',
            'workflow_type': 'data_processing',
            'nodes_config': [
                {'id': 'node_1', 'type': 'data_collect', 'name': '数据采集', 'config': {'sources': ['weibo', 'news', 'forum']}},
                {'id': 'node_2', 'type': 'data_clean', 'name': '数据清洗', 'config': {'remove_duplicates': True, 'filter_spam': True}},
                {'id': 'node_3', 'type': 'sentiment_analysis', 'name': '情感分析', 'config': {'model': 'bert-base-chinese'}},
                {'id': 'node_4', 'type': 'save_to_db', 'name': '结果入库', 'config': {'table': 'opinion_results'}}
            ],
            'trigger_type': 'schedule',
            'trigger_config': {'cron_expression': '0 0 */6 * * *'},
            'enabled': 1,
            'run_count': 18,
            'success_count': 17,
            'fail_count': 1,
            'last_run_time': (now - timedelta(hours=6)).strftime('%Y-%m-%d %H:%M:%S'),
            'created_at': (now - timedelta(days=14)).strftime('%Y-%m-%d %H:%M:%S')
        },
        {
            'name': '每日运营报表生成',
            'description': '自动生成用户活跃度、模型调用、数据源统计报表',
            'workflow_type': 'report_generation',
            'nodes_config': [
                {'id': 'node_1', 'type': 'query_stats', 'name': '查询统计数据', 'config': {}},
                {'id': 'node_2', 'type': 'generate_charts', 'name': '生成图表', 'config': {'formats': ['png', 'pdf']}},
                {'id': 'node_3', 'type': 'compile_report', 'name': '编译报告', 'config': {'template': 'daily_report'}},
                {'id': 'node_4', 'type': 'send_notification', 'name': '发送通知', 'config': {'channels': ['email', 'dingtalk']}}
            ],
            'trigger_type': 'cron',
            'trigger_config': {'cron_expression': '0 0 9 * * *'},
            'enabled': 1,
            'run_count': 25,
            'success_count': 24,
            'fail_count': 1,
            'last_run_time': (now - timedelta(hours=16)).strftime('%Y-%m-%d %H:%M:%S'),
            'created_at': (now - timedelta(days=25)).strftime('%Y-%m-%d %H:%M:%S')
        },
        {
            'name': '异常检测与告警流程',
            'description': '监控系统指标，发现异常时自动触发告警',
            'workflow_type': 'alerting',
            'nodes_config': [
                {'id': 'node_1', 'type': 'collect_metrics', 'name': '收集指标', 'config': {'metrics': ['cpu', 'memory', 'disk', 'network']}},
                {'id': 'node_2', 'type': 'analyze_anomaly', 'name': '异常检测', 'config': {'algorithm': 'isolation_forest'}},
                {'id': 'node_3', 'type': 'check_thresholds', 'name': '阈值判断', 'config': {'thresholds': {'cpu': 85, 'memory': 90}}},
                {'id': 'node_4', 'type': 'send_alert', 'name': '发送告警', 'config': {'severity_levels': ['warning', 'critical']}}
            ],
            'trigger_type': 'realtime',
            'trigger_config': {'interval_seconds': 60},
            'enabled': 1,
            'run_count': 156,
            'success_count': 154,
            'fail_count': 2,
            'last_run_time': (now - timedelta(minutes=45)).strftime('%Y-%m-%d %H:%M:%S'),
            'created_at': (now - timedelta(days=20)).strftime('%Y-%m-%d %H:%M:%S')
        }
    ]
    
    workflow_ids = []
    for wf in workflows:
        cursor.execute('''
            INSERT INTO workflows 
            (name, description, workflow_type, nodes_config, trigger_type, trigger_config, 
             enabled, run_count, success_count, fail_count, last_run_time, created_at, updated_at) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            wf['name'],
            wf['description'],
            wf['workflow_type'],
            str(wf['nodes_config']),
            wf['trigger_type'],
            str(wf['trigger_config']),
            wf['enabled'],
            wf['run_count'],
            wf['success_count'],
            wf['fail_count'],
            wf.get('last_run_time'),
            wf['created_at'],
            wf['created_at']
        ))
        workflow_id = cursor.lastrowid
        workflow_ids.append(workflow_id)
        status = '✅' if wf['enabled'] else '⏸️'
        print(f"  {status} [{workflow_id}] {wf['name']} ({wf['workflow_type']})")
        print(f"      触发方式: {wf['trigger_type']} | 执行{wf['run_count']}次 | 成功率{round(wf['success_count']/wf['run_count']*100, 1)}%")
    
    print(f"\n✅ 已创建 {len(workflow_ids)} 个工作流")
    
    # ============================================================
    # 3. 创建执行日志 (让系统看起来有运行历史)
    # ============================================================
    print("\n📊 [3/3] 创建执行日志...")
    
    total_logs = 0
    
    # 定时任务执行日志
    for i, task in enumerate(scheduled_tasks):
        for j in range(min(task['run_count'], 5)):  # 每个任务最多5条日志
            log_time = (now - timedelta(
                hours=j*24 + i*2,
                minutes=(j*37) % 60
            )).strftime('%Y-%m-%d %H:%M:%S')
            
            is_success = j < task['success_count']
            status = 'success' if is_success else 'failed'
            
            message = ''
            data_count = 0
            duration = 0
            
            if task['task_type'] == 'surveillance':
                message = f'成功采集 {150 + j*23} 条数据' if is_success else '连接超时'
                data_count = 150 + j*23 if is_success else 0
                duration = 125.5 + j*10 if is_success else 300
            elif task['task_type'] == 'backup':
                message = f'备份完成，文件大小 {256 + j*50}MB' if is_success else '磁盘空间不足'
                data_count = 1 if is_success else 0
                duration = 320 + j*20 if is_success else 0
            elif task['task_type'] == 'cleanup':
                message = f'清理了 {1200 + j*200} 条过期日志' if is_success else '权限不足'
                data_count = 1200 + j*200 if is_success else 0
                duration = 45.2 + j*5 if is_success else 0
            elif task['task_type'] == 'health_check':
                message = '所有服务正常运行' if is_success else '响应时间超过阈值'
                data_count = 5 if is_success else 0
                duration = 3.2 + j*0.5 if is_success else 0
            
            end_time = (now - timedelta(
                hours=j*24 + i*2,
                minutes=(j*37) % 60,
                seconds=int(duration) if duration > 0 else 0
            )).strftime('%Y-%m-%d %H:%M:%S') if is_success else None
            
            cursor.execute('''
                INSERT INTO task_logs 
                (task_id, task_name, task_type, status, message, start_time, end_time, 
                 duration_seconds, data_count, created_at) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                task_ids[i], task['name'], task['task_type'], status, message,
                log_time, end_time, duration, data_count, log_time
            ))
            total_logs += 1
    
    # 工作流执行日志
    for i, wf in enumerate(workflows):
        for j in range(min(wf['run_count'], 4)):  # 每个工作流最多4条日志
            log_time = (now - timedelta(
                hours=j*6 + i*3,
                minutes=(j*29) % 60
            )).strftime('%Y-%m-%d %H:%M:%S')
            
            is_success = j < wf['success_count']
            status = 'completed' if is_success else 'failed'
            
            message = ''
            node_results = []
            duration = 0
            
            if wf['workflow_type'] == 'data_processing':
                nodes = ['数据采集', '数据清洗', '情感分析', '结果入库']
                if is_success:
                    message = '数据处理流程执行成功'
                    node_results = [
                        {'node': nodes[0], 'status': 'success', 'data_count': 1200},
                        {'node': nodes[1], 'status': 'success', 'data_count': 1150},
                        {'node': nodes[2], 'status': 'success', 'data_count': 1150},
                        {'node': nodes[3], 'status': 'success', 'data_count': 1150}
                    ]
                    duration = 245.8 + j*15
                else:
                    message = '情感分析节点失败：模型服务不可用'
                    node_results = [
                        {'node': nodes[0], 'status': 'success', 'data_count': 1180},
                        {'node': nodes[1], 'status': 'success', 'data_count': 1130},
                        {'node': nodes[2], 'status': 'failed', 'error': 'Connection timeout'}
                    ]
                    
            elif wf['workflow_type'] == 'report_generation':
                nodes = ['查询统计', '生成图表', '编译报告', '发送通知']
                if is_success:
                    message = '日报生成并发送成功'
                    node_results = [
                        {'node': nodes[0], 'status': 'success'},
                        {'node': nodes[1], 'status': 'success', 'files': ['chart1.png', 'chart2.png']},
                        {'node': nodes[2], 'status': 'success', 'file': 'daily_report_20260530.pdf'},
                        {'node': nodes[3], 'status': 'success', 'channels': ['email', 'dingtalk']}
                    ]
                    duration = 185.3 + j*12
                else:
                    message = '邮件发送失败：SMTP服务器无响应'
                    node_results = [
                        {'node': nodes[0], 'status': 'success'},
                        {'node': nodes[1], 'status': 'success'},
                        {'node': nodes[2], 'status': 'success', 'file': 'daily_report_20260529.pdf'},
                        {'node': nodes[3], 'status': 'failed', 'error': 'SMTP connection timeout'}
                    ]
                    
            elif wf['workflow_type'] == 'alerting':
                nodes = ['收集指标', '异常检测', '阈值判断', '发送告警']
                if is_success:
                    message = '监控正常，未发现异常'
                    node_results = [
                        {'node': nodes[0], 'status': 'success', 'metrics': {'cpu': 45, 'memory': 62}},
                        {'node': nodes[1], 'status': 'success', 'anomalies': []},
                        {'node': nodes[2], 'status': 'success', 'alert_level': 'none'}
                    ]
                    duration = 12.6 + j*2
                else:
                    message = 'CPU使用率超过阈值，已发送告警'
                    node_results = [
                        {'node': nodes[0], 'status': 'success', 'metrics': {'cpu': 92, 'memory': 78}},
                        {'node': nodes[1], 'status': 'success', 'anomalies': [{'metric': 'cpu', 'value': 92}]},
                        {'node': nodes[2], 'status': 'success', 'alert_level': 'critical'},
                        {'node': nodes[3], 'status': 'success', 'sent_to': ['admin@company.com']}
                    ]
                    duration = 8.3
            
            end_time = (now - timedelta(
                hours=j*6 + i*3,
                minutes=(j*29) % 60,
                seconds=int(duration) if duration > 0 else 0
            )).strftime('%Y-%m-%d %H:%M:%S') if is_success else None
            
            cursor.execute('''
                INSERT INTO workflow_logs 
                (workflow_id, workflow_name, workflow_type, status, message, start_time, end_time, 
                 duration_seconds, node_results, created_at) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                workflow_ids[i], wf['name'], wf['workflow_type'], status, message,
                log_time, end_time, duration, str(node_results), log_time
            ))
            total_logs += 1
    
    print(f"\n✅ 已创建 {total_logs} 条执行日志")
    
    # 提交所有更改
    conn.commit()
    conn.close()
    
    # ============================================================
    # 统计汇总
    # ============================================================
    print("\n" + "=" * 70)
    print("📈 数据初始化完成！统计信息：")
    print("=" * 70)
    print(f"\n⏰ 定时任务:")
    print(f"   总数: {len(task_ids)} 个")
    print(f"   启用: {sum(1 for t in scheduled_tasks if t['enabled'])} 个")
    print(f"   总执行次数: {sum(t['run_count'] for t in scheduled_tasks)} 次")
    print(f"   平均成功率: {round(sum(t['success_count']/t['run_count'] for t in scheduled_tasks)/len(scheduled_tasks)*100, 1)}%")
    
    print(f"\n🔄 工作流:")
    print(f"   总数: {len(workflow_ids)} 个")
    print(f"   启用: {sum(1 for w in workflows if w['enabled'])} 个")
    print(f"   总执行次数: {sum(w['run_count'] for w in workflows)} 次")
    print(f"   平均成功率: {round(sum(w['success_count']/w['run_count'] for w in workflows)/len(workflows)*100, 1)}%")
    
    print(f"\n📊 执行日志:")
    print(f"   总计: {total_logs} 条")
    
    print("\n" + "=" * 70)
    print("✨ 现在可以刷新页面查看效果了！")
    print("=" * 70)


if __name__ == '__main__':
    try:
        create_sample_data()
    except Exception as e:
        print(f"\n❌ 初始化失败: {e}")
        import traceback
        traceback.print_exc()
