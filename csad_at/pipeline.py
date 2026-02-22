"""
CSAD-AT 统一检测流水线

核心修正：I-SPOT 的正确应用方式
  I-SPOT 的输入应该是"所有节点的分数拼成一条全局时间线"，而不是每个节点单独一条。
  原因：CSAD-AT 的核心是跨节点比较——同一个时间窗口内，得分偏高的节点就是异常的。
  如果每个节点单独做 I-SPOT，等于丧失了跨节点的比较语义。

全局时间线的构造方式：
  对于 N 个节点、W 个窗口，将分数按窗口优先排列：
    [win_0_node_0, win_0_node_1, ..., win_0_node_N-1,
     win_1_node_0, win_1_node_1, ..., win_1_node_N-1,
     ...
     win_W-1_node_0, ..., win_W-1_node_N-1]
  这样 I-SPOT 的阈值反映的是"在当前整体分布下，多高的分数算异常"，
  即能自动识别出得分远高于其他节点的那些（节点, 窗口）对。

完整流程：
  1. 三种方法各自计算距离偏离度分数
  2. 对每种方法的分数做截断 + Min-Max 归一化到 [0, 1]
  3. 每种方法的归一化分数 -> 全局时间线 -> I-SPOT -> 中间检测结果
  4. 加权平均融合三种归一化分数
  5. 融合分数 -> 全局时间线 -> I-SPOT -> 最终检测结果
  6. 可视化每个阶段

对应论文第三章 3.4 节 CSAD-AT 框架
"""

import numpy as np
import pandas as pd
from .euc_detector import run_euc_detector
from .ae_detector import run_ae_detector
from .dbscan_detector import run_dbscan_detector
from .ispot import ISPOT


def clip_and_minmax(scores_dict, n_nodes, n_windows):
    """
    截断负值 + 全局 Min-Max 归一化

    参数:
        scores_dict: {node_idx: list of float}
        n_nodes: 节点数
        n_windows: 窗口数

    返回:
        normalized: {node_idx: list of float}, 归一化后的分数
    """
    # 收集所有分数
    all_vals = []
    for i in range(n_nodes):
        all_vals.extend(scores_dict[i])
    all_vals = np.array(all_vals)

    # 截断负值
    all_vals = np.maximum(all_vals, 0)

    # 全局 min-max
    vmin = all_vals.min()
    vmax = all_vals.max()

    normalized = {}
    for i in range(n_nodes):
        raw = np.maximum(np.array(scores_dict[i]), 0)
        if vmax - vmin < 1e-10:
            normalized[i] = [0.0] * len(raw)
        else:
            normed = (raw - vmin) / (vmax - vmin)
            normalized[i] = normed.tolist()

    return normalized


def scores_to_global_timeline(scores_dict, n_nodes, n_windows):
    """
    将 {node_idx: [w0, w1, ...]} 按窗口优先顺序拼成一维全局序列

    排列顺序：win_0_node_0, win_0_node_1, ..., win_1_node_0, ...
    这样同一窗口内的不同节点分数相邻，I-SPOT 能捕捉跨节点的极值差异

    返回:
        timeline: ndarray, shape=(n_windows * n_nodes,)
        index_map: list of (window_idx, node_idx), 每个位置对应的窗口和节点
    """
    timeline = []
    index_map = []
    for w in range(n_windows):
        for i in range(n_nodes):
            timeline.append(scores_dict[i][w])
            index_map.append((w, i))
    return np.array(timeline), index_map


