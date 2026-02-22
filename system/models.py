"""
数据库ORM模型定义

使用SQLite + 自定义ORM层实现轻量级数据持久化
对应论文第五章 5.1.3 数据库设计

表结构:
- users: 用户管理（认证与权限）
- cluster_configs: 集群配置（常态化监控）
- detection_tasks: 检测任务记录
- detection_results: 节点级检测结果
- alert_rules: 三级告警规则
- alert_logs: 告警日志
- datasets: 数据集管理
"""

import sqlite3
import hashlib
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'csad_system.db')


def get_db():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """初始化数据库表结构"""
    conn = get_db()
    c = conn.cursor()

    # 用户表
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        username VARCHAR(50) UNIQUE NOT NULL,
        password_hash VARCHAR(255) NOT NULL,
        display_name VARCHAR(100) DEFAULT '',
        role VARCHAR(20) DEFAULT 'user',
        is_active INTEGER DEFAULT 1,
        last_login DATETIME,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    # 集群配置表
    c.execute('''CREATE TABLE IF NOT EXISTS cluster_configs (
        cluster_id INTEGER PRIMARY KEY AUTOINCREMENT,
        cluster_name VARCHAR(100) NOT NULL,
        prometheus_url VARCHAR(255) NOT NULL,
        promql_query TEXT NOT NULL,
        check_interval INTEGER DEFAULT 5,
        scenario_type VARCHAR(20) DEFAULT 'auto',
        is_active INTEGER DEFAULT 1,
        description TEXT DEFAULT '',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    # 检测任务表
    c.execute('''CREATE TABLE IF NOT EXISTS detection_tasks (
        task_id INTEGER PRIMARY KEY AUTOINCREMENT,
        cluster_id INTEGER,
        task_type VARCHAR(20) DEFAULT 'manual',
        scenario VARCHAR(20),
        status VARCHAR(20) DEFAULT 'pending',
        data_source VARCHAR(50),
        n_nodes INTEGER,
        n_anomaly INTEGER DEFAULT 0,
        max_score REAL DEFAULT 0,
        started_at DATETIME,
        finished_at DATETIME,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (cluster_id) REFERENCES cluster_configs(cluster_id)
    )''')

    # 检测结果表
    c.execute('''CREATE TABLE IF NOT EXISTS detection_results (
        result_id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER NOT NULL,
        node_name VARCHAR(100) NOT NULL,
        anomaly_score REAL NOT NULL,
        is_anomaly INTEGER DEFAULT 0,
        detection_time DATETIME NOT NULL,
        FOREIGN KEY (task_id) REFERENCES detection_tasks(task_id)
    )''')

    # 告警规则表
    c.execute('''CREATE TABLE IF NOT EXISTS alert_rules (
        rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
        rule_name VARCHAR(100) DEFAULT '',
        level VARCHAR(20) DEFAULT 'info',
        condition_type VARCHAR(50) DEFAULT 'score_threshold',
        threshold REAL DEFAULT 3.0,
        notify_type VARCHAR(50) DEFAULT 'system',
        notify_target VARCHAR(255) DEFAULT '',
        is_active INTEGER DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    # 告警日志表
    c.execute('''CREATE TABLE IF NOT EXISTS alert_logs (
        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER,
        rule_id INTEGER,
        rule_name VARCHAR(100) DEFAULT '',
        level VARCHAR(20) DEFAULT 'info',
        node_name VARCHAR(100),
        anomaly_score REAL,
        cluster_id INTEGER,
        status VARCHAR(20) DEFAULT 'pending',
        acknowledged_by VARCHAR(50),
        acknowledged_at DATETIME,
        triggered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (task_id) REFERENCES detection_tasks(task_id),
        FOREIGN KEY (rule_id) REFERENCES alert_rules(rule_id)
    )''')

    # 数据集表
    c.execute('''CREATE TABLE IF NOT EXISTS datasets (
        dataset_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name VARCHAR(200) NOT NULL,
        source VARCHAR(50) DEFAULT 'upload',
        file_path VARCHAR(500),
        n_metrics INTEGER DEFAULT 1,
        n_nodes INTEGER DEFAULT 0,
        n_timestamps INTEGER DEFAULT 0,
        uploaded_by VARCHAR(50),
        uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    # 默认管理员
    c.execute("SELECT COUNT(*) FROM users WHERE username='admin'")
    if c.fetchone()[0] == 0:
        pwd_hash = hashlib.sha256('admin123'.encode()).hexdigest()
        c.execute(
            "INSERT INTO users (username, password_hash, display_name, role) VALUES (?, ?, ?, ?)",
            ('admin', pwd_hash, '系统管理员', 'admin')
        )

    # 默认告警规则
    c.execute("SELECT COUNT(*) FROM alert_rules")
    if c.fetchone()[0] == 0:
        rules = [
            ('信息级告警', 'info', 2.0, 'system'),
            ('警告级告警', 'warning', 3.0, 'system'),
            ('严重级告警', 'critical', 4.5, 'system'),
        ]
        for name, level, threshold, notify in rules:
            c.execute(
                "INSERT INTO alert_rules (rule_name, level, threshold, notify_type) VALUES (?, ?, ?, ?)",
                (name, level, threshold, notify)
            )

    conn.commit()
    conn.close()


# ==================== 便捷查询函数 ====================

def query_all(table, where=None, order_by=None, limit=None):
    """通用查询，返回字典列表"""
    conn = get_db()
    sql = f"SELECT * FROM {table}"
    params = []
    if where:
        conditions = [f"{k} = ?" for k in where]
        sql += " WHERE " + " AND ".join(conditions)
        params = list(where.values())
    if order_by:
        sql += f" ORDER BY {order_by}"
    if limit:
        sql += f" LIMIT {limit}"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def query_one(table, where):
    """查询单条记录"""
    results = query_all(table, where, limit=1)
    return results[0] if results else None


def insert(table, data):
    """插入记录，返回自增ID"""
    conn = get_db()
    keys = ', '.join(data.keys())
    placeholders = ', '.join(['?'] * len(data))
    sql = f"INSERT INTO {table} ({keys}) VALUES ({placeholders})"
    cursor = conn.execute(sql, list(data.values()))
    conn.commit()
    last_id = cursor.lastrowid
    conn.close()
    return last_id


def update(table, data, where):
    """更新记录"""
    conn = get_db()
    set_clause = ', '.join([f"{k} = ?" for k in data])
    where_clause = ' AND '.join([f"{k} = ?" for k in where])
    sql = f"UPDATE {table} SET {set_clause} WHERE {where_clause}"
    conn.execute(sql, list(data.values()) + list(where.values()))
    conn.commit()
    conn.close()


def delete(table, where):
    """删除记录"""
    conn = get_db()
    where_clause = ' AND '.join([f"{k} = ?" for k in where])
    sql = f"DELETE FROM {table} WHERE {where_clause}"
    conn.execute(sql, list(where.values()))
    conn.commit()
    conn.close()


def count(table, where=None):
    """计数查询"""
    conn = get_db()
    sql = f"SELECT COUNT(*) FROM {table}"
    params = []
    if where:
        conditions = [f"{k} = ?" for k in where]
        sql += " WHERE " + " AND ".join(conditions)
        params = list(where.values())
    result = conn.execute(sql, params).fetchone()[0]
    conn.close()
    return result
