"""
多视角保守集成决策模块

核心思想：采用逻辑与（AND）策略进行集成决策，即只有当所有检测方法
（欧氏距离、自编码器、DBSCAN）同时判定某节点为异常时，才最终确认该
节点为异常。这种保守策略牺牲了一定的召回率，但显著降低了误报率，
适合对误报敏感的生产环境。

决策公式:
    y_hat_t = I[AND_m(s_t^(m) > z_t^(m))]

其中 s_t^(m) 为第m种方法的异常分数，z_t^(m) 为对应的自适应阈值。

对应论文第三章 3.5.2 节
"""

import numpy as np
from .ispot import ISPOT


class ConservativeEnsemble:
    """多视角保守集成决策器"""

    def __init__(self, n_methods=3, q=1e-3, init_window=200):
        """
        参数:
            n_methods: 参与集成的检测方法数量
            q: I-SPOT的目标误报率
            init_window: I-SPOT初始化窗口大小
        """
        self.n_methods = n_methods
        self.q = q
        self.init_window = init_window

    def ensemble_decide(self, all_scores, all_thresholds=None):
        """
        执行保守集成决策

        参数:
            all_scores: 各方法的异常分数列表
                        [scores_method1, scores_method2, ...]
                        每个元素 shape=(T, N)
            all_thresholds: 各方法对应的阈值列表 (可选)
                            若为None，使用I-SPOT计算自适应阈值

        返回:
            dict: {
                'ensemble_labels': 集成决策标签 shape=(T, N),
                'per_method_labels': 各方法标签列表,
                'per_method_thresholds': 各方法阈值列表
            }
        """
        M = len(all_scores)
        T, N = np.array(all_scores[0]).shape

        per_method_labels = []
        per_method_thresholds = []

        for m in range(M):
            scores_m = np.array(all_scores[m])
            method_labels = np.zeros((T, N), dtype=int)
            method_thresholds = np.zeros((T, N))

            for n in range(N):
                node_scores = scores_m[:, n]

                if all_thresholds is not None and m < len(all_thresholds):
                    # 使用提供的阈值
                    thresh = all_thresholds[m]
                    if isinstance(thresh, (int, float)):
                        method_labels[:, n] = (node_scores > thresh).astype(int)
                        method_thresholds[:, n] = thresh
                    else:
                        thresh_array = np.array(thresh)
                        if thresh_array.ndim == 1:
                            method_labels[:, n] = (
                                node_scores > thresh_array
                            ).astype(int)
                            method_thresholds[:, n] = thresh_array
                else:
                    # 使用I-SPOT计算自适应阈值
                    ispot = ISPOT(
                        q=self.q, init_window=self.init_window
                    )
                    result = ispot.run(node_scores)
                    method_labels[:, n] = np.array(result['anomalies'])
                    method_thresholds[:, n] = np.array(result['thresholds'])

            per_method_labels.append(method_labels)
            per_method_thresholds.append(method_thresholds)

        # 保守集成：逻辑与 - 所有方法都判定为异常才确认
        ensemble_labels = np.ones((T, N), dtype=int)
        for method_labels in per_method_labels:
            ensemble_labels = ensemble_labels & method_labels

        return {
            'ensemble_labels': ensemble_labels.tolist(),
            'per_method_labels': [l.tolist() for l in per_method_labels],
            'per_method_thresholds': [
                t.tolist() for t in per_method_thresholds
            ],
        }
