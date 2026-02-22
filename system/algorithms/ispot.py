"""
I-SPOT (Inclusive SPOT) 自适应阈值算法

核心思想：基于极值理论中的广义帕累托分布 (GPD) 对异常分数序列的尾部
进行建模，动态计算自适应阈值。

性能优化（相比原版）：
- GPD 参数不再逐步重新拟合，改为**定期批量重估计**
  （每 update_interval 步重新拟合一次，默认50步）
- 使用矩估计作为默认方法，仅在数据充足时才调用 MLE
- 大幅减少 scipy.stats.genpareto.fit 的调用次数

对应论文第三章 3.5.1 节
"""

import numpy as np


class ISPOT:
    """I-SPOT自适应阈值算法（性能优化版）"""

    def __init__(self, q=1e-3, init_window=200, level=0.98,
                 update_interval=50):
        """
        参数:
            q: 目标误报率（风险概率）
            init_window: 初始化窗口大小
            level: 初始阈值的分位数水平
            update_interval: GPD参数重估间隔（步数）
        """
        self.q = q
        self.init_window = init_window
        self.level = level
        self.update_interval = update_interval
        self.thresholds = []
        self._initialized = False
        self._t0 = None
        self._exceedances = []
        self._n_total = 0
        self._n_exceed = 0
        self._current_xi = 0.0
        self._current_sigma = 1.0
        self._steps_since_update = 0

    def _estimate_gpd_params(self, exceedances):
        """
        估计GPD参数 (xi, sigma)，使用矩估计（快速）
        """
        if len(exceedances) < 5:
            return 0.0, max(np.std(exceedances) if len(exceedances) > 1 else 1.0, 1e-6)

        exceedances = np.array(exceedances)
        exceedances = exceedances[exceedances > 0]

        if len(exceedances) < 5:
            return 0.0, 1e-6

        # 矩估计（比 MLE 快几个数量级）
        mean_e = exceedances.mean()
        var_e = exceedances.var()
        if var_e > 1e-10 and mean_e > 1e-10:
            xi = 0.5 * (mean_e ** 2 / var_e - 1)
            sigma = 0.5 * mean_e * (mean_e ** 2 / var_e + 1)
        else:
            xi, sigma = 0.0, max(mean_e, 1e-6)

        return float(np.clip(xi, -0.5, 0.5)), float(max(sigma, 1e-6))

    def initialize(self, initial_scores):
        """
        使用初始数据估计初始阈值和GPD参数
        """
        initial_scores = np.array(initial_scores)
        self._t0 = float(np.quantile(initial_scores, self.level))

        exceedances = initial_scores[initial_scores > self._t0] - self._t0
        self._exceedances = list(exceedances)
        self._n_total = len(initial_scores)
        self._n_exceed = len(exceedances)

        if len(self._exceedances) > 2:
            self._current_xi, self._current_sigma = self._estimate_gpd_params(
                self._exceedances
            )
            self._compute_threshold()
        else:
            self.thresholds.append(self._t0 * 1.5)

        self._initialized = True

    def _compute_threshold(self):
        """根据当前GPD参数计算自适应阈值"""
        if self._n_exceed == 0:
            self.thresholds.append(self._t0 * 1.5)
            return

        ratio = self._n_total / max(self._n_exceed * self.q, 1e-10)
        xi = self._current_xi
        sigma = self._current_sigma

        if abs(xi) < 1e-10:
            z = self._t0 + sigma * np.log(max(ratio, 1.0))
        else:
            z = self._t0 + (sigma / xi) * (max(ratio, 1.0) ** xi - 1)

        z = max(z, self._t0)
        self.thresholds.append(float(z))

    def update(self, score):
        """
        I-SPOT更新：处理新分数，定期重估GPD参数
        """
        if not self._initialized:
            raise RuntimeError("Must call initialize() before update()")

        current_threshold = self.thresholds[-1]
        is_anomaly = score > current_threshold

        self._n_total += 1

        if score > self._t0:
            exceedance = score - self._t0
            self._exceedances.append(exceedance)
            self._n_exceed += 1

        # 限制历史数据量
        max_exceedances = 500
        if len(self._exceedances) > max_exceedances:
            self._exceedances = self._exceedances[-max_exceedances:]

        self._steps_since_update += 1

        # 定期重新估计GPD参数（而非每步都拟合）
        if self._steps_since_update >= self.update_interval:
            if len(self._exceedances) > 5:
                self._current_xi, self._current_sigma = (
                    self._estimate_gpd_params(self._exceedances)
                )
            self._steps_since_update = 0

        # 用当前参数计算阈值
        self._compute_threshold()

        return current_threshold, is_anomaly

    def run(self, scores):
        """
        对完整的分数序列运行I-SPOT
        """
        scores = np.array(scores)

        init_size = min(self.init_window, len(scores) // 2)
        if init_size < 10:
            init_size = min(10, len(scores))
        self.initialize(scores[:init_size])

        thresholds = [self.thresholds[-1]] * init_size
        anomalies = [0] * init_size

        for t in range(init_size, len(scores)):
            threshold, is_anomaly = self.update(float(scores[t]))
            thresholds.append(threshold)
            anomalies.append(1 if is_anomaly else 0)

        return {
            'thresholds': thresholds,
            'anomalies': anomalies,
        }
