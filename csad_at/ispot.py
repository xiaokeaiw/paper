"""
I-SPOT (Inclusive SPOT) 自适应阈值算法

核心思想（区别于经典SPOT）：
1. 包容性极值建模策略：所有数据点都纳入训练数据池 D_t
2. 全局数据池：最大容量 W_max，FIFO 管理
3. 定期重估：每 T_update 步，基于 D_t 重新计算 t_0、拟合 GPD、得到 z_q

使用方式（关键）：
    所有节点所有窗口的分数拼接成一条时间序列，统一用一次 I-SPOT。
    因为 CSAD-AT 的核心是"跨节点比较"——同一个时间窗口内分数高的节点
    就是异常，所以需要一个全局统一阈值。

对应论文第三章 3.4 节
"""

import numpy as np
from collections import deque
from scipy.optimize import minimize


class ISPOT:
    """I-SPOT (Inclusive SPOT) 自适应阈值算法"""

    def __init__(self):
        pass

    def log_prob(self, y, gamma, sigma_recip):
        """GPD 对数似然函数"""
        sample_num = y.shape[0]
        temp = np.log(1 + (gamma * sigma_recip).reshape(-1, 1) *
                      y.reshape(1, -1)).sum(axis=1)
        sigma_recip = sigma_recip.copy()
        sigma_recip[sigma_recip == 0] = 1e-6
        ret = sample_num * np.log(sigma_recip) - (1 + 1 / gamma) * temp
        return ret

    def _compute_threshold(self, t0, gamma, sigma, q, nt, n):
        """z_q = t_0 + (sigma / xi) * [(n / N_t * q)^{-xi} - 1]"""
        if nt == 0 or n == 0:
            return t0 * 1.5
        temp = (q * n / nt) ** (-gamma)
        return t0 + sigma / gamma * (temp - 1)

    def _grimshaw(self, y, k=10, x0=None):
        """Grimshaw 方法求解 GPD 参数 (gamma=xi, sigma)"""
        def v(x):
            return 1 + np.log(
                1 + x.reshape(-1, 1) * y.reshape(1, -1)).mean(axis=1)

        def optimize_func(x):
            z = 1 + x.reshape(-1, 1) * y.reshape(1, -1)
            ux = (1 / z).mean(axis=1)
            vx = 1 + np.log(z).mean(axis=1)
            jac_u = -(y / np.square(z)).mean(axis=1)
            jac_v = (y / z).mean(axis=1)
            uv = ux * vx - 1
            target = np.square(uv).sum()
            jac = jac_u * vx + ux * jac_v
            return target, 2 * uv * jac

        if x0 is not None:
            assert isinstance(x0, np.ndarray) and x0.shape[0] == k
        else:
            x0 = np.zeros(k)

        y_min = y.min()
        y_max = y.max()
        y_mean = y.mean()

        if y_min <= 0:
            y_min = 1e-8
        if y_max <= 0:
            return 0.0, max(y_mean, 1e-6), x0

        low = -1 / y_max
        high = 2 * (y_mean - y_min) / max(y_min ** 2, 1e-10)
        mid = high * y_min / max(y_mean, 1e-10)

        candidate_x = np.zeros(k)
        try:
            solution = minimize(
                optimize_func, x0=x0[:k // 2],
                method='L-BFGS-B', jac=True,
                bounds=np.array([low, 0]).reshape(1, -1).repeat(
                    k // 2, axis=0))
            candidate_x[:k // 2] = solution.x

            solution = minimize(
                optimize_func, x0=x0[-k // 2:],
                method='L-BFGS-B', jac=True,
                bounds=np.array([mid, high]).reshape(1, -1).repeat(
                    k // 2, axis=0))
            candidate_x[-k // 2:] = solution.x
        except Exception:
            return 0.0, max(y_mean, 1e-6), x0

        gamma = v(candidate_x) - 1
        gamma[gamma == 0] = 1e-6
        sigma_recip = candidate_x / gamma
        log_prob = self.log_prob(y, gamma, sigma_recip)

        target_index = np.argmax(log_prob)
        return (gamma[target_index],
                1 / sigma_recip[target_index],
                candidate_x)

    def _fit_from_pool(self, pool_data, level, q, x0=None):
        """
        基于当前数据池重新估计参数

        1. t_0 = percentile(pool, level)
        2. Y = {s - t_0 | s > t_0}
        3. Grimshaw 拟合 GPD -> (gamma, sigma)
        4. z_q = threshold
        """
        pool = np.array(pool_data)
        n = len(pool)

        t0 = float(np.percentile(pool, level * 100))

        exceed_mask = pool > t0
        y = pool[exceed_mask] - t0
        nt = len(y)

        if nt < 3:
            return t0 * 1.5, t0, x0

        try:
            gamma, sigma, x0_new = self._grimshaw(y, x0=x0)
        except Exception:
            return t0 * 1.5, t0, x0

        z_q = self._compute_threshold(t0, gamma, sigma, q, nt, n)
        z_q = max(z_q, t0)

        return z_q, t0, x0_new

    def run(self, scores, anomaly_ratio=0.0085, initial_seq_ratio=0.25,
            level=0.98, w_max=None, t_update=50):
        """
        I-SPOT 主流程

        参数:
            scores: ndarray, 一维分数序列
                    （可以是单节点时序，也可以是所有节点拼接的全局序列）
            anomaly_ratio: 目标误报率 q
            initial_seq_ratio: 初始化序列占总长度的比例
            level: 初始阈值分位数水平
            w_max: 数据池最大容量（None=无上限）
            t_update: 重估间隔步数

        返回:
            dict: {
                'anomaly_flags': list of int, 0/1 标记
                'thresholds': list of float, z_q 序列
                't0_values': list of float, t_0 序列
                'anomaly_indices': list of int, 异常索引
            }
        """
        scores = np.array(scores, dtype=np.float64)
        total_len = len(scores)

        initial_seq_len = max(20, int(total_len * initial_seq_ratio))
        initial_seq_len = min(initial_seq_len, total_len - 1)

        if w_max is None:
            w_max = total_len

        # --- 初始化 ---
        data_pool = deque(
            maxlen=w_max if w_max < total_len else None)
        for val in scores[:initial_seq_len]:
            data_pool.append(float(val))

        x0 = None
        z_q, t0, x0 = self._fit_from_pool(
            list(data_pool), level, anomaly_ratio, x0)

        anomaly_flags = [0] * initial_seq_len
        thresholds = [z_q] * initial_seq_len
        t0_values = [t0] * initial_seq_len
        anomaly_indices = []

        steps_since_update = 0

        # --- 流式处理 ---
        for i in range(initial_seq_len, total_len):
            thresholds.append(z_q)
            t0_values.append(t0)

            if scores[i] > z_q:
                anomaly_flags.append(1)
                anomaly_indices.append(i)
            else:
                anomaly_flags.append(0)

            # 包容性更新：所有点都加入数据池
            data_pool.append(float(scores[i]))

            steps_since_update += 1
            if steps_since_update >= t_update:
                pool_list = list(data_pool)
                if len(pool_list) >= 20:
                    z_q_new, t0_new, x0_new = self._fit_from_pool(
                        pool_list, level, anomaly_ratio, x0)
                    z_q = z_q_new
                    t0 = t0_new
                    x0 = x0_new
                steps_since_update = 0

        return {
            'anomaly_flags': anomaly_flags,
            'thresholds': thresholds,
            't0_values': t0_values,
            'anomaly_indices': anomaly_indices,
            'initial_seq_len': initial_seq_len,
        }
