"""
Classic SPOT (Streaming Peaks-over-Threshold) Algorithm

Key difference from I-SPOT:
  - Only exceedances (points above t0) are used to update the GPD model
  - Anomalies are NOT added to the data pool (exclusive strategy)
  - This is the standard POT approach from Siffer et al. (KDD 2017)

Used for comparison with I-SPOT in Section 3.2.
"""

import numpy as np
from collections import deque
from scipy.optimize import minimize


class SPOT:
    """Classic SPOT streaming threshold algorithm"""

    def __init__(self):
        pass

    def log_prob(self, y, gamma, sigma_recip):
        """GPD log-likelihood"""
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
        """Grimshaw method for GPD parameter estimation"""
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
        # Guard against divide-by-zero
        if sigma_recip[target_index] == 0:
            return 0.0, max(y_mean, 1e-6), candidate_x
        return (gamma[target_index],
                1 / sigma_recip[target_index],
                candidate_x)

    def _fit_from_pool(self, pool_data, level, q, x0=None):
        """Fit GPD from data pool"""
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
        Classic SPOT main loop

        Key difference from I-SPOT:
          - Only NON-anomaly points are added to the data pool
          - Exceedances above z_q are excluded from model updates

        Parameters / Returns: same as ISPOT.run()
        """
        scores = np.asarray(scores).flatten().astype(np.float64)
        total_len = len(scores)

        initial_seq_len = max(20, int(total_len * initial_seq_ratio))
        initial_seq_len = min(initial_seq_len, total_len - 1)

        if w_max is None:
            w_max = total_len

        # --- Initialization phase ---
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

        # --- Streaming phase ---
        for i in range(initial_seq_len, total_len):
            thresholds.append(z_q)
            t0_values.append(t0)

            if scores[i] > z_q:
                anomaly_flags.append(1)
                anomaly_indices.append(i)
                # Classic SPOT: do NOT add anomalies to pool
            else:
                anomaly_flags.append(0)
                # Only normal points enter the pool
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
