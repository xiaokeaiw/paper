"""
欧氏距离视角 - 距离偏离度分数

核心思路：
  在每个滑动窗口内，计算所有节点曲线之间的欧氏距离矩阵，
  然后得到每个节点的"平均距离"（该节点与其他所有节点的距离均值）。

  异常分数 = 节点平均距离 - 窗口全局平均距离

  即"该节点相对于整体的距离偏离度"。正值越大表示该节点与群体偏离越远。

  注意：这里不做 Z-score 标准化，保留原始距离量纲的偏离度，
  以便后续 min-max 归一化 + I-SPOT 能利用尾部极值特征。

对应论文第三章 3.2 节
"""

import numpy as np
from tqdm import tqdm


def compute_euc_deviation_scores(window_curves):
    """
    计算单个窗口内各节点的欧氏距离偏离度分数

    参数:
        window_curves: list of ndarray, 每个元素是一个节点在该窗口内的时序片段
                       len = N (节点数), 每个 shape = (window_size,)

    返回:
        deviation_scores: ndarray, shape=(N,), 每个节点的距离偏离度
    """
    n = len(window_curves)
    if n <= 1:
        return np.zeros(n)

    # 计算欧氏距离矩阵
    curves_array = np.array(window_curves)  # (N, W)
    # 利用向量化: ||a-b||^2 = ||a||^2 + ||b||^2 - 2*a.b
    norms_sq = np.sum(curves_array ** 2, axis=1)  # (N,)
    dot_products = curves_array @ curves_array.T     # (N, N)
    dist_sq = norms_sq[:, None] + norms_sq[None, :] - 2 * dot_products
    dist_sq = np.maximum(dist_sq, 0)  # 数值安全
    dist_matrix = np.sqrt(dist_sq)

    # 每个节点的平均距离（排除自身）
    node_avg_distances = dist_matrix.sum(axis=1) / (n - 1)

    # 窗口全局平均距离
    global_mean = node_avg_distances.mean()

    # 偏离度 = 节点平均距离 - 全局平均距离
    deviation_scores = node_avg_distances - global_mean

    return deviation_scores


def run_euc_detector(curves, timestamps, window_size=60, step=30):
    """
    对完整时间序列运行欧氏距离偏离度检测

    参数:
        curves: list of ndarray, 每个元素是一个节点的完整时序, shape=(T,)
        timestamps: ndarray, 时间戳序列, shape=(T,)
        window_size: 滑动窗口大小
        step: 窗口滑动步长

    返回:
        dict: {
            'scores': dict, {node_idx: list of float},
            'window_starts': list,
            'window_ends': list,
            'n_windows': int,
            'n_nodes': int,
        }
    """
    T = len(timestamps)
    n_nodes = len(curves)
    total_windows = max(1, (T - window_size) // step)

    results = {
        'scores': {i: [] for i in range(n_nodes)},
        'window_starts': [],
        'window_ends': [],
    }

    for start in tqdm(range(0, T - window_size, step),
                      total=total_windows, desc="[EUC] 滑动窗口"):
        end = start + window_size
        results['window_starts'].append(timestamps[start])
        results['window_ends'].append(timestamps[end - 1])

        # 提取窗口数据
        window_curves = [curve[start:end].astype(np.float64) for curve in curves]

        # 计算偏离度分数
        deviation = compute_euc_deviation_scores(window_curves)

        for i in range(n_nodes):
            results['scores'][i].append(float(deviation[i]))

    results['n_windows'] = len(results['window_starts'])
    results['n_nodes'] = n_nodes
    return results
