"""
基于曲线相似性的分布式集群异常检测系统 - Flask主应用

功能模块:
- 用户认证与权限管理
- 数据管理（文件上传 + Prometheus接入）
- 多种异常检测算法调度
- 集群常态化监控管理
- 三级告警管理
- 可视化仪表盘
- RESTful API接口

对应论文第五章
"""

import os
import json
import uuid
import hashlib
import traceback
from datetime import datetime
from functools import wraps

import numpy as np
from flask import Flask, request, jsonify, render_template, session

from config import Config
import models
from services.data_loader import DataLoader
from services.preprocessor import Preprocessor
from services.detection_engine import DetectionEngine
from services.alert_service import check_alert_rules, get_alert_stats

# 尝试导入调度器（可选依赖）
try:
    from services.scheduler import init_scheduler, update_cluster_job
    SCHEDULER_ENABLED = True
except ImportError:
    SCHEDULER_ENABLED = False

# 创建Flask应用
app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = Config.SECRET_KEY

# 确保上传目录存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# 内存缓存：存储已加载的数据和检测结果（用于手动检测场景）
data_cache = {}
result_cache = {}


# ==================== 工具函数 ====================

def hash_password(password):
    """SHA-256密码哈希"""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def login_required(f):
    """登录鉴权装饰器"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': '请先登录'}), 401
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """管理员权限装饰器"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': '请先登录'}), 401
        if session.get('role') != 'admin':
            return jsonify({'error': '需要管理员权限'}), 403
        return f(*args, **kwargs)
    return decorated


# ==================== 页面路由 ====================

@app.route('/')
def index():
    """主页面 - 单页应用入口"""
    return render_template('index.html')


# ==================== 认证API ====================

@app.route('/api/auth/login', methods=['POST'])
def login():
    """用户登录"""
    params = request.get_json()
    username = params.get('username', '')
    password = params.get('password', '')

    if not username or not password:
        return jsonify({'error': '用户名和密码不能为空'}), 400

    user = models.query_one('users', {'username': username})
    if not user or user['password_hash'] != hash_password(password):
        return jsonify({'error': '用户名或密码错误'}), 401

    if not user['is_active']:
        return jsonify({'error': '账户已被禁用'}), 403

    # 更新登录时间
    models.update('users', {
        'last_login': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }, {'user_id': user['user_id']})

    session['user_id'] = user['user_id']
    session['username'] = user['username']
    session['role'] = user['role']

    return jsonify({
        'message': '登录成功',
        'user': {
            'user_id': user['user_id'],
            'username': user['username'],
            'role': user['role'],
            'display_name': user['display_name'],
        }
    })


@app.route('/api/auth/logout', methods=['POST'])
def logout():
    """用户登出"""
    session.clear()
    return jsonify({'message': '已登出'})


@app.route('/api/auth/me', methods=['GET'])
@login_required
def get_current_user():
    """获取当前登录用户信息"""
    user = models.query_one('users', {'user_id': session['user_id']})
    if not user:
        session.clear()
        return jsonify({'error': '用户不存在'}), 401
    return jsonify({
        'user_id': user['user_id'],
        'username': user['username'],
        'role': user['role'],
        'display_name': user['display_name'],
    })


# ==================== 用户管理API ====================

@app.route('/api/users', methods=['GET'])
@admin_required
def list_users():
    """获取用户列表"""
    users = models.query_all('users')
    result = []
    for u in users:
        result.append({
            'user_id': u['user_id'],
            'username': u['username'],
            'display_name': u['display_name'],
            'role': u['role'],
            'is_active': u['is_active'],
            'last_login': u['last_login'],
            'created_at': u['created_at'],
        })
    return jsonify(result)


@app.route('/api/users', methods=['POST'])
@admin_required
def create_user():
    """创建用户"""
    params = request.get_json()
    username = params.get('username', '')
    password = params.get('password', '')
    display_name = params.get('display_name', username)
    role = params.get('role', 'user')

    if not username or not password:
        return jsonify({'error': '用户名和密码不能为空'}), 400

    existing = models.query_one('users', {'username': username})
    if existing:
        return jsonify({'error': '用户名已存在'}), 409

    user_id = models.insert('users', {
        'username': username,
        'password_hash': hash_password(password),
        'display_name': display_name,
        'role': role,
    })
    return jsonify({'message': '用户创建成功', 'user_id': user_id}), 201


