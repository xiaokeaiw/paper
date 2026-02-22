"""
告警规则匹配与通知分发服务

支持三级告警: info(信息) / warning(警告) / critical(严重)
对应论文第五章 5.3.6 告警管理模块
"""

import threading
from datetime import datetime, timedelta

try:
    import requests as req_lib
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

import models

SUPPRESS_MINUTES = 30


def check_alert_rules(task_id, scores_dict, cluster_id=None):
    """
    检查告警规则并生成告警记录

    参数:
        task_id: 检测任务ID
        scores_dict: {node_name: anomaly_score}
        cluster_id: 集群ID（可选）
    """
    rules = models.query_all('alert_rules', where={'is_active': 1})
    now = datetime.now()
    alerts_created = []

    for node_name, score in scores_dict.items():
        for rule in rules:
            if score >= rule['threshold']:
                # 告警抑制检查
                if _is_suppressed(node_name, rule['level']):
                    continue

                log_id = models.insert('alert_logs', {
                    'task_id': task_id,
                    'rule_id': rule['rule_id'],
                    'rule_name': rule['rule_name'],
                    'level': rule['level'],
                    'node_name': node_name,
                    'anomaly_score': round(score, 4),
                    'cluster_id': cluster_id,
                    'status': 'pending',
                    'triggered_at': now.strftime('%Y-%m-%d %H:%M:%S'),
                })

                alerts_created.append({
                    'log_id': log_id,
                    'level': rule['level'],
                    'node': node_name,
                    'score': score,
                })

                # 异步通知
                if rule['notify_type'] != 'system' and rule['notify_target']:
                    msg = f"[{rule['level'].upper()}] 节点 {node_name} 异常分数 {score:.4f} 超过阈值 {rule['threshold']}"
                    threading.Thread(
                        target=_send_notification,
                        args=(log_id, rule['notify_type'], rule['notify_target'], msg),
                        daemon=True
                    ).start()

    return alerts_created


def _is_suppressed(node_name, level):
    """检查是否在告警抑制窗口内"""
    conn = models.get_db()
    suppress_since = (datetime.now() - timedelta(minutes=SUPPRESS_MINUTES)).strftime('%Y-%m-%d %H:%M:%S')
    cursor = conn.execute(
        "SELECT COUNT(*) FROM alert_logs WHERE node_name=? AND level=? AND triggered_at>?",
        (node_name, level, suppress_since)
    )
    count = cursor.fetchone()[0]
    conn.close()
    return count > 0


def _send_notification(log_id, method, target, message):
    """发送告警通知"""
    try:
        if method == 'webhook' and REQUESTS_AVAILABLE:
            req_lib.post(target, json={
                "msgtype": "markdown",
                "markdown": {"content": f"**集群异常告警**\n\n{message}"}
            }, timeout=10)
    except Exception as e:
        print(f"[Alert] 通知发送失败: {e}")


def get_alert_stats():
    """获取告警统计数据"""
    conn = models.get_db()

    # 各级别告警数
    level_counts = {}
    for level in ['info', 'warning', 'critical']:
        cursor = conn.execute("SELECT COUNT(*) FROM alert_logs WHERE level=?", (level,))
        level_counts[level] = cursor.fetchone()[0]

    # 待处理告警
    cursor = conn.execute("SELECT COUNT(*) FROM alert_logs WHERE status='pending'")
    pending = cursor.fetchone()[0]

    # 最近24小时
    since = (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
    cursor = conn.execute("SELECT COUNT(*) FROM alert_logs WHERE triggered_at>?", (since,))
    recent_24h = cursor.fetchone()[0]

    conn.close()
    return {
        'level_counts': level_counts,
        'pending': pending,
        'recent_24h': recent_24h,
        'total': sum(level_counts.values()),
    }
