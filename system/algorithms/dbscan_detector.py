"""
基于DBSCAN聚类的密度相似性异常检测

核心思想：利用DBSCAN算法在滑动窗口内对节点时序曲线进行聚类，
基于密度可达性将节点划分为核心点、边界点和噪声点。

性能优化：
- 支持 stride 步长采样，大幅减少 DBSCAN 调用次数
- 自适应 eps：根据距离矩阵分布自动调整

对应论文第三章 3.3.3 节
"""

import numpy as np
from sklearn.cluster import DBSCAN
from scipy.spatial.distance import pdist, squareform


class DBSCANDetector:
    """基于DBSCAN聚类的异常检测器"""

    def __init__(self, window_size=60, eps=0.5, min_samples=3, stride=1):
        """
        参数:
            window_size: 滑动窗口大小
            eps: DBSCAN邻域半径参数（若为'auto'则自适应）
            min_samples: 核心点最小邻域样本数
            stride: 滑动步长
        """
        self.window_size = window_size
        self.eps = eps
        self.min_samples = min_samples
        self.stride = stride

    def detect_window(self, window_data):
        """
        对单个窗口内的数据执行DBSCAN聚类
        """
        N = window_data.shape[1]

        if N < 2:
            return np.zeros(N, dtype=int), np.zeros(N)

        features = window_data.T  # (N, window_size)
        dist_matrix = squareform(pdist(features, metric='euclidean'))

        # 自适应 eps：使用距离分布的中位数
        eps = self.eps
        if eps == 'auto' or eps <= 0:
            upper_tri = dist_matrix[np.triu_indices(N, k=1)]
            if len(upper_tri) > 0:
                eps = float(np.median(upper_tri) * 0.8)
            else:
                eps = 1.0

        clustering = DBSCAN(
            eps=eps,
            min_samples=min(self.min_samples, max(N - 1, 1)),
            metric='precomputed'
        ).fit(dist_matrix)

        cluster_labels = clustering.labels_

        # 异常分数计算
        anomaly_scores = np.zeros(N)
        noise_mask = cluster_labels == -1
        anomaly_scores[noise_mask] = 1.0

        for label in set(cluster_labels):
            if label == -1:
                continue
            members = np.where(cluster_labels == label)[0]
            if len(members) > 1:
                cluster_center = features[members].mean(axis=0)
                for idx in members:
                    dist_to_center = np.linalg.norm(
                        features[idx] - cluster_center
                    )
                    anomaly_scores[idx] = dist_to_center

        if anomaly_scores.max() > 0:
            anomaly_scores = anomaly_scores / anomaly_scores.max()

        return cluster_labels, anomaly_scores

    def detect(self, data):
        """
        基于滑动窗口执行DBSCAN异常检测（带stride优化）
        """
        T, N = data.shape
        n_windows = T - self.window_size + 1
        sample_indices = list(range(0, n_windows, self.stride))
        n_sampled = len(sample_indices)

        sampled_scores = np.zeros((n_sampled, N))
        all_cluster_labels = []

        for idx, t in enumerate(sample_indices):
            window = data[t:t + self.window_size, :]
            cluster_labels, window_scores = self.detect_window(window)
            sampled_scores[idx] = window_scores
            all_cluster_labels.append(cluster_labels.tolist())

        # 插值还原完整时间轴
        if self.stride > 1 and n_sampled > 1:
            scores = np.zeros((n_windows, N))
            for n in range(N):
                scores[:, n] = np.interp(
                    np.arange(n_windows),
                    [i * self.stride for i in range(n_sampled)],
                    sampled_scores[:, n]
                )
        else:
            scores = sampled_scores

        labels = (scores > 0.5).astype(int)
        node_scores = scores.max(axis=0)

        return {
            'scores': scores.tolist(),
            'labels': labels.tolist(),
            'node_scores': node_scores.tolist(),
            'cluster_labels': all_cluster_labels,
        }