@app.route('/api/users/<int:user_id>', methods=['PUT'])
@admin_required
def update_user(user_id):
    """更新用户信息"""
    params = request.get_json()
    update_data = {}
    if 'display_name' in params:
        update_data['display_name'] = params['display_name']
    if 'role' in params:
        update_data['role'] = params['role']
    if 'is_active' in params:
        update_data['is_active'] = 1 if params['is_active'] else 0
    if 'password' in params and params['password']:
        update_data['password_hash'] = hash_password(params['password'])

    if update_data:
        models.update('users', update_data, {'user_id': user_id})
    return jsonify({'message': '更新成功'})


@app.route('/api/users/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    """删除用户"""
    if user_id == session.get('user_id'):
        return jsonify({'error': '不能删除当前登录用户'}), 400
    models.delete('users', {'user_id': user_id})
    return jsonify({'message': '删除成功'})


# ==================== 数据管理API ====================

@app.route('/api/datasets', methods=['GET'])
@login_required
def list_datasets():
    """获取数据集列表"""
    datasets = models.query_all('datasets', order_by='uploaded_at DESC')
    return jsonify(datasets)


@app.route('/api/datasets/<int:dataset_id>', methods=['DELETE'])
@login_required
def delete_dataset(dataset_id):
    """删除数据集"""
    ds = models.query_one('datasets', {'dataset_id': dataset_id})
    if ds and ds.get('file_path') and os.path.exists(ds['file_path']):
        os.remove(ds['file_path'])
    models.delete('datasets', {'dataset_id': dataset_id})
    cache_key = f"ds_{dataset_id}"
    data_cache.pop(cache_key, None)
    return jsonify({'message': '删除成功'})


@app.route('/api/datasets/<int:dataset_id>/load', methods=['POST'])
@login_required
def load_dataset(dataset_id):
    """将已上传的数据集重新加载到内存缓存中（用于选择已有数据集进行检测）"""
    ds = models.query_one('datasets', {'dataset_id': dataset_id})
    if not ds:
        return jsonify({'error': '数据集不存在'}), 404

    cache_key = f"ds_{dataset_id}"

    # 如果已在缓存中，直接返回
    if cache_key in data_cache:
        return jsonify({
            'data_id': cache_key,
            'dataset_id': dataset_id,
            'name': ds['name'],
            'n_metrics': ds['n_metrics'],
            'n_nodes': ds['n_nodes'],
            'n_timestamps': ds['n_timestamps'],
        })

    # 从文件重新加载
    file_path = ds.get('file_path', '')
    if not file_path or not os.path.exists(file_path):
        return jsonify({'error': '数据文件不存在，可能已被清理'}), 404

    try:
        ext = file_path.rsplit('.', 1)[1].lower() if '.' in file_path else ''
        if ext == 'csv':
            raw_data = DataLoader.load_from_csv(file_path)
        elif ext == 'json':
            raw_data = DataLoader.load_from_json(file_path)
        else:
            return jsonify({'error': f'不支持的文件格式: {ext}'}), 400

        processed, preprocess_info = Preprocessor.preprocess_pipeline(raw_data)

        data_cache[cache_key] = {
            'raw': raw_data,
            'processed': processed,
            'preprocess_info': preprocess_info,
            'filename': ds['name'],
        }

        return jsonify({
            'data_id': cache_key,
            'dataset_id': dataset_id,
            'name': ds['name'],
            'n_metrics': ds['n_metrics'],
            'n_nodes': ds['n_nodes'],
            'n_timestamps': ds['n_timestamps'],
        })

    except Exception as e:
        return jsonify({'error': f'数据加载失败: {str(e)}'}), 500


@app.route('/api/algorithms', methods=['GET'])
def get_algorithms():
    """获取可用算法列表"""
    algorithms = {
        'single_metric': {
            'name': '单指标多节点检测（CSAD-AT框架）',
            'methods': {
                'euclidean': {'name': '欧氏距离相似性', 'params': {
                    'window_size': {'type': 'int', 'default': 60, 'desc': '滑动窗口大小'}
                }},
                'autoencoder': {'name': '自编码器嵌入相似性', 'params': {
                    'window_size': {'type': 'int', 'default': 60, 'desc': '滑动窗口大小'},
                    'ae_epochs': {'type': 'int', 'default': 50, 'desc': '训练轮数'}
                }},
                'dbscan': {'name': 'DBSCAN聚类相似性', 'params': {
                    'window_size': {'type': 'int', 'default': 60, 'desc': '滑动窗口大小'},
                    'dbscan_eps': {'type': 'float', 'default': 0.5, 'desc': 'DBSCAN邻域半径'},
                    'dbscan_min_samples': {'type': 'int', 'default': 3, 'desc': '最小样本数'}
                }}
            },
            'ensemble': {
                'name': '保守集成决策（I-SPOT + 逻辑与）',
                'params': {
                    'ispot_q': {'type': 'float', 'default': 0.001, 'desc': 'I-SPOT目标误报率'}
                }
            }
        },
        'multi_metric': {
            'name': '多指标多节点检测（双视角融合框架）',
            'params': {
                'w_num': {'type': 'float', 'default': 0.5, 'desc': '数值视角权重'},
                'w_shape': {'type': 'float', 'default': 0.5, 'desc': '形状视角权重'},
                'alphabet_size': {'type': 'int', 'default': 7, 'desc': 'SAX字母表大小'}
            }
        }
    }
    return jsonify(algorithms)


@app.route('/api/upload', methods=['POST'])
@login_required
def upload_file():
    """上传数据文件（CSV/JSON），保存到数据库并缓存"""
    if 'file' not in request.files:
        return jsonify({'error': '未找到上传文件'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '未选择文件'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': f'不支持的文件格式，允许: {", ".join(Config.ALLOWED_EXTENSIONS)}'}), 400

    data_id = str(uuid.uuid4())[:8]
    ext = file.filename.rsplit('.', 1)[1].lower()
    save_path = os.path.join(app.config['UPLOAD_FOLDER'], f'{data_id}.{ext}')
    file.save(save_path)

    try:
        if ext == 'csv':
            raw_data = DataLoader.load_from_csv(save_path)
        elif ext == 'json':
            raw_data = DataLoader.load_from_json(save_path)
        else:
            return jsonify({'error': f'暂不支持{ext}格式'}), 400

        processed, preprocess_info = Preprocessor.preprocess_pipeline(raw_data)

        n_metrics = len(processed)
        n_nodes = max((len(df.columns) for df in processed.values()), default=0)
        n_timestamps = max((len(df) for df in processed.values()), default=0)

        dataset_id = models.insert('datasets', {
            'name': file.filename,
            'source': 'upload',
            'file_path': save_path,
            'n_metrics': n_metrics,
            'n_nodes': n_nodes,
            'n_timestamps': n_timestamps,
            'uploaded_by': session.get('username', 'system'),
        })

        cache_key = f"ds_{dataset_id}"
        data_cache[cache_key] = {
            'raw': raw_data,
            'processed': processed,
            'preprocess_info': preprocess_info,
            'filename': file.filename,
        }

        summary = {
            'dataset_id': dataset_id,
            'data_id': cache_key,
            'filename': file.filename,
            'n_metrics': n_metrics,
            'n_nodes': n_nodes,
            'n_timestamps': n_timestamps,
            'metrics': [],
        }
        for name, df in processed.items():
            summary['metrics'].append({
                'name': name,
                'n_nodes': len(df.columns),
                'n_timestamps': len(df),
                'node_names': list(df.columns),
                'time_range': {
                    'start': str(df.index[0]),
                    'end': str(df.index[-1]),
                },
            })

        return jsonify(summary)

    except Exception as e:
        if os.path.exists(save_path):
            os.remove(save_path)
        return jsonify({'error': f'数据解析失败: {str(e)}'}), 400


@app.route('/api/prometheus', methods=['POST'])
@login_required
def load_prometheus():
    """从Prometheus API加载数据"""
    params = request.get_json()
    required = ['url', 'query', 'start', 'end']
    for field in required:
        if field not in params:
            return jsonify({'error': f'缺少必要参数: {field}'}), 400

    try:
        raw_data = DataLoader.load_from_prometheus(
            url=params['url'], query=params['query'],
            start=params['start'], end=params['end'],
            step=params.get('step', '60s'),
        )
        processed, preprocess_info = Preprocessor.preprocess_pipeline(raw_data)

        n_metrics = len(processed)
        n_nodes = max((len(df.columns) for df in processed.values()), default=0)
        n_timestamps = max((len(df) for df in processed.values()), default=0)

        dataset_id = models.insert('datasets', {
            'name': f"prometheus_{params['query'][:30]}",
            'source': 'prometheus',
            'n_metrics': n_metrics,
            'n_nodes': n_nodes,
            'n_timestamps': n_timestamps,
            'uploaded_by': session.get('username', 'system'),
        })

        cache_key = f"ds_{dataset_id}"
        data_cache[cache_key] = {
            'raw': raw_data, 'processed': processed,
            'preprocess_info': preprocess_info,
            'filename': f'prometheus_{params["query"][:20]}',
        }

        return jsonify({
            'dataset_id': dataset_id, 'data_id': cache_key,
            'source': 'prometheus', 'n_metrics': n_metrics,
            'n_nodes': n_nodes, 'n_timestamps': n_timestamps,
        })

    except Exception as e:
        return jsonify({'error': f'Prometheus数据获取失败: {str(e)}'}), 400


@app.route('/api/demo', methods=['GET'])
def load_demo():
    """加载演示数据"""
    raw_data = DataLoader.generate_demo_data(
        n_nodes=Config.DEMO_N_NODES,
        n_timestamps=Config.DEMO_N_TIMESTAMPS,
        n_anomaly_nodes=Config.DEMO_N_ANOMALY_NODES,
    )
    anomaly_info = raw_data.pop('_anomaly_info', {})
    processed, preprocess_info = Preprocessor.preprocess_pipeline(raw_data)

    data_id = 'demo'
    data_cache[data_id] = {
        'raw': raw_data, 'processed': processed,
        'preprocess_info': preprocess_info,
        'filename': 'demo_data', 'anomaly_info': anomaly_info,
    }

    summary = {'data_id': data_id, 'source': 'demo', 'anomaly_info': anomaly_info, 'metrics': []}
    for name, df in processed.items():
        summary['metrics'].append({
            'name': name, 'n_nodes': len(df.columns),
            'n_timestamps': len(df), 'node_names': list(df.columns),
        })
    return jsonify(summary)


# ==================== 检测API ====================

@app.route('/api/detect', methods=['POST'])
@login_required
def run_detection():
    """执行异常检测，结果写入数据库并触发告警"""
    params = request.get_json()
    data_id = params.get('data_id')

    if data_id not in data_cache:
        return jsonify({'error': '数据未找到，请先上传数据或选择已有数据集'}), 404

    cached = data_cache[data_id]
    processed = cached['processed']
    scenario = params.get('scenario', 'auto')
    config = params.get('config', {})

    task_id = models.insert('detection_tasks', {
        'cluster_id': params.get('cluster_id'),
        'task_type': 'manual',
        'scenario': scenario,
        'status': 'running',
        'data_source': 'upload' if data_id.startswith('ds_') else 'demo',
        'started_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    })

    try:
        result = DetectionEngine.run_detection(processed, scenario=scenario, config=config)

        node_names = result.get('node_names', [])
        node_scores = result.get('node_scores', result.get('fused_scores', []))
        anomaly_nodes = result.get('anomaly_nodes', [])

        scores_dict = {}
        for i, name in enumerate(node_names):
            if i < len(node_scores):
                score = float(node_scores[i])
                is_anomaly = name in anomaly_nodes
                models.insert('detection_results', {
                    'task_id': task_id,
                    'node_name': name,
                    'anomaly_score': round(score, 4),
                    'is_anomaly': 1 if is_anomaly else 0,
                    'detection_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                })
                scores_dict[name] = score

        models.update('detection_tasks', {
            'status': 'completed',
            'n_nodes': len(node_names),
            'n_anomaly': len(anomaly_nodes),
            'max_score': round(max(node_scores) if node_scores else 0, 4),
            'finished_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }, {'task_id': task_id})

        check_alert_rules(task_id, scores_dict)

        chart_data = {}
        for name, df in processed.items():
            chart_data[name] = {
                'timestamps': [str(t) for t in df.index],
                'nodes': {},
            }
            for col in df.columns:
                chart_data[name]['nodes'][col] = df[col].tolist()

        result['task_id'] = task_id
        result['chart_data'] = chart_data
        return jsonify(result)

    except Exception as e:
        traceback.print_exc()
        models.update('detection_tasks', {
            'status': 'failed',
            'finished_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }, {'task_id': task_id})
        return jsonify({'error': f'检测执行失败: {str(e)}'}), 500


@app.route('/api/detection/tasks', methods=['GET'])
@login_required
def list_detection_tasks():
    """获取检测任务列表"""
    tasks = models.query_all('detection_tasks', order_by='started_at DESC')
    return jsonify(tasks)


@app.route('/api/detection/tasks/<int:task_id>/results', methods=['GET'])
@login_required
def get_task_results(task_id):
    """获取某次检测的详细结果"""
    results = models.query_all('detection_results', where={'task_id': task_id})
    return jsonify(results)


@app.route('/api/data/<data_id>/preview', methods=['GET'])
@login_required
def preview_data(data_id):
    """预览已加载的数据"""
    if data_id not in data_cache:
        return jsonify({'error': '数据未找到'}), 404

    cached = data_cache[data_id]
    processed = cached['processed']
    preview = {}
    for name, df in processed.items():
        preview[name] = {
            'timestamps': [str(t) for t in df.index],
            'nodes': {},
        }
        for col in df.columns:
            preview[name]['nodes'][col] = df[col].tolist()

    return jsonify({
        'data_id': data_id,
        'filename': cached['filename'],
        'data': preview,
    })


# ==================== 集群管理API ====================

@app.route('/api/clusters', methods=['GET'])
@login_required
def list_clusters():
    """获取集群配置列表"""
    clusters = models.query_all('cluster_configs')
    return jsonify(clusters)


@app.route('/api/clusters', methods=['POST'])
@login_required
def create_cluster():
    """创建集群配置"""
    params = request.get_json()
    required = ['cluster_name', 'prometheus_url', 'promql_query']
    for field in required:
        if field not in params:
            return jsonify({'error': f'缺少参数: {field}'}), 400

    cluster_id = models.insert('cluster_configs', {
        'cluster_name': params['cluster_name'],
        'prometheus_url': params['prometheus_url'],
        'promql_query': params['promql_query'],
        'check_interval': params.get('check_interval', 5),
        'scenario_type': params.get('scenario_type', 'auto'),
        'is_active': 1 if params.get('is_active', True) else 0,
        'description': params.get('description', ''),
    })

    if SCHEDULER_ENABLED:
        cluster = models.query_one('cluster_configs', {'cluster_id': cluster_id})
        if cluster:
            update_cluster_job(cluster_id)

    return jsonify({'message': '集群创建成功', 'cluster_id': cluster_id}), 201


@app.route('/api/clusters/<int:cluster_id>', methods=['PUT'])
@login_required
def update_cluster(cluster_id):
    """更新集群配置"""
    params = request.get_json()
    update_data = {}
    for key in ['cluster_name', 'prometheus_url', 'promql_query',
                'check_interval', 'scenario_type', 'description']:
        if key in params:
            update_data[key] = params[key]
    if 'is_active' in params:
        update_data['is_active'] = 1 if params['is_active'] else 0

    if update_data:
        models.update('cluster_configs', update_data, {'cluster_id': cluster_id})
        if SCHEDULER_ENABLED:
            update_cluster_job(cluster_id)

    return jsonify({'message': '更新成功'})


@app.route('/api/clusters/<int:cluster_id>', methods=['DELETE'])
@login_required
def delete_cluster(cluster_id):
    """删除集群配置"""
    models.update('cluster_configs', {'is_active': 0}, {'cluster_id': cluster_id})
    if SCHEDULER_ENABLED:
        update_cluster_job(cluster_id)
    models.delete('cluster_configs', {'cluster_id': cluster_id})
    return jsonify({'message': '删除成功'})


# ==================== 告警管理API ====================

@app.route('/api/alerts/rules', methods=['GET'])
@login_required
def list_alert_rules():
    """获取告警规则列表"""
    rules = models.query_all('alert_rules')
    return jsonify(rules)


@app.route('/api/alerts/rules', methods=['POST'])
@login_required
def create_alert_rule():
    """创建告警规则"""
    params = request.get_json()
    rule_id = models.insert('alert_rules', {
        'rule_name': params.get('rule_name', ''),
        'level': params.get('level', 'info'),
        'condition_type': params.get('condition_type', 'score_threshold'),
        'threshold': params.get('threshold', 3.0),
        'notify_type': params.get('notify_type', 'system'),
        'notify_target': params.get('notify_target', ''),
        'is_active': 1 if params.get('is_active', True) else 0,
    })
    return jsonify({'message': '规则创建成功', 'rule_id': rule_id}), 201


@app.route('/api/alerts/rules/<int:rule_id>', methods=['PUT'])
@login_required
def update_alert_rule(rule_id):
    """更新告警规则"""
    params = request.get_json()
    update_data = {}
    for key in ['rule_name', 'level', 'condition_type', 'threshold',
                'notify_type', 'notify_target']:
        if key in params:
            update_data[key] = params[key]
    if 'is_active' in params:
        update_data['is_active'] = 1 if params['is_active'] else 0

    if update_data:
        models.update('alert_rules', update_data, {'rule_id': rule_id})
    return jsonify({'message': '更新成功'})


@app.route('/api/alerts/rules/<int:rule_id>', methods=['DELETE'])
@login_required
def delete_alert_rule(rule_id):
    """删除告警规则"""
    models.delete('alert_rules', {'rule_id': rule_id})
    return jsonify({'message': '删除成功'})


@app.route('/api/alerts/logs', methods=['GET'])
@login_required
def list_alert_logs():
    """获取告警日志"""
    logs = models.query_all('alert_logs', order_by='triggered_at DESC')
    return jsonify(logs)


@app.route('/api/alerts/logs/<int:log_id>/ack', methods=['POST'])
@login_required
def acknowledge_alert(log_id):
    """确认告警"""
    models.update('alert_logs', {
        'status': 'acknowledged',
        'acknowledged_by': session.get('username', ''),
        'acknowledged_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }, {'log_id': log_id})
    return jsonify({'message': '已确认'})


@app.route('/api/alerts/stats', methods=['GET'])
@login_required
def alert_stats():
    """获取告警统计"""
    return jsonify(get_alert_stats())


# ==================== 仪表盘API ====================

@app.route('/api/dashboard', methods=['GET'])
@login_required
def dashboard():
    """获取仪表盘统计数据"""
    stats = {
        'total_tasks': models.count('detection_tasks'),
        'completed_tasks': models.count('detection_tasks', {'status': 'completed'}),
        'total_datasets': models.count('datasets'),
        'active_clusters': models.count('cluster_configs', {'is_active': 1}),
        'total_alerts': models.count('alert_logs'),
        'pending_alerts': models.count('alert_logs', {'status': 'pending'}),
        'total_users': models.count('users'),
    }

    stats['recent_tasks'] = models.query_all(
        'detection_tasks', order_by='started_at DESC', limit=10
    )
    stats['recent_alerts'] = models.query_all(
        'alert_logs', order_by='triggered_at DESC', limit=5
    )

    return jsonify(stats)


# ==================== 启动 ====================

with app.app_context():
    models.init_db()

if SCHEDULER_ENABLED:
    with app.app_context():
        try:
            init_scheduler()
        except Exception as e:
            print(f"[Warning] 调度器启动失败: {e}")

if __name__ == '__main__':
    print("=" * 60)
    print("  基于曲线相似性的分布式集群异常检测系统")
    print("  访问地址: http://localhost:5000")
    print("  默认账号: admin / admin123")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=True)