def global_ispot_detect(scores_dict, n_nodes, n_windows, curve_names,
                        anomaly_ratio=0.0085, level=0.98,
                        t_update=50, w_max=None):
    """
    将所有节点分数拼成全局时间线，运行一次 I-SPOT

    返回:
        result: dict with keys:
            'timeline': 全局序列
            'index_map': 位置到(窗口,节点)的映射
            'ispot_result': I-SPOT 原始输出
            'anomaly_matrix': ndarray (n_windows, n_nodes), 0/1
            'anomaly_nodes': 被标记为异常的节点名列表
            'anomaly_details': list of {node, window, score, threshold}
    """
    timeline, index_map = scores_to_global_timeline(
        scores_dict, n_nodes, n_windows)

    ispot = ISPOT()
    ispot_res = ispot.run(
        timeline,
        anomaly_ratio=anomaly_ratio,
        level=level,
        t_update=t_update,
        w_max=w_max,
    )

    # 将一维结果映射回 (窗口, 节点) 矩阵
    anomaly_matrix = np.zeros((n_windows, n_nodes), dtype=int)
    anomaly_details = []

    for flat_idx in ispot_res['anomaly_indices']:
        w, i = index_map[flat_idx]
        anomaly_matrix[w, i] = 1
        anomaly_details.append({
            'node': curve_names[i],
            'node_idx': i,
            'window_idx': w,
            'score': float(timeline[flat_idx]),
            'threshold': float(ispot_res['thresholds'][flat_idx]),
        })

    # 统计异常节点（至少在一个窗口被标记）
    anomaly_node_idxs = np.where(anomaly_matrix.sum(axis=0) > 0)[0]
    anomaly_nodes = [curve_names[i] for i in anomaly_node_idxs]

    # 统计每个节点的异常窗口数
    node_anomaly_counts = {}
    for i in anomaly_node_idxs:
        node_anomaly_counts[curve_names[i]] = int(anomaly_matrix[:, i].sum())

    return {
        'timeline': timeline,
        'index_map': index_map,
        'ispot_result': ispot_res,
        'anomaly_matrix': anomaly_matrix,
        'anomaly_nodes': anomaly_nodes,
        'node_anomaly_counts': node_anomaly_counts,
        'anomaly_details': anomaly_details,
    }


def weighted_fusion(score_dicts, weights, n_nodes, n_windows):
    """
    加权融合多种归一化分数

    参数:
        score_dicts: list of {node_idx: list of float}
        weights: list of float, 各方法权重
        n_nodes: 节点数
        n_windows: 窗口数

    返回:
        fused: {node_idx: list of float}
    """
    # 归一化权重
    w_sum = sum(weights)
    weights = [w / w_sum for w in weights]

    fused = {i: np.zeros(n_windows) for i in range(n_nodes)}
    for m, scores in enumerate(score_dicts):
        for i in range(n_nodes):
            fused[i] += weights[m] * np.array(scores[i])

    for i in range(n_nodes):
        fused[i] = fused[i].tolist()

    return fused


