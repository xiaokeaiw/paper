"""
DBSCAN 密度视角 - 可达距离偏离度分数

核心思路：
  在每个滑动窗口内，计算所有节点曲线之间的欧氏距离矩阵，
  然后基于 DBSCAN 的密度可达性概念计算每个节点的异常程度。

  具体做法：
  1. 计算每个节点的 k 近邻距离（第 k 个最近邻的距离）
  2. 计算局部可达密度 (Local Reachability Density, LRD)
  3. 异常分数 = 节点的 k 近邻距离 - 窗口全局平均 k 近邻距离

  即"该节点在密度层面偏离群体的程度"。
  k 近邻距离大意味着该节点周围比较稀疏，说明它远离多数节点。

  不做 Z-score，保留原始距离偏离度。

对应论文第三章 3.3 节
"""

import numpy as np
from tqdm import tqdm


def compute_dbscan_deviation_scores(window_curves, k_neighbors=5):
    """
    计算单个窗口内各节点的密度偏离度分数

    参数:
        window_curves: list of ndarray, 每个元素 shape=(window_size,)
        k_neighbors: k 近邻数

    返回:
        deviation_scores: ndarray, shape=(N,)
    """
    n = len(window_curves)
    if n <= 1:
        return np.zeros(n)

    # 欧氏距离矩阵（向量化计算）
    curves_array = np.array(window_curves)  # (N, W)
    norms_sq = np.sum(curves_array ** 2, axis=1)
    dot_products = curves_array @ curves_array.T
    dist_sq = norms_sq[:, None] + norms_sq[None, :] - 2 * dot_products
    dist_sq = np.maximum(dist_sq, 0)
    dist_matrix = np.sqrt(dist_sq)

    k = min(k_neighbors, n - 1)

    # 每个节点的 k 近邻距离
    # 排序距离矩阵的每一行（第0个是自身=0，取第k个）
    sorted_dists = np.sort(dist_matrix, axis=1)
    kth_distances = sorted_dists[:, k]  # (N,)

    # 偏离度 = 节点的 k 近邻距离 - 全局平均 k 近邻距离
    global_mean_kth = kth_distances.mean()
    deviation_scores = kth_distances - global_mean_kth

    return deviation_scores


def run_dbscan_detector(curves, timestamps, window_size=60, step=30,
                        k_neighbors=5):
    """
    对完整时间序列运行 DBSCAN 密度偏离度检测

    参数:
        curves: list of ndarray, 每个节点的完整时序
        timestamps: ndarray, 时间戳
        window_size: 滑动窗口大小
        step: 步长
        k_neighbors: k 近邻数

    返回:
        dict: 检测结果
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
                      total=total_windows, desc="[DBSCAN] 滑动窗口"):
        end = start + window_size
        results['window_starts'].append(timestamps[start])
        results['window_ends'].append(timestamps[end - 1])

        window_curves = [curve[start:end].astype(np.float64)
                         for curve in curves]

        deviation = compute_dbscan_deviation_scores(
            window_curves, k_neighbors)

        for i in range(n_nodes):
            results['scores'][i].append(float(deviation[i]))

    results['n_windows'] = len(results['window_starts'])
    results['n_nodes'] = n_nodes
    return results
