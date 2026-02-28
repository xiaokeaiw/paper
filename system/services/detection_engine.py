"""
检测引擎调度模块（集成 csad_at 模块）

负责根据用户配置的场景类型和算法参数，协调调用相应的检测算法，
并组织检测结果。支持两种检测场景：
1. 单指标多节点场景（第三章CSAD-AT框架）-- 使用 csad_at 模块
2. 多指标多节点场景（第四章双视角融合框架）-- 保留原有 algorithms/

单指标多节点场景的检测流程（来自 csad_at.pipeline）：
  三种方法(欧氏距离、自编码器、DBSCAN)各自产出 {node_idx: [scores]} 的时序异常分数,
  截断负值 + 全局 Min-Max 归一化到 [0, 1],
  加权融合三种归一化分数,
  融合分数 -> 全局时间线 -> I-SPOT 自适应阈值 -> 最终异常矩阵,
  从异常矩阵中提取异常节点和时间片段。

对应论文第五章 5.3 节
"""

import sys
import os
import numpy as np

# --- 将 csad_at 所在目录加入 sys.path ---
_current_dir = os.path.dirname(os.path.abspath(__file__))
_files_dir = os.path.abspath(os.path.join(_current_dir, '..', '..'))
if _files_dir not in sys.path:
    sys.path.insert(0, _files_dir)

from csad_at.euc_detector import run_euc_detector
from csad_at.ae_detector import run_ae_detector
from csad_at.dbscan_detector import run_dbscan_detector
from csad_at.pipeline import (
    clip_and_minmax,
    weighted_fusion,
    global_ispot_detect,
)