def run_pipeline(csv_file, window_size=60, step=30,
                 weights=None,
                 k_neighbors=5,
                 ae_latent_dim=5, ae_epochs=50, ae_lr=1e-3,
                 anomaly_ratio=0.0085, ispot_level=0.98,
                 ispot_t_update=50, ispot_w_max=None,
                 methods=None):
    """
    CSAD-AT 端到端检测流水线

    返回:
        results: dict, 完整检测结果（含中间阶段结果）
    """
    if weights is None:
        weights = [1.0 / 3, 1.0 / 3, 1.0 / 3]
    if methods is None:
        methods = ['euclidean', 'autoencoder', 'dbscan']

    # ========== 0. 加载数据 ==========
    print("=" * 70)
    print("CSAD-AT: 基于曲线相似性的自适应阈值异常检测框架")
    print("=" * 70)

    df = pd.read_csv(csv_file)
    for col in df.columns[1:]:
        df[col] = df[col].replace([np.inf, -np.inf], np.nan)
        df[col] = df[col].ffill().bfill().fillna(0)
    df.iloc[:, 0] = df.iloc[:, 0].ffill().bfill()

    timestamps = df.iloc[:, 0].values
    curve_names = df.columns[1:].tolist()
    curves = [df[col].values.astype(np.float64) for col in curve_names]
    n_nodes = len(curves)
    T = len(timestamps)

    print(f"数据: {T} 时间步, {n_nodes} 节点")
    print(f"窗口: size={window_size}, step={step}")
    print(f"方法: {methods}, 权重: {weights}")
    print()

    # ========== 1. 三种方法各自计算距离偏离度 ==========
    method_results = {}
    active_weights = []

    if 'euclidean' in methods:
        print("[1/3] 欧氏距离偏离度...")
        euc_res = run_euc_detector(curves, timestamps, window_size, step)
        method_results['euclidean'] = euc_res
        n_windows = euc_res['n_windows']
        active_weights.append(weights[0] if len(weights) > 0 else 1.0)
    else:
        n_windows = max(1, (T - window_size) // step)

    if 'autoencoder' in methods:
        print("[2/3] 自编码器嵌入偏离度...")
        ae_res = run_ae_detector(
            curves, timestamps, window_size, step,
            latent_dim=ae_latent_dim, epochs=ae_epochs, lr=ae_lr)
        method_results['autoencoder'] = ae_res
        n_windows = ae_res['n_windows']
        active_weights.append(weights[1] if len(weights) > 1 else 1.0)

    if 'dbscan' in methods:
        print("[3/3] DBSCAN 密度偏离度...")
        db_res = run_dbscan_detector(
            curves, timestamps, window_size, step, k_neighbors)
        method_results['dbscan'] = db_res
        n_windows = db_res['n_windows']
        active_weights.append(weights[2] if len(weights) > 2 else 1.0)

    # ========== 2. 截断 + Min-Max 归一化 ==========
    print("\n[归一化] 截断负值 + Min-Max 归一化到 [0, 1]...")
    normalized_scores = {}
    method_scores = []
    for name, res in method_results.items():
        normed = clip_and_minmax(res['scores'], n_nodes, n_windows)
        normalized_scores[name] = normed
        method_scores.append(normed)

        # 打印统计
        all_v = []
        for i in range(n_nodes):
            all_v.extend(normed[i])
        arr = np.array(all_v)
        print(f"  {name}: min={arr.min():.4f}, max={arr.max():.4f}, "
              f"mean={arr.mean():.4f}, >0.5占比={100*(arr>0.5).mean():.1f}%")

    # ========== 3. 每种方法单独 I-SPOT（中间结果） ==========
    print(f"\n[中间检测] 各方法单独运行 I-SPOT (全局时间线)...")
    method_ispot_results = {}
    for name, normed in normalized_scores.items():
        print(f"  {name}: ", end="")
        det = global_ispot_detect(
            normed, n_nodes, n_windows, curve_names,
            anomaly_ratio=anomaly_ratio,
            level=ispot_level,
            t_update=ispot_t_update,
            w_max=ispot_w_max,
        )
        method_ispot_results[name] = det
        n_anomaly_points = len(det['anomaly_details'])
        print(f"{len(det['anomaly_nodes'])} 异常节点, "
              f"{n_anomaly_points} 异常(节点,窗口)对")

    # ========== 4. 加权融合 ==========
    print(f"\n[融合] 加权平均 (权重: {active_weights})...")
    fused_scores = weighted_fusion(
        method_scores, active_weights, n_nodes, n_windows)

    # 打印融合后统计
    all_fused = []
    for i in range(n_nodes):
        all_fused.extend(fused_scores[i])
    fused_arr = np.array(all_fused)
    print(f"  融合分数: min={fused_arr.min():.4f}, max={fused_arr.max():.4f}, "
          f"mean={fused_arr.mean():.4f}, >0.5占比={100*(fused_arr>0.5).mean():.1f}%")

    # ========== 5. 融合后 I-SPOT 最终检测 ==========
    print(f"\n[最终检测] 融合分数全局 I-SPOT "
          f"(q={anomaly_ratio}, level={ispot_level}, "
          f"t_update={ispot_t_update})...")

    fused_ispot = global_ispot_detect(
        fused_scores, n_nodes, n_windows, curve_names,
        anomaly_ratio=anomaly_ratio,
        level=ispot_level,
        t_update=ispot_t_update,
        w_max=ispot_w_max,
    )

    # ========== 6. 汇总结果 ==========
    first_res = next(iter(method_results.values()))
    window_starts = first_res['window_starts']
    window_ends = first_res['window_ends']

    # 提取异常片段
    anomaly_segments = []
    for i_node, node_name in enumerate(curve_names):
        # 找出该节点被标记异常的窗口
        node_anomaly_wins = np.where(
            fused_ispot['anomaly_matrix'][:, i_node] == 1)[0].tolist()
        if node_anomaly_wins:
            segments = _extract_segments(
                node_anomaly_wins, node_name, i_node,
                window_starts, window_ends)
            anomaly_segments.extend(segments)

    print(f"\n{'=' * 70}")
    print(f"检测完成: {len(fused_ispot['anomaly_nodes'])} 个异常节点, "
          f"{len(anomaly_segments)} 个异常片段")
    if fused_ispot['anomaly_nodes']:
        print(f"异常节点: {fused_ispot['anomaly_nodes']}")
        for name, cnt in fused_ispot['node_anomaly_counts'].items():
            print(f"  {name}: {cnt} 个异常窗口")
    print(f"{'=' * 70}")

    return {
        'curve_names': curve_names,
        'n_nodes': n_nodes,
        'n_windows': n_windows,
        'window_starts': window_starts,
        'window_ends': window_ends,
        # 原始方法结果
        'method_results': method_results,
        # 归一化分数
        'normalized_scores': normalized_scores,
        # 各方法单独 I-SPOT 中间结果
        'method_ispot_results': method_ispot_results,
        # 融合
        'fused_scores': fused_scores,
        'active_weights': active_weights,
        # 融合后 I-SPOT 最终结果
        'fused_ispot': fused_ispot,
        # 汇总
        'anomaly_nodes': fused_ispot['anomaly_nodes'],
        'anomaly_segments': anomaly_segments,
    }


def _extract_segments(anomaly_indices, node_name, node_idx,
                      window_starts, window_ends):
    """从异常窗口索引列表中提取连续片段"""
    if not anomaly_indices:
        return []

    segments = []
    seg_start = anomaly_indices[0]
    prev = anomaly_indices[0]

    for idx in anomaly_indices[1:]:
        if idx == prev + 1:
            prev = idx
        else:
            segments.append({
                'node': node_name,
                'node_idx': node_idx,
                'win_start': seg_start,
                'win_end': prev + 1,
                'duration': prev - seg_start + 1,
                'start_time': (window_starts[seg_start]
                               if seg_start < len(window_starts) else None),
                'end_time': (window_ends[min(prev, len(window_ends) - 1)]
                             if prev < len(window_ends) else None),
            })
            seg_start = idx
            prev = idx

    segments.append({
        'node': node_name,
        'node_idx': node_idx,
        'win_start': seg_start,
        'win_end': prev + 1,
        'duration': prev - seg_start + 1,
        'start_time': (window_starts[seg_start]
                       if seg_start < len(window_starts) else None),
        'end_time': (window_ends[min(prev, len(window_ends) - 1)]
                     if prev < len(window_ends) else None),
    })

    return segments


def save_results(results, output_dir):
    """保存检测结果到 CSV 文件"""
    import os
    os.makedirs(output_dir, exist_ok=True)

    curve_names = results['curve_names']
    n_nodes = results['n_nodes']
    n_windows = results['n_windows']
    fused_ispot = results['fused_ispot']

    # 1. 保存融合分数 + 最终检测结果
    rows = []
    for w in range(n_windows):
        for i in range(n_nodes):
            row = {
                'curve_name': curve_names[i],
                'window_idx': w,
                'window_start': results['window_starts'][w],
                'window_end': results['window_ends'][w],
                'fused_score': results['fused_scores'][i][w],
                'is_anomaly': int(fused_ispot['anomaly_matrix'][w, i]),
            }
            # 各方法归一化分数
            for method_name, normed in results['normalized_scores'].items():
                row[f'{method_name}_norm'] = normed[i][w]
            # 各方法单独检测结果
            for method_name, det in results['method_ispot_results'].items():
                row[f'{method_name}_anomaly'] = int(
                    det['anomaly_matrix'][w, i])
            rows.append(row)

    df = pd.DataFrame(rows)
    output_file = os.path.join(output_dir, 'detection_results.csv')
    df.to_csv(output_file, index=False)
    print(f"检测结果已保存: {output_file}")

    # 2. 各方法中间检测结果摘要
    for method_name, det in results['method_ispot_results'].items():
        if det['anomaly_details']:
            det_df = pd.DataFrame(det['anomaly_details'])
            det_file = os.path.join(
                output_dir, f'{method_name}_anomalies.csv')
            det_df.to_csv(det_file, index=False)
            print(f"  {method_name} 异常详情: {det_file}")

    # 3. 保存异常片段摘要
    if results['anomaly_segments']:
        seg_df = pd.DataFrame(results['anomaly_segments'])
        seg_file = os.path.join(output_dir, 'anomaly_segments.csv')
        seg_df.to_csv(seg_file, index=False)
        print(f"异常片段已保存: {seg_file}")

    # 4. 保存汇总报告
    report_file = os.path.join(output_dir, 'report.txt')
    with open(report_file, 'w') as f:
        f.write("CSAD-AT 检测报告\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"总节点数: {n_nodes}\n")
        f.write(f"总窗口数: {n_windows}\n")
        f.write(f"融合权重: {results['active_weights']}\n\n")

        f.write("--- 各方法中间检测结果 ---\n")
        for method_name, det in results['method_ispot_results'].items():
            f.write(f"\n{method_name}:\n")
            f.write(f"  异常节点: {det['anomaly_nodes']}\n")
            for name, cnt in det['node_anomaly_counts'].items():
                f.write(f"    {name}: {cnt} 个异常窗口\n")

        f.write(f"\n--- 融合后最终检测结果 ---\n")
        f.write(f"异常节点: {fused_ispot['anomaly_nodes']}\n")
        for name, cnt in fused_ispot['node_anomaly_counts'].items():
            f.write(f"  {name}: {cnt} 个异常窗口\n")
        f.write(f"异常片段数: {len(results['anomaly_segments'])}\n")

    print(f"检测报告已保存: {report_file}")
