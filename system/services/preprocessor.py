"""
数据预处理模块

包含缺失值处理、时间戳对齐和数据归一化三个核心功能，
为后续的异常检测算法提供干净、标准化的输入数据。

对应论文第五章 5.1 节（数据预处理阶段）和第三章 3.2 节
"""

import numpy as np
import pandas as pd


class Preprocessor:
    """数据预处理器"""

    @staticmethod
    def interpolate_missing(df, method='linear', max_gap=5):
        """
        缺失值填充

        策略：
        - 短时缺失（gap <= max_gap）：线性插值
        - 长时缺失：标记为NaN或剔除该节点

        参数:
            df: pandas DataFrame
            method: 插值方法 ('linear', 'nearest', 'ffill')
            max_gap: 最大允许插值间隔

        返回:
            df_filled: 填充后的DataFrame
            dropped_nodes: 被剔除的节点列表
        """
        dropped_nodes = []
        df_filled = df.copy()

        for col in df_filled.columns:
            # 计算最长连续缺失段
            is_null = df_filled[col].isnull()
            if is_null.any():
                null_groups = is_null.ne(is_null.shift()).cumsum()
                max_consecutive = is_null.groupby(null_groups).sum().max()

                if max_consecutive > max_gap:
                    # 长时缺失：剔除该节点
                    dropped_nodes.append(col)
                    continue

            # 线性插值填充短时缺失
            df_filled[col] = df_filled[col].interpolate(method=method)
            # 头尾可能无法插值，用前填/后填处理
            df_filled[col] = df_filled[col].bfill().ffill()

        # 剔除长时缺失的节点
        if dropped_nodes:
            df_filled = df_filled.drop(columns=dropped_nodes)

        return df_filled, dropped_nodes

    @staticmethod
    def align_timestamps(df, interval='60s'):
        """
        时间戳对齐

        将不规则采样的数据重采样到固定时间间隔，
        确保不同节点的数据在时间维度上严格对齐。

        参数:
            df: pandas DataFrame, index为DatetimeIndex
            interval: 目标采样间隔

        返回:
            df_aligned: 对齐后的DataFrame
        """
        if not isinstance(df.index, pd.DatetimeIndex):
            try:
                df.index = pd.to_datetime(df.index)
            except Exception:
                return df

        # 重采样到固定间隔，使用均值聚合
        df_aligned = df.resample(interval).mean()
        # 插值填补重采样后的缺失
        df_aligned = df_aligned.interpolate(method='linear')
        df_aligned = df_aligned.bfill().ffill()

        return df_aligned

    @staticmethod
    def normalize(df, method='zscore'):
        """
        数据归一化

        参数:
            df: pandas DataFrame
            method: 归一化方法
                - 'zscore': Z-score标准化 (x-mu)/sigma
                - 'minmax': Min-Max归一化到[0,1]
                - 'robust': 基于中位数和IQR的鲁棒归一化

        返回:
            df_normalized: 归一化后的DataFrame
            stats: 归一化参数（用于反归一化）
        """
        df_normalized = df.copy()
        stats = {}

        if method == 'zscore':
            for col in df_normalized.columns:
                mu = df_normalized[col].mean()
                sigma = df_normalized[col].std()
                stats[col] = {'mean': mu, 'std': sigma}
                if sigma > 1e-10:
                    df_normalized[col] = (df_normalized[col] - mu) / sigma
                else:
                    df_normalized[col] = 0

        elif method == 'minmax':
            for col in df_normalized.columns:
                vmin = df_normalized[col].min()
                vmax = df_normalized[col].max()
                stats[col] = {'min': vmin, 'max': vmax}
                rng = vmax - vmin
                if rng > 1e-10:
                    df_normalized[col] = (df_normalized[col] - vmin) / rng
                else:
                    df_normalized[col] = 0

        elif method == 'robust':
            for col in df_normalized.columns:
                median = df_normalized[col].median()
                q25 = df_normalized[col].quantile(0.25)
                q75 = df_normalized[col].quantile(0.75)
                iqr = q75 - q25
                stats[col] = {'median': median, 'iqr': iqr}
                if iqr > 1e-10:
                    df_normalized[col] = (
                        df_normalized[col] - median
                    ) / iqr
                else:
                    df_normalized[col] = 0

        return df_normalized, stats

    @staticmethod
    def preprocess_pipeline(data_dict, interval='60s',
                            normalize_method='zscore'):
        """
        完整预处理流水线

        参数:
            data_dict: {metric_name: DataFrame}
            interval: 时间对齐间隔
            normalize_method: 归一化方法

        返回:
            processed: {metric_name: 预处理后的DataFrame}
            info: 预处理信息（被剔除的节点等）
        """
        processed = {}
        info = {'dropped_nodes': {}, 'stats': {}}

        for metric_name, df in data_dict.items():
            if metric_name.startswith('_'):
                continue

            # Step 1: 时间戳对齐
            df_aligned = Preprocessor.align_timestamps(df, interval)

            # Step 2: 缺失值填充
            df_filled, dropped = Preprocessor.interpolate_missing(df_aligned)
            info['dropped_nodes'][metric_name] = dropped

            # Step 3: 归一化
            df_normalized, stats = Preprocessor.normalize(
                df_filled, normalize_method
            )
            info['stats'][metric_name] = stats

            processed[metric_name] = df_normalized

        return processed, info
