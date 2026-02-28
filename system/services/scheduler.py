"""
常态化监控定时调度服务

基于APScheduler实现对多个集群的定时巡检
对应论文第五章 5.3.5 常态化监控模块
"""

from datetime import datetime, timedelta

import models
from services.data_loader import DataLoader
from services.preprocessor import Preprocessor
from services.detection_engine import DetectionEngine
from services.alert_service import check_alert_rules

# 尝试导入APScheduler（可选依赖）
try:
    from apscheduler.schedulers.background import BackgroundScheduler
    SCHEDULER_AVAILABLE = True
except ImportError:
    SCHEDULER_AVAILABLE = False

scheduler = None


def init_scheduler():
    """初始化调度器并加载所有活跃集群的巡检任务"""
    global scheduler
    if not SCHEDULER_AVAILABLE:
        print("[Scheduler] APScheduler不可用，常态化监控功能已禁用")
        return

    scheduler = BackgroundScheduler()

    # 从数据库加载所有活跃的集群配置
    clusters = models.query_all('cluster_configs', where={'is_active': 1})
    for cluster in clusters:
        _add_cluster_job(cluster)

    if clusters:
        scheduler.start()
        print(f"[Scheduler] 已启动，监控 {len(clusters)} 个集群")
    else:
        print("[Scheduler] 暂无活跃集群配置")


def _add_cluster_job(cluster):
    """为一个集群添加定时巡检任务"""
    if scheduler is None:
        return
    job_id = f"monitor_{cluster['cluster_id']}"
    scheduler.add_job(
        func=run_detection_cycle,
        trigger='interval',
        minutes=cluster['check_interval'],
        id=job_id,
        args=[cluster['cluster_id']],
        replace_existing=True,
        max_instances=1,
    )


def update_cluster_job(cluster_id):
    """更新某个集群的巡检任务（新增/修改/停用时调用）"""
    if scheduler is None:
        return

    job_id = f"monitor_{cluster_id}"

    # 先移除旧任务
    try:
        scheduler.remove_job(job_id)
    except Exception:
        pass

    # 如果集群仍然活跃，重新添加
    cluster = models.query_one('cluster_configs', {'cluster_id': cluster_id})
    if cluster and cluster['is_active']:
        _add_cluster_job(cluster)


def run_detection_cycle(cluster_id):
    """
    执行单次巡检周期的完整流程

    流程: 拉取数据 -> 预处理 -> 检测 -> 保存结果 -> 触发告警
    """
    cluster = models.query_one('cluster_configs', {'cluster_id': cluster_id})
    if not cluster or not cluster['is_active']:
        return

    now = datetime.now()
    window_minutes = cluster['check_interval'] * 10  # 检测窗口为巡检间隔的10倍

    # 创建检测任务记录
    task_id = models.insert('detection_tasks', {
        'cluster_id': cluster_id,
        'task_type': 'scheduled',
        'scenario': cluster['scenario_type'],
        'status': 'running',
        'data_source': 'prometheus',
        'started_at': now.strftime('%Y-%m-%d %H:%M:%S'),
    })

    try:
        # Step 1: 拉取Prometheus数据
        end_time = now
        start_time = end_time - timedelta(minutes=window_minutes)
        raw_data = DataLoader.load_from_prometheus(
            url=cluster['prometheus_url'],
            query=cluster['promql_query'],
            start=start_time.isoformat(),
            end=end_time.isoformat(),
            step='60s'
        )

        # Step 2: 预处理
        processed, _ = Preprocessor.preprocess_pipeline(raw_data)

        # Step 3: 异常检测
        result = DetectionEngine.run_detection(
            processed,
            scenario=cluster['scenario_type'],
            config={'threshold': 3.0}
        )

        # Step 4: 保存结果
        node_names = result.get('node_names', [])
        raw_scores = result.get('node_scores', result.get('fused_scores', []))
        anomaly_nodes = result.get('anomaly_nodes', [])

        # fused_scores may be dict {node_idx: list} or plain list
        if isinstance(raw_scores, dict):
            node_scores = []
            for i in range(len(node_names)):
                v = raw_scores.get(i, raw_scores.get(str(i), 0))
                if isinstance(v, (list, tuple)):
                    node_scores.append(float(max(v)) if v else 0.0)
                else:
                    node_scores.append(float(v))
        else:
            node_scores = []
            for v in raw_scores:
                if isinstance(v, (list, tuple)):
                    node_scores.append(float(max(v)) if v else 0.0)
                elif hasattr(v, '__float__'):
                    node_scores.append(float(v))
                else:
                    node_scores.append(0.0)

        scores_dict = {}
        for i, name in enumerate(node_names):
            if i < len(node_scores):
                score = node_scores[i]
                is_anomaly = name in anomaly_nodes
                models.insert('detection_results', {
                    'task_id': task_id,
                    'node_name': name,
                    'anomaly_score': round(float(score), 4),
                    'is_anomaly': 1 if is_anomaly else 0,
                    'detection_time': now.strftime('%Y-%m-%d %H:%M:%S'),
                })
                scores_dict[name] = float(score)

        # Step 5: 更新任务状态
        models.update('detection_tasks', {
            'status': 'completed',
            'n_nodes': len(node_names),
            'n_anomaly': len(anomaly_nodes),
            'max_score': round(max(node_scores) if node_scores else 0, 4),
            'finished_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }, {'task_id': task_id})

        # Step 6: 触发告警检查
        check_alert_rules(task_id, scores_dict, cluster_id=cluster_id)

    except Exception as e:
        models.update('detection_tasks', {
            'status': 'failed',
            'finished_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }, {'task_id': task_id})
        print(f"[Scheduler] 集群 {cluster['cluster_name']} 巡检失败: {e}")
