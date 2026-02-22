"""
数值与形状双视角融合模块

核心思想：将基于欧氏距离的数值异常分数与基于改进SAX的形状异常分数
进行加权融合，综合两个互补视角的检测结果，实现对不同类型异常的全面覆盖。

融合公式:
    s_i^final = w_num * s_i^num + w_shape * s_i^shape
    其中 w_num + w_shape = 1

对应论文第四章 4.5 节
"""

import numpy as np
from .euclidean import MultiMetricEuclideanDetector
from .sax_improved import ImprovedSAXDetector


class DualPerspectiveFusion:
    """数值与形状双视角融合检测器"""

    def __init__(self, w_num=0.5, w_shape=0.5, metric_weights=None,
                 alphabet_size=7):
        """
        参数:
            w_num: 数值视角权重
            w_shape: 形状视角权重
            metric_weights: 各指标权重（用于数值视角的多指标融合）
            alphabet_size: SAX字母表大小
        """
        assert abs(w_num + w_shape - 1.0) < 1e-6, \
            "w_num + w_shape must equal 1.0"
        self.w_num = w_num
        self.w_shape = w_shape
        self.num_detector = MultiMetricEuclideanDetector(
            weights=metric_weights
        )
        self.shape_detector = ImprovedSAXDetector(
            alphabet_size=alphabet_size
        )

    def detect(self, multi_metric_data, shape_metric_data=None):
        """
        执行双视角融合异常检测

        参数:
            multi_metric_data: dict, {metric_name: numpy数组 shape=(T, N)}
                              用于数值视角检测
            shape_metric_data: dict, {metric_name: numpy数组 shape=(T, N)}
                              用于形状视角检测，若为None则使用同一数据

        返回:
            dict: {
                'fused_scores': 融合后各节点异常分数,
                'numerical_scores': 数值视角分数,
                'shape_scores': 形状视角分数,
                'per_metric_details': 各指标详细分数,
                'node_ranking': 异常分数排名
            }
        """
        if shape_metric_data is None:
            shape_metric_data = multi_metric_data

        # 数值视角检测
        num_result = self.num_detector.detect(multi_metric_data)
        num_scores = np.array(num_result['fused_scores'])

        # 形状视角检测：对各指标分别做SAX，再融合
        N = len(num_scores)
        shape_scores_all = []
        per_metric_shape = {}

        for name, data in shape_metric_data.items():
            result = self.shape_detector.detect(data)
            metric_shape = np.array(result['shape_scores'])
            shape_scores_all.append(np.maximum(metric_shape, 0))
            per_metric_shape[name] = metric_shape.tolist()

        # 形状分数取各指标平均
        if shape_scores_all:
            shape_scores = np.mean(shape_scores_all, axis=0)
        else:
            shape_scores = np.zeros(N)

        # 归一化两个视角的分数到可比范围
        if num_scores.max() > 0:
            num_normalized = num_scores / num_scores.max()
        else:
            num_normalized = num_scores

        if shape_scores.max() > 0:
            shape_normalized = shape_scores / shape_scores.max()
        else:
            shape_normalized = shape_scores

        # 加权融合
        fused = self.w_num * num_normalized + self.w_shape * shape_normalized

        ranking = np.argsort(-fused).tolist()

        return {
            'fused_scores': fused.tolist(),
            'numerical_scores': num_scores.tolist(),
            'shape_scores': shape_scores.tolist(),
            'per_metric_numerical': num_result['per_metric_scores'],
            'per_metric_shape': per_metric_shape,
            'node_ranking': ranking,
        }
