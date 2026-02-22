"""
基于欧氏距离的数值相似性异常检测

核心思想：在滑动窗口内计算各节点时序曲线之间的欧氏距离，
距离均值经Z-score归一化后作为异常分数。偏离群体行为模式
越大的节点，其异常分数越高。

性能优化：
- 采用步长采样（stride）减少窗口数量
- 使用向量化 pdist 替代手写循环

对应论文第三章 3.3.1 节和第四章 4.3 节
"""

import numpy as np
from scipy.spatial.distance import pdist, squareform


class EuclideanDetector:
    """基于欧氏距离的曲线相似性异常检测器"""

    def __init__(self, window_size=60, stride=1):
        """
        参数:
            window_size: 滑动窗口大小（时间步数）
            stride: 滑动步长，stride>1 可大幅减少计算量
        """
        self.window_size = window_size
        self.stride = stride

    def compute_anomaly_scores(self, data):
        """
        基于滑动窗口计算每个节点在每个时间步的异常分数

        参数:
            data: numpy数组, shape=(T, N)

        返回:
            scores: numpy数组, shape=(n_output_windows, N)
        """
        T, N = data.shape
        n_windows = T - self.window_size + 1
        # 采样的窗口索引
        sample_indices = list(range(0, n_windows, self.stride))
        n_sampled = len(sample_indices)
        scores = np.zeros((n_sampled, N))

        for idx, t in enumerate(sample_indices):
            window = data[t:t + self.window_size, :]
            # pdist + squareform 一次性计算节点间距离矩阵
            distances = pdist(window.T, metric='euclidean')
            dist_matrix = squareform(distances)

            np.fill_diagonal(dist_matrix, 0)
            avg_distances = dist_matrix.sum(axis=1) / max(N - 1, 1)

            mu = avg_distances.mean()
            sigma = avg_distances.std()
            if sigma > 1e-10:
                scores[idx] = (avg_distances - mu) / sigma

        # 如果有stride采样，通过插值还原到完整时间轴
        if self.stride > 1 and n_sampled > 1:
            full_scores = np.zeros((n_windows, N))
            for n in range(N):
                full_scores[:, n] = np.interp(
                    np.arange(n_windows),
                    [i * self.stride for i in range(n_sampled)],
                    scores[:, n]
                )
            return full_scores

        return scores

    def detect(self, data, threshold=3.0):
        """
        执行异常检测
        """
        scores = self.compute_anomaly_scores(data)
        labels = (scores > threshold).astype(int)
        node_scores = scores.max(axis=0)

        return {
            'scores': scores.tolist(),
            'labels': labels.tolist(),
            'node_scores': node_scores.tolist(),
        }


class MultiMetricEuclideanDetector:
    """
    多指标欧氏距离检测器（第四章数值视角）

    对多个指标分别计算节点间欧氏距离，
    经Z-score归一化后进行加权融合
    """

    def __init__(self, weights=None):
        self.weights = weights

    def detect(self, multi_metric_data):
        metric_names = list(multi_metric_data.keys())
        N = None
        per_metric_scores = {}

        for name in metric_names:
            data = multi_metric_data[name]
            if N is None:
                N = data.shape[1]

            dist_matrix = squareform(pdist(data.T, metric='euclidean'))
            np.fill_diagonal(dist_matrix, 0)
            avg_distances = dist_matrix.sum(axis=1) / max(N - 1, 1)

            mu = avg_distances.mean()
            sigma = avg_distances.std()
            if sigma > 1e-10:
                normalized = (avg_distances - mu) / sigma
            else:
                normalized = np.zeros(N)

            per_metric_scores[name] = normalized

        if self.weights is None:
            w = {name: 1.0 / len(metric_names) for name in metric_names}
        else:
            w = self.weights

        fused = np.zeros(N)
        for name in metric_names:
            fused += w.get(name, 1.0 / len(metric_names)) * np.maximum(
                per_metric_scores[name], 0
            )

        return {
            'fused_scores': fused.tolist(),
            'per_metric_scores': {
                k: v.tolist() for k, v in per_metric_scores.items()
            },
        }
