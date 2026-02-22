"""
系统配置文件
"""

import os


class Config:
    """基础配置"""
    # Flask配置
    SECRET_KEY = os.environ.get('SECRET_KEY', 'csad-anomaly-detection-2024-secret')
    DEBUG = True

    # 数据库
    DATABASE = os.path.join(os.path.dirname(__file__), 'csad_system.db')

    # 文件上传配置
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    ALLOWED_EXTENSIONS = {'csv', 'json', 'xlsx'}

    # Session配置
    SESSION_TYPE = 'filesystem'
    PERMANENT_SESSION_LIFETIME = 86400  # 24小时

    # 算法默认参数
    DEFAULT_WINDOW_SIZE = 60
    DEFAULT_DBSCAN_EPS = 0.5
    DEFAULT_DBSCAN_MIN_SAMPLES = 3
    DEFAULT_ISPOT_Q = 1e-3
    DEFAULT_ISPOT_INIT_WINDOW = 200
    DEFAULT_SAX_ALPHABET_SIZE = 7
    DEFAULT_W_NUM = 0.5
    DEFAULT_W_SHAPE = 0.5

    # 演示数据配置
    DEMO_N_NODES = 15
    DEMO_N_TIMESTAMPS = 500
    DEMO_N_ANOMALY_NODES = 2

    # 告警配置
    ALERT_SUPPRESSION_MINUTES = 30  # 告警抑制窗口


class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False
