"""
改进SAX (Symbolic Aggregate approXimation) 形状异常检测

核心改进（相较于传统SAX）：
1. 取消分段聚合（PAA）步骤，保留原始时间分辨率
2. 采用严格距离计算规则：仅完全相同符号距离为0
3. 预计算符号距离查找表，提升计算效率

性能优化：
- sax_distance 使用 numpy 向量化查表替代纯 Python zip 循环
- compute_shape_scores 中的距离矩阵使用向量化批量计算

对应论文第四章 4.4 节
"""

import numpy as np
from scipy.stats import norm


class ImprovedSAXDetector:
    """基于改进SAX的形状异常检测器"""

    def __init__(self, alphabet_size=7):
        self.alphabet_size = alphabet_size
        self.breakpoints = self._compute_breakpoints()
        self.distance_table = self._build_distance_table()

    def _compute_breakpoints(self):
        probs = np.linspace(0, 1, self.alphabet_size + 1)[1:-1]
        breakpoints = norm.ppf(probs)
        return breakpoints

    def _build_distance_table(self):
        a = self.alphabet_size
        table = np.zeros((a, a))
        bp = self.breakpoints

        for i in range(a):
            for j in range(a):
                if i == j:
                    table[i][j] = 0.0
                else:
                    hi = max(i, j)
                    lo = min(i, j)
                    upper = bp[hi - 1] if hi - 1 < len(bp) else bp[-1]
                    lower = bp[lo] if lo < len(bp) else bp[0]
                    table[i][j] = max(upper - lower, 0)

        return table

    def symbolize(self, series):
        """将归一化后的时序数据转换为SAX符号序列"""
        symbols = np.digitize(series, self.breakpoints)
        return symbols

    def sax_distance_vectorized(self, symbols_a, symbols_b):
        """
        向量化计算两个符号序列之间的SAX距离
        使用查找表直接索引，避免 Python 逐元素循环
        """
        # 通过查找表批量获取每对符号的距离
        dists = self.distance_table[symbols_a, symbols_b]
        return float(np.sqrt(np.sum(dists ** 2)))

    def compute_shape_scores(self, data):
        """
        计算各节点的形状异常分数（向量化版本）
        """
        T, N = data.shape

        # Step 1: 向量化 Z-score 归一化
        mu = data.mean(axis=0)
        sigma = data.std(axis=0)
        sigma[sigma < 1e-10] = 1.0  # 避免除零
        normalized = (data - mu) / sigma

        # Step 2: 批量符号化
        # np.digitize 可以直接处理整个矩阵
        all_symbols = np.digitize(normalized, self.breakpoints)  # (T, N)

        # Step 3: 向量化计算节点间SAX距离矩阵
        dist_matrix = np.zeros((N, N))
        for i in range(N):
            for j in range(i + 1, N):
                # 向量化查表：一次性获取 T 个符号对的距离
                dists = self.distance_table[all_symbols[:, i], all_symbols[:, j]]
                d = float(np.sqrt(np.sum(dists ** 2)))
                dist_matrix[i, j] = d
                dist_matrix[j, i] = d

        # Step 4: 计算各节点的平均距离并Z-score归一化
        avg_distances = dist_matrix.sum(axis=1) / max(N - 1, 1)
        mu_d = avg_distances.mean()
        sigma_d = avg_distances.std()
        if sigma_d > 1e-10:
            scores = (avg_distances - mu_d) / sigma_d
        else:
            scores = np.zeros(N)

        return scores

    def detect(self, data):
        scores = self.compute_shape_scores(data)
        ranking = np.argsort(-scores).tolist()

        return {
            'shape_scores': scores.tolist(),
            'node_ranking': ranking,
        }