# 多指标场景仍使用原有的 DualPerspectiveFusion
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
    def _extract_segments_from_matrix(anomaly_matrix, curve_names,
                                      window_starts=None, window_ends=None):
        """
        从 csad_at 的异常矩阵 (n_windows, n_nodes) 中提取异常片段

        参数:
            anomaly_matrix: shape=(n_windows, n_nodes) 的二值矩阵
            curve_names: 节点名称列表
            window_starts: 窗口起始时间戳（可选）
            window_ends: 窗口结束时间戳（可选）

        返回:
            anomaly_nodes: 异常节点名称列表
            anomaly_segments: 异常片段列表
        """
        mat = np.array(anomaly_matrix)
        if mat.ndim == 1:
            mat = mat.reshape(-1, 1)
        if mat.size == 0:
            return [], []

        T, N = mat.shape
        anomaly_nodes = []
        anomaly_segments = []

        for ni in range(N):
            col = mat[:, ni]
            if col.sum() == 0:
                continue

            node_name = curve_names[ni] if ni < len(curve_names) else f'node_{ni}'
            anomaly_nodes.append(node_name)

            in_seg = False
            seg_start = 0
            for t in range(T):
                if col[t] == 1 and not in_seg:
                    seg_start = t
                    in_seg = True
                elif col[t] == 0 and in_seg:
                    seg = {
                        'node': node_name, 'node_idx': int(ni),
                        'win_start': int(seg_start), 'win_end': int(t),
                        'start': int(seg_start), 'end': int(t),
                        'duration': int(t - seg_start),
                    }
                    if window_starts is not None:
                        seg['start_time'] = str(window_starts[seg_start])
                    if window_ends is not None:
                        prev = max(0, t - 1)
                        seg['end_time'] = str(window_ends[prev])
                    anomaly_segments.append(seg)
                    in_seg = False
            if in_seg:
                seg = {
                    'node': node_name, 'node_idx': int(ni),
                    'win_start': int(seg_start), 'win_end': int(T),
                    'start': int(seg_start), 'end': int(T),
                    'duration': int(T - seg_start),
                }
                if window_starts is not None:
                    seg['start_time'] = str(window_starts[seg_start])
                if window_ends is not None:
                    prev = max(0, T - 1)
                    seg['end_time'] = str(window_ends[prev])
                anomaly_segments.append(seg)

        return anomaly_nodes, anomaly_segments

    @staticmethod
    def _extract_segments_from_labels(labels, node_names, window_size=1):
        """
        从集成决策的二值标签矩阵中提取异常片段（兼容旧接口）
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
            if node_labels.sum() == 0:
                continue

            node_name = node_names[ni] if ni < len(node_names) else f'node_{ni}'
            anomaly_nodes.append(node_name)

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
                        'end': int(min(t + window_size - 1,
                                       seg_start + window_size + (t - seg_start))),
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
                    'end': int(min(T + window_size - 1,
                                   seg_start + window_size + (T - seg_start))),
                    'duration': int(T - seg_start),
                })

        return anomaly_nodes, anomaly_segments

    @staticmethod
    def _extract_anomaly_segments(scores, node_names, threshold=3.0):
        """从时序异常分数中提取异常片段（后备方案）"""
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

    # ================================================================
    # 单指标多节点检测（CSAD-AT 框架，使用 csad_at 模块）
    # ================================================================

    @staticmethod
    def run_single_metric(data, config=None):
        """
        单指标多节点检测流程（CSAD-AT框架）

        使用 csad_at 模块中的三种检测器 + clip_and_minmax 归一化
        + weighted_fusion 加权融合 + global_ispot_detect 最终检测。

        流程：
        1. 将 numpy 数据 (T, N) 转换为 csad_at 期望的 curves 格式
        2. 三种方法各自产出 {node_idx: [scores]} 的偏离度分数
        3. 截断负值 + 全局 Min-Max 归一化到 [0, 1]
        4. 加权融合三种归一化分数
        5. 融合分数 -> 全局时间线 -> I-SPOT 自适应阈值 -> 最终异常矩阵
        6. 从异常矩阵提取异常节点和时间片段
        """
        if config is None:
            config = {}

        T, N = data.shape
        raw_window_size = config.get('window_size', 60)
        window_size = DetectionEngine._validate_window_size(T, raw_window_size)
        threshold = config.get('threshold', 3.0)
        methods = config.get('methods', ['euclidean', 'autoencoder', 'dbscan'])

        # csad_at 参数
        anomaly_ratio = config.get('anomaly_ratio', 0.0065)
        ispot_level = config.get('ispot_level', 0.98)
        ispot_t_update = config.get('ispot_t_update', 50)
        ispot_w_max = config.get('ispot_w_max', None)
        weights = config.get('weights', [1.0 / 3, 1.0 / 3, 1.0 / 3])

        if N < 2:
            return {
                'scenario': 'single_metric', 'methods': {},
                'ensemble': None, 'threshold': threshold,
                'anomaly_nodes': [], 'anomaly_segments': [],
                'window_size': window_size,
                'warning': '节点数不足，至少需要2个节点进行相似性比较',
            }

        n_windows_max = T - window_size + 1
        if n_windows_max < 1:
            return {
                'scenario': 'single_metric', 'methods': {},
                'ensemble': None, 'threshold': threshold,
                'anomaly_nodes': [], 'anomaly_segments': [],
                'window_size': window_size,
                'warning': f'数据长度({T})不足以执行滑动窗口检测(窗口={window_size})',
            }

        # 自动计算步长
        stride = _auto_stride(n_windows_max)
        step = stride

        print(f"[DetectionEngine] T={T}, N={N}, window={window_size}, "
              f"n_windows_max={n_windows_max}, step={step}")

        # --- 将 numpy (T, N) 转换为 csad_at 期望的 curves 格式 ---
        curves = [data[:, i].astype(np.float64) for i in range(N)]
        timestamps = np.arange(T)
        curve_names = [f'node_{i}' for i in range(N)]

        results = {
            'scenario': 'single_metric',
            'methods': {},
            'ensemble': None,
            'threshold': threshold,
            'window_size': window_size,
        }

        method_results = {}
        active_weights = []
        n_windows = None

        # 1. 欧氏距离检测
        if 'euclidean' in methods:
            try:
                euc_res = run_euc_detector(curves, timestamps,
                                           window_size, step)
                method_results['euclidean'] = euc_res
                n_windows = euc_res['n_windows']
                active_weights.append(weights[0] if len(weights) > 0 else 1.0)
                results['methods']['euclidean'] = {
                    'scores': euc_res['scores'],
                    'n_windows': euc_res['n_windows'],
                }
            except Exception as e:
                print(f"[DetectionEngine] 欧氏距离检测失败: {e}")

        # 2. 自编码器嵌入检测
        if 'autoencoder' in methods:
            try:
                ae_res = run_ae_detector(
                    curves, timestamps, window_size, step,
                    latent_dim=config.get('ae_latent_dim', 5),
                    epochs=config.get('ae_epochs', 50),
                    lr=config.get('ae_lr', 1e-3),
                )
                method_results['autoencoder'] = ae_res
                n_windows = ae_res['n_windows']
                active_weights.append(weights[1] if len(weights) > 1 else 1.0)
                results['methods']['autoencoder'] = {
                    'scores': ae_res['scores'],
                    'n_windows': ae_res['n_windows'],
                }
            except Exception as e:
                print(f"[DetectionEngine] 自编码器检测失败: {e}")

        # 3. DBSCAN密度检测
        if 'dbscan' in methods:
            try:
                db_res = run_dbscan_detector(
                    curves, timestamps, window_size, step,
                    k_neighbors=config.get('k_neighbors', 5),
                )
                method_results['dbscan'] = db_res
                n_windows = db_res['n_windows']
                active_weights.append(weights[2] if len(weights) > 2 else 1.0)
                results['methods']['dbscan'] = {
                    'scores': db_res['scores'],
                    'n_windows': db_res['n_windows'],
                }
            except Exception as e:
                print(f"[DetectionEngine] DBSCAN检测失败: {e}")

        if not method_results or n_windows is None:
            results['anomaly_nodes'] = []
            results['anomaly_segments'] = []
            results['warning'] = '所有检测方法均失败'
            return results

        # --- csad_at pipeline 流程 ---
        # 4. 截断 + Min-Max 归一化
        print("[DetectionEngine] 截断负值 + Min-Max 归一化...")
        normalized_scores = {}
        method_scores = []
        for name, res in method_results.items():
            normed = clip_and_minmax(res['scores'], N, n_windows)
            normalized_scores[name] = normed
            method_scores.append(normed)

        # 5. 加权融合
        print(f"[DetectionEngine] 加权融合 (权重: {active_weights})...")
        fused_scores = weighted_fusion(
            method_scores, active_weights, N, n_windows)

        # 6. 融合分数 -> 全局时间线 -> I-SPOT -> 最终检测
        print(f"[DetectionEngine] 全局 I-SPOT (q={anomaly_ratio}, "
              f"level={ispot_level}, t_update={ispot_t_update})...")
        fused_ispot = global_ispot_detect(
            fused_scores, N, n_windows, curve_names,
            anomaly_ratio=anomaly_ratio,
            level=ispot_level,
            t_update=ispot_t_update,
            w_max=ispot_w_max,
        )

        # 7. 提取异常节点和片段
        window_starts = None
        window_ends = None
        if method_results:
            first_res = next(iter(method_results.values()))
            window_starts = first_res.get('window_starts')
            window_ends = first_res.get('window_ends')

        anomaly_nodes, anomaly_segments = (
            DetectionEngine._extract_segments_from_matrix(
                fused_ispot['anomaly_matrix'],
                curve_names,
                window_starts=window_starts,
                window_ends=window_ends,
            )
        )

        # 构建集成结果（兼容旧格式）
        results['ensemble'] = {
            'anomaly_matrix': fused_ispot['anomaly_matrix'],
            'anomaly_nodes': fused_ispot['anomaly_nodes'],
            'anomaly_details': fused_ispot['anomaly_details'],
            'node_anomaly_counts': fused_ispot.get('node_anomaly_counts', {}),
            'ensemble_labels': fused_ispot['anomaly_matrix'].tolist(),
        }
        results['normalized_scores'] = normalized_scores
        results['fused_scores'] = fused_scores
        results['fused_ispot'] = fused_ispot
        results['anomaly_nodes'] = anomaly_nodes
        results['anomaly_segments'] = anomaly_segments
        results['n_windows'] = n_windows
        results['curve_names'] = curve_names

        print(f"[DetectionEngine] 检测完成: "
              f"{len(anomaly_nodes)} 个异常节点, "
              f"{len(anomaly_segments)} 个异常片段")

        return results

    # ================================================================
    # 多指标多节点检测（双视角融合框架，保留原有 algorithms/）
    # ================================================================

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

    # ================================================================
    # 统一检测入口
    # ================================================================

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
            # 单指标场景：异常节点和片段已在 run_single_metric 中提取
            # 补充时间戳映射
            if timestamps and result.get('anomaly_segments'):
                for seg in result['anomaly_segments']:
                    if 'start_time' not in seg:
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

            # 将 curve_names (node_0, node_1...) 映射回真实 node_names
            if (result.get('anomaly_nodes')
                    and result['anomaly_nodes']
                    and node_names):
                mapped_nodes = []
                for anode in result['anomaly_nodes']:
                    if anode.startswith('node_'):
                        try:
                            idx = int(anode.split('_')[1])
                            if idx < len(node_names):
                                mapped_nodes.append(node_names[idx])
                            else:
                                mapped_nodes.append(anode)
                        except (ValueError, IndexError):
                            mapped_nodes.append(anode)
                    else:
                        mapped_nodes.append(anode)
                result['anomaly_nodes'] = mapped_nodes

                if result.get('anomaly_segments'):
                    for seg in result['anomaly_segments']:
                        ni = seg.get('node_idx')
                        if ni is not None and ni < len(node_names):
                            seg['node'] = node_names[ni]

        elif result.get('scenario') == 'multi_metric':
            # 多指标场景：使用融合分数判定
            raw_sc = result.get('fused_scores', result.get('node_scores', []))
            # Handle dict or list with nested lists
            if isinstance(raw_sc, dict):
                scores = [float(max(raw_sc[k])) if isinstance(raw_sc[k], (list, tuple)) else float(raw_sc[k]) for k in sorted(raw_sc.keys(), key=lambda x: int(x) if str(x).isdigit() else 0)]
            else:
                scores = [float(max(v)) if isinstance(v, (list, tuple)) else float(v) for v in raw_sc]
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
