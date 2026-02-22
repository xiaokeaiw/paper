"""
检测引擎调度模块

负责根据用户配置的场景类型和算法参数，协调调用相应的检测算法，
并组织检测结果。支持两种检测场景：
1. 单指标多节点场景（第三章CSAD-AT框架）
2. 多指标多节点场景（第四章双视角融合框架）

单指标多节点场景的检测流程：
  三种方法(欧氏距离、自编码器、DBSCAN)各自产出 (T', N) 的时序异常分数,
  由 I-SPOT 为每种方法的每个节点计算自适应阈值,
  再通过保守集成(逻辑与)得到最终的 (T', N) 二值标签矩阵,
  最后从标签矩阵中提取异常时间片段。
  不存在"聚合单个曲线异常分数为节点分数"这一步。

对应论文第五章 5.3 节
"""

import numpy as np
from algorithms.euclidean import EuclideanDetector, MultiMetricEuclideanDetector
from algorithms.autoencoder import AutoEncoderDetector
from algorithms.dbscan_detector import DBSCANDetector
from algorithms.ispot import ISPOT
from algorithms.ensemble import ConservativeEnsemble
from algorithms.sax_improved import ImprovedSAXDetector
from algorithms.fusion import DualPerspectiveFusion


def _auto_stride(n_windows, target_samples=120):
    """
    根据窗口总数自动计算合理的滑动步长
    目标：采样点控制在 target_samples 左右，既保证精度又控制耗时
    """
    if n_windows <= target_samples:
        return 1
    return max(1, n_windows // target_samples)


class DetectionEngine:
    """异常检测引擎"""

    @staticmethod
    def _extract_segments_from_labels(labels, node_names, window_size=1):
        """
        从集成决策的二值标签矩阵中提取异常片段

        参数:
            labels: shape=(T', N) 的二值标签，1=异常，0=正常
            node_names: 节点名称列表
            window_size: 滑动窗口大小，用于映射回原始时间索引

        返回:
            anomaly_nodes: 被判定为异常的节点名称列表
            anomaly_segments: 异常片段列表，每项包含
                node, node_idx, start, end, duration
        """
        labels_arr = np.array(labels)
        if labels_arr.ndim == 1:
            labels_arr = labels_arr.reshape(-1, 1)
        if labels_arr.size == 0:
            return [], []

        T, N = labels_arr.shape
        anomaly_nodes = []
        anomaly_segments = []

        for ni in range(N):
            node_labels = labels_arr[:, ni]
            # 该节点是否有任何异常窗口
            if node_labels.sum() == 0:
                continue

            node_name = node_names[ni] if ni < len(node_names) else f'node_{ni}'
            anomaly_nodes.append(node_name)

            # 提取连续异常片段
            in_segment = False
            seg_start = 0
            for t in range(T):
                if node_labels[t] == 1 and not in_segment:
                    seg_start = t
                    in_segment = True
                elif node_labels[t] == 0 and in_segment:
                    anomaly_segments.append({
                        'node': node_name,
                        'node_idx': int(ni),
                        'win_start': int(seg_start),
                        'win_end': int(t),
                        'start': int(seg_start),
                        'end': int(min(t + window_size - 1, seg_start + window_size + (t - seg_start))),
                        'duration': int(t - seg_start),
                    })
                    in_segment = False
            if in_segment:
                anomaly_segments.append({
                    'node': node_name,
                    'node_idx': int(ni),
                    'win_start': int(seg_start),
                    'win_end': int(T),
                    'start': int(seg_start),
                    'end': int(min(T + window_size - 1, seg_start + window_size + (T - seg_start))),
                    'duration': int(T - seg_start),
                })

        return anomaly_nodes, anomaly_segments

    @staticmethod
    def _extract_anomaly_segments(scores, node_names, threshold=3.0):
        """从时序异常分数中提取异常片段（用于无集成决策时的后备方案）"""
        scores_arr = np.array(scores)
        if scores_arr.ndim == 1:
            scores_arr = scores_arr.reshape(-1, 1)
        if scores_arr.size == 0:
            return [], []

        T, N = scores_arr.shape
        node_max_scores = scores_arr.max(axis=0)
        anomaly_node_indices = np.where(node_max_scores > threshold)[0]
        anomaly_nodes = [node_names[i] for i in anomaly_node_indices] if node_names else []

        anomaly_segments = []
        for ni in anomaly_node_indices:
            node_name = node_names[ni] if node_names else f'node_{ni}'
            is_anomaly = scores_arr[:, ni] > threshold

            in_segment = False
            seg_start = 0
            for t in range(T):
                if is_anomaly[t] and not in_segment:
                    seg_start = t
                    in_segment = True
                elif not is_anomaly[t] and in_segment:
                    max_score = float(scores_arr[seg_start:t, ni].max())
                    anomaly_segments.append({
                        'node': node_name, 'node_idx': int(ni),
                        'start': int(seg_start), 'end': int(t),
                        'max_score': round(max_score, 4),
                        'duration': int(t - seg_start),
                    })
                    in_segment = False
            if in_segment:
                max_score = float(scores_arr[seg_start:T, ni].max())
                anomaly_segments.append({
                    'node': node_name, 'node_idx': int(ni),
                    'start': int(seg_start), 'end': int(T),
                    'max_score': round(max_score, 4),
                    'duration': int(T - seg_start),
                })

        return anomaly_nodes, anomaly_segments

    @staticmethod
    def _validate_window_size(data_length, window_size):
        """校验并自动调整窗口大小"""
        if window_size >= data_length:
            adjusted = max(data_length // 3, 5)
            adjusted = min(adjusted, data_length - 1)
            if adjusted < 3:
                adjusted = min(3, data_length - 1)
            print(f"[DetectionEngine] 窗口大小 {window_size} >= 数据长度 {data_length}，"
                  f"已自动调整为 {adjusted}")
            return max(adjusted, 1)
        return window_size

    @staticmethod
    def run_single_metric(data, config=None):
        """
        单指标多节点检测流程（CSAD-AT框架）

        流程：
        1. 三种方法各自产出 (T', N) 的时序异常分数矩阵
        2. I-SPOT 为每种方法每个节点计算自适应阈值
        3. 保守集成(逻辑与)得到 (T', N) 的二值标签
        4. 从标签矩阵提取异常时间片段

        不进行节点分数聚合。异常判定完全来自集成决策。
        """
        if config is None:
            config = {}

        T, N = data.shape
        raw_window_size = config.get('window_size', 60)
        window_size = DetectionEngine._validate_window_size(T, raw_window_size)
        threshold = config.get('threshold', 3.0)
        methods = config.get('methods', ['euclidean', 'autoencoder', 'dbscan'])

        if N < 2:
            return {
                'scenario': 'single_metric', 'methods': {},
                'ensemble': None, 'threshold': threshold,
                'anomaly_nodes': [], 'anomaly_segments': [],
                'window_size': window_size,
                'warning': '节点数不足，至少需要2个节点进行相似性比较',
            }

        n_windows = T - window_size + 1
        if n_windows < 1:
            return {
                'scenario': 'single_metric', 'methods': {},
                'ensemble': None, 'threshold': threshold,
                'anomaly_nodes': [], 'anomaly_segments': [],
                'window_size': window_size,
                'warning': f'数据长度({T})不足以执行滑动窗口检测(窗口={window_size})',
            }

        # 自动计算步长
        stride = _auto_stride(n_windows)
        print(f"[DetectionEngine] T={T}, N={N}, window={window_size}, "
              f"n_windows={n_windows}, stride={stride}")

        results = {
            'scenario': 'single_metric',
            'methods': {},
            'ensemble': None,
            'threshold': threshold,
            'window_size': window_size,
        }

        all_scores = []

        # 1. 欧氏距离检测
        if 'euclidean' in methods:
            try:
                detector = EuclideanDetector(
                    window_size=window_size, stride=stride
                )
                euc_result = detector.detect(data, threshold=threshold)
                results['methods']['euclidean'] = euc_result
                all_scores.append(np.array(euc_result['scores']))
            except Exception as e:
                print(f"[DetectionEngine] 欧氏距离检测失败: {e}")

        # 2. 自编码器嵌入检测
        if 'autoencoder' in methods:
            try:
                ae_detector = AutoEncoderDetector(
                    window_size=window_size,
                    hidden_dim=config.get('ae_hidden_dim', 32),
                    latent_dim=config.get('ae_latent_dim', 8),
                    epochs=config.get('ae_epochs', 30),
                    stride=stride,
                )
                train_size = max(data.shape[0] // 2, window_size + 1)
                train_size = min(train_size, data.shape[0])
                ae_detector.train(data[:train_size])
                ae_result = ae_detector.detect(data, threshold=threshold)
                results['methods']['autoencoder'] = ae_result
                all_scores.append(np.array(ae_result['scores']))
            except Exception as e:
                print(f"[DetectionEngine] 自编码器检测失败: {e}")

        # 3. DBSCAN聚类检测
        if 'dbscan' in methods:
            try:
                db_detector = DBSCANDetector(
                    window_size=window_size,
                    eps=config.get('dbscan_eps', 0.5),
                    min_samples=config.get('dbscan_min_samples', 3),
                    stride=stride,
                )
                db_result = db_detector.detect(data)
                results['methods']['dbscan'] = db_result
                all_scores.append(np.array(db_result['scores']))
            except Exception as e:
                print(f"[DetectionEngine] DBSCAN检测失败: {e}")

        # 4. I-SPOT自适应阈值 + 保守集成决策
        # 这是CSAD-AT框架的核心：通过集成决策直接得到异常标签
        if len(all_scores) > 1:
            try:
                min_len = min(s.shape[0] for s in all_scores)
                aligned_scores = [s[:min_len] for s in all_scores]

                ensemble = ConservativeEnsemble(
                    n_methods=len(aligned_scores),
                    q=config.get('ispot_q', 1e-3),
                    init_window=min(config.get('ispot_init_window', 200), min_len),
                )
                ensemble_result = ensemble.ensemble_decide(aligned_scores)
                results['ensemble'] = ensemble_result
            except Exception as e:
                print(f"[DetectionEngine] 集成决策失败: {e}")

        # 不再聚合节点分数。异常判定完全来自集成决策的标签矩阵。

        return results

    @staticmethod
    def run_multi_metric(data_dict, config=None):
        """多指标多节点检测流程（双视角融合框架）"""
        if config is None:
            config = {}

        fusion = DualPerspectiveFusion(
            w_num=config.get('w_num', 0.5),
            w_shape=config.get('w_shape', 0.5),
            metric_weights=config.get('metric_weights'),
            alphabet_size=config.get('alphabet_size', 7),
        )

        result = fusion.detect(data_dict)
        result['scenario'] = 'multi_metric'
        return result

    @staticmethod
    def run_detection(data_dict, scenario='auto', config=None):
        """统一检测入口"""
        if config is None:
            config = {}

        metric_data = {
            k: v for k, v in data_dict.items() if not k.startswith('_')
        }

        numpy_data = {}
        node_names = None
        timestamps = None

        for name, df in metric_data.items():
            if hasattr(df, 'values'):
                if node_names is None:
                    node_names = list(df.columns)
                if timestamps is None and hasattr(df, 'index'):
                    timestamps = [str(t) for t in df.index]
                numpy_data[name] = df.values
            else:
                numpy_data[name] = np.array(df)

        if not numpy_data:
            return {
                'error': '没有可用的数据进行检测',
                'node_names': [], 'timestamps': [],
                'n_nodes': 0, 'n_metrics': 0, 'metric_names': [],
                'anomaly_nodes': [], 'anomaly_segments': [],
            }

        if node_names is None:
            first_data = next(iter(numpy_data.values()))
            node_names = [f'node_{i}' for i in range(first_data.shape[1])]

        if scenario == 'auto':
            scenario = 'single' if len(numpy_data) == 1 else 'multi'

        if scenario == 'single':
            first_data = next(iter(numpy_data.values()))
            result = DetectionEngine.run_single_metric(first_data, config)
        else:
            result = DetectionEngine.run_multi_metric(numpy_data, config)

        result['node_names'] = node_names
        result['timestamps'] = timestamps
        result['n_nodes'] = len(node_names) if node_names else 0
        result['n_metrics'] = len(numpy_data)
        result['metric_names'] = list(numpy_data.keys())

        threshold = config.get('threshold', 3.0)
        result['threshold'] = threshold
        window_size = result.get('window_size', config.get('window_size', 60))

        # === 提取异常节点和异常片段 ===

        if result.get('scenario') == 'single_metric':
            # 单指标场景：优先使用集成决策标签
            if result.get('ensemble') and result['ensemble'].get('ensemble_labels'):
                anomaly_nodes, anomaly_segments = (
                    DetectionEngine._extract_segments_from_labels(
                        result['ensemble']['ensemble_labels'],
                        node_names,
                        window_size=window_size,
                    )
                )
                result['anomaly_nodes'] = anomaly_nodes
                result['anomaly_segments'] = anomaly_segments
            elif result.get('methods'):
                # 后备：只有一种方法时无法集成，用分数阈值判定
                first_method = next(iter(result['methods'].values()))
                if 'scores' in first_method and first_method['scores']:
                    anomaly_nodes, anomaly_segments = (
                        DetectionEngine._extract_anomaly_segments(
                            first_method['scores'], node_names, threshold
                        )
                    )
                    result['anomaly_nodes'] = anomaly_nodes
                    result['anomaly_segments'] = anomaly_segments

            # 为异常片段添加时间戳映射
            if timestamps and result.get('anomaly_segments'):
                for seg in result['anomaly_segments']:
                    ts_start = min(
                        seg['start'] + window_size - 1,
                        len(timestamps) - 1
                    )
                    ts_end = min(
                        seg['end'] + window_size - 1,
                        len(timestamps) - 1
                    )
                    ts_start = max(0, min(ts_start, len(timestamps) - 1))
                    ts_end = max(0, min(ts_end, len(timestamps) - 1))
                    seg['start_time'] = timestamps[ts_start]
                    seg['end_time'] = timestamps[ts_end]

        elif result.get('scenario') == 'multi_metric':
            # 多指标场景：使用融合分数判定
            scores = result.get('fused_scores', result.get('node_scores', []))
            anomaly_nodes = []
            for i, s in enumerate(scores):
                if s > threshold and node_names and i < len(node_names):
                    anomaly_nodes.append(node_names[i])
            result['anomaly_nodes'] = anomaly_nodes
            result['anomaly_segments'] = []

        if 'anomaly_nodes' not in result:
            result['anomaly_nodes'] = []
        if 'anomaly_segments' not in result:
            result['anomaly_segments'] = []

        return result
