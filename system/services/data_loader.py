"""
数据加载模块

支持多种数据接入方式：
1. CSV文件上传：适用于离线分析场景
2. JSON文件上传：支持结构化数据输入
3. Prometheus API：对接生产环境监控系统

统一输出格式:
    {metric_name: pandas.DataFrame(columns=node_names, index=timestamps)}
"""

import os
import json
import numpy as np
import pandas as pd

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class DataLoader:
    """统一数据加载器"""

    @staticmethod
    def _smart_to_datetime(series):
        """
        智能转换时间列，自动识别Unix时间戳（秒/毫秒/纳秒）和字符串格式

        参数:
            series: pandas Series，时间列

        返回:
            转换后的 DatetimeIndex
        """
        # 如果已经是datetime类型，直接返回
        if pd.api.types.is_datetime64_any_dtype(series):
            return pd.to_datetime(series)

        # 尝试转换为数值
        try:
            numeric_vals = pd.to_numeric(series, errors='coerce')
            if numeric_vals.notna().all():
                # 全是数字，判断是Unix秒、毫秒还是纳秒
                sample = float(numeric_vals.iloc[0])
                if sample > 1e18:
                    # 纳秒级 (> 10^18)
                    return pd.to_datetime(numeric_vals, unit='ns')
                elif sample > 1e15:
                    # 微秒级 (> 10^15)
                    return pd.to_datetime(numeric_vals, unit='us')
                elif sample > 1e12:
                    # 毫秒级 (> 10^12)
                    return pd.to_datetime(numeric_vals, unit='ms')
                elif sample > 1e9:
                    # 秒级 Unix 时间戳 (> 10^9, 即 2001年以后)
                    return pd.to_datetime(numeric_vals, unit='s')
                else:
                    # 可能是年份数字或其他，尝试当字符串解析
                    pass
        except (ValueError, TypeError):
            pass

        # 非数值或数值太小，当字符串解析
        try:
            return pd.to_datetime(series)
        except Exception:
            # 都失败了，用整数索引
            return pd.RangeIndex(len(series))

    @staticmethod
    def load_from_csv(file_path, timestamp_col=None):
        """
        从CSV文件加载数据

        支持两种格式：
        1. 宽表格式：第一列为时间戳，其余列为各节点数据
        2. 长表格式：包含timestamp, node, value列

        参数:
            file_path: CSV文件路径
            timestamp_col: 时间戳列名（自动检测）

        返回:
            dict: {metric_name: DataFrame}
        """
        df = pd.read_csv(file_path)

        # 自动检测时间戳列
        if timestamp_col is None:
            for col in df.columns:
                if col.lower() in ('timestamp', 'time', 'datetime', 'date',
                                   '时间', '时间戳'):
                    timestamp_col = col
                    break

        # 判断数据格式
        if 'node' in df.columns and 'value' in df.columns:
            # 长表格式 -> 透视为宽表
            return DataLoader._parse_long_format(df, timestamp_col)
        else:
            # 宽表格式
            return DataLoader._parse_wide_format(df, timestamp_col)

    @staticmethod
    def _parse_wide_format(df, timestamp_col):
        """解析宽表格式CSV"""
        if timestamp_col and timestamp_col in df.columns:
            # 使用智能时间转换（自动识别Unix时间戳）
            df[timestamp_col] = DataLoader._smart_to_datetime(df[timestamp_col])
            df = df.set_index(timestamp_col)
        elif df.columns[0].lower() in ('timestamp', 'time', 'datetime', 'date',
                                        '时间', '时间戳'):
            col_name = df.columns[0]
            df[col_name] = DataLoader._smart_to_datetime(df[col_name])
            df = df.set_index(col_name)
        else:
            # 第一列可能就是时间列但名字不在列表中
            # 检查第一列是否看起来像时间戳（纯数字且值很大）
            first_col = df.columns[0]
            try:
                first_val = pd.to_numeric(df[first_col].iloc[0], errors='coerce')
                if pd.notna(first_val) and first_val > 1e9:
                    # 可能是Unix时间戳
                    df[first_col] = DataLoader._smart_to_datetime(df[first_col])
                    df = df.set_index(first_col)
            except (ValueError, TypeError):
                pass

        # 确保所有数据列为数值型
        numeric_df = df.select_dtypes(include=[np.number])

        if numeric_df.empty and not df.empty:
            # 尝试强制转换
            for col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            numeric_df = df.dropna(axis=1, how='all')

        # 如果没有指标区分，整体作为单指标
        metric_name = 'default_metric'
        return {metric_name: numeric_df}

    @staticmethod
    def _parse_long_format(df, timestamp_col):
        """解析长表格式CSV"""
        results = {}

        # 检测是否有指标列
        metric_col = None
        for col in df.columns:
            if col.lower() in ('metric', 'indicator', '指标'):
                metric_col = col
                break

        ts_col = timestamp_col or 'timestamp'

        if metric_col:
            for metric_name, group in df.groupby(metric_col):
                pivot = group.pivot(
                    index=ts_col,
                    columns='node',
                    values='value'
                )
                pivot.index = DataLoader._smart_to_datetime(pivot.index.to_series())
                results[metric_name] = pivot
        else:
            pivot = df.pivot(
                index=ts_col,
                columns='node',
                values='value'
            )
            pivot.index = DataLoader._smart_to_datetime(pivot.index.to_series())
            results['default_metric'] = pivot

        return results

    @staticmethod
    def load_from_json(file_path):
        """
        从JSON文件加载数据

        支持格式:
        {
            "metric_name": {
                "timestamps": [...],
                "nodes": {
                    "node_1": [...],
                    "node_2": [...]
                }
            }
        }

        参数:
            file_path: JSON文件路径

        返回:
            dict: {metric_name: DataFrame}
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            raw = json.load(f)

        results = {}

        # 检测是否为多指标格式
        if isinstance(raw, dict):
            first_value = next(iter(raw.values()))
            if isinstance(first_value, dict) and 'nodes' in first_value:
                # 多指标格式
                for metric_name, metric_data in raw.items():
                    ts_raw = metric_data.get(
                        'timestamps',
                        range(len(next(iter(metric_data['nodes'].values()))))
                    )
                    timestamps = DataLoader._smart_to_datetime(pd.Series(ts_raw))
                    df = pd.DataFrame(
                        metric_data['nodes'], index=timestamps
                    )
                    results[metric_name] = df
            elif isinstance(first_value, list):
                # 简单格式：{node_name: [values]}
                timestamps = pd.RangeIndex(len(first_value))
                df = pd.DataFrame(raw, index=timestamps)
                results['default_metric'] = df

        return results

    @staticmethod
    def load_from_prometheus(url, query, start, end, step='60s'):
        """
        从Prometheus API加载数据

        参数:
            url: Prometheus服务器地址
            query: PromQL查询表达式
            start: 开始时间 (ISO格式或时间戳)
            end: 结束时间
            step: 采样间隔

        返回:
            dict: {metric_name: DataFrame}
        """
        if not REQUESTS_AVAILABLE:
            raise ImportError("requests library is required for Prometheus")

        api_url = f"{url.rstrip('/')}/api/v1/query_range"
        params = {
            'query': query,
            'start': start,
            'end': end,
            'step': step,
        }

        response = requests.get(api_url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        if data['status'] != 'success':
            raise ValueError(
                f"Prometheus query failed: {data.get('error', 'Unknown')}"
            )

        results = {}
        metric_data = {}

        for result in data['data']['result']:
            # 提取节点标识
            labels = result['metric']
            node_name = labels.get(
                'instance', labels.get('node', labels.get('pod', 'unknown'))
            )
            metric_name = labels.get('__name__', 'prometheus_metric')

            timestamps = [float(v[0]) for v in result['values']]
            values = [float(v[1]) for v in result['values']]

            if metric_name not in metric_data:
                metric_data[metric_name] = {'timestamps': timestamps}
            metric_data[metric_name][node_name] = values

        for metric_name, data_dict in metric_data.items():
            timestamps = pd.to_datetime(
                data_dict.pop('timestamps'), unit='s'
            )
            df = pd.DataFrame(data_dict, index=timestamps)
            results[metric_name] = df

        return results if results else {'prometheus_metric': pd.DataFrame()}

    @staticmethod
    def generate_demo_data(n_nodes=15, n_timestamps=500, n_anomaly_nodes=2,
                           seed=42):
        """
        生成演示用模拟数据

        模拟真实YARN集群RPC Router连接数的特征：
        - 基础信号：无规律大幅波动（随机游走+突变跳变），而非周期性
        - 正常节点：紧密跟随基础信号，个体偏差极小（负载均衡效应）
        - 异常节点：在特定时段显著偏离群体（幅度偏离或形状偏离）
        - 异常占比约8%，分散在多个短片段中

        参数:
            n_nodes: 节点数
            n_timestamps: 时间步数
            n_anomaly_nodes: 异常节点数
            seed: 随机种子

        返回:
            dict: {metric_name: DataFrame, _anomaly_info: {...}}
        """
        np.random.seed(seed)
        timestamps = pd.date_range('2024-01-01', periods=n_timestamps, freq='1min')
        node_names = [f'node_{i+1:02d}' for i in range(n_nodes)]

        # === 生成无规律基础信号（模拟真实集群负载波动） ===
        # 1) 随机游走 + 均值回归：模拟整体负载缓慢漂移
        walk = np.zeros(n_timestamps)
        for i in range(1, n_timestamps):
            walk[i] = walk[i - 1] * 0.995 + np.random.randn() * 3

        # 2) 突变跳变：模拟任务调度导致的负载阶跃
        n_jumps = np.random.randint(5, 12)
        jump_times = sorted(np.random.choice(n_timestamps, n_jumps, replace=False))
        jump_level = 0.0
        level_signal = np.zeros(n_timestamps)
        for jt in jump_times:
            jump_level += np.random.randn() * 40
            jump_level = np.clip(jump_level, -100, 100)
            level_signal[jt:] = jump_level

        # 3) 中频波动：非周期性的负载脉冲
        pulse_signal = np.zeros(n_timestamps)
        for _ in range(np.random.randint(8, 20)):
            center = np.random.randint(0, n_timestamps)
            width = np.random.randint(5, 40)
            height = np.random.randn() * 25
            s_p = max(0, center - width // 2)
            e_p = min(n_timestamps, center + width // 2)
            pulse_signal[s_p:e_p] += height

        # 4) 高频小噪声
        hf_noise = np.random.randn(n_timestamps) * 2

        # 合成基础信号，偏移到正值区域
        base_signal = 200 + walk + level_signal + pulse_signal + hf_noise
        base_signal = np.maximum(base_signal, 10)

        # === 生成各节点数据（正常节点紧密跟随基础信号） ===
        data = np.zeros((n_timestamps, n_nodes))
        for n in range(n_nodes):
            # 极小个体偏差（标准差约为信号的1%-2%）
            individual_noise = np.random.randn(n_timestamps) * 2.5
            offset = np.random.randn() * 1.5
            data[:, n] = base_signal + individual_noise + offset

        # === 注入异常（多个分散的短片段） ===
        anomaly_nodes = np.random.choice(n_nodes, n_anomaly_nodes, replace=False)
        anomaly_segments = []

        for an in anomaly_nodes:
            node_name = node_names[an]
            n_segs = np.random.randint(3, 6)
            seg_regions = np.linspace(0, n_timestamps, n_segs + 2)[1:-1].astype(int)

            for region_center in seg_regions:
                seg_len = np.random.randint(10, 40)
                seg_start = max(0, region_center + np.random.randint(-30, 30))
                seg_end = min(n_timestamps, seg_start + seg_len)
                if seg_end <= seg_start:
                    continue

                anomaly_type = np.random.choice(['amplitude', 'shape', 'combined'])

                if anomaly_type == 'amplitude':
                    direction = np.random.choice([-1, 1])
                    magnitude = np.random.uniform(60, 120)
                    data[seg_start:seg_end, an] += direction * magnitude
                    data[seg_start:seg_end, an] += (
                        np.random.randn(seg_end - seg_start) * 8
                    )
                elif anomaly_type == 'shape':
                    indep_walk = np.cumsum(
                        np.random.randn(seg_end - seg_start) * 6
                    )
                    indep_walk += data[seg_start, an] - indep_walk[0]
                    data[seg_start:seg_end, an] = (
                        indep_walk + np.random.randn(seg_end - seg_start) * 3
                    )
                else:  # combined
                    offset_val = (np.random.choice([-1, 1])
                                  * np.random.uniform(40, 80))
                    jitter = np.random.randn(seg_end - seg_start) * 15
                    data[seg_start:seg_end, an] += offset_val + jitter

                anomaly_segments.append({
                    'node': node_name,
                    'node_idx': int(an),
                    'start': int(seg_start),
                    'end': int(seg_end),
                    'start_time': str(timestamps[seg_start]),
                    'end_time': str(
                        timestamps[min(seg_end - 1, n_timestamps - 1)]
                    ),
                    'type': anomaly_type,
                })

        data = np.maximum(data, 1)

        df = pd.DataFrame(data, index=timestamps, columns=node_names)
        return {
            'rpc_connections': df,
            '_anomaly_info': {
                'anomaly_nodes': [node_names[i] for i in anomaly_nodes],
                'anomaly_node_indices': [int(i) for i in anomaly_nodes],
                'anomaly_segments': anomaly_segments,
                'total_anomaly_points': sum(
                    s['end'] - s['start'] for s in anomaly_segments
                ),
                'anomaly_ratio': sum(
                    s['end'] - s['start'] for s in anomaly_segments
                ) / (n_timestamps * n_nodes),
            }
        }
