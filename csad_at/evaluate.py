"""
CSAD-AT 性能评估模块

评估逻辑（以原始检测窗口为单位）：
  - 每个 (node, window_idx) 被 I-SPOT 标记为异常 = 一个独立检测窗口
  - TP: 该检测窗口与同节点某条 ground truth 的时间重叠 >= overlap_threshold
  - FP: 该检测窗口不匹配任何同节点的 ground truth
  - FN: 对于每条未被检测到的 ground truth，计算它应覆盖的有效窗口数

关键修正：
  I-SPOT 前 initial_seq_len 个数据点用于初始化 GPD 模型，
  对应的前 init_windows 个窗口在评估时完全排除。

异常标注文件格式 (anomaly_data_YARN6_new.csv):
  node, start, end, label
  其中 label=1 表示确认异常
"""

import numpy as np
import pandas as pd
import datetime
from collections import defaultdict


def timestamp_to_datetime(timestamp):
    """将时间戳转换为 datetime 对象（兼容多种格式）"""
    try:
        timestamp_int = int(timestamp)
        if 1e9 < timestamp_int < 2e9:
            return datetime.datetime.fromtimestamp(timestamp_int)
        elif 1e12 < timestamp_int < 2e12:
            return datetime.datetime.fromtimestamp(timestamp_int / 1000.0)
    except (ValueError, TypeError, OSError):
        pass

    try:
        num_ts = float(timestamp)
        base_date = datetime.datetime(1899, 12, 30)
        return base_date + datetime.timedelta(days=num_ts)
    except Exception:
        pass

    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S"]:
        try:
            return datetime.datetime.strptime(str(timestamp), fmt)
        except Exception:
            continue

    return timestamp


def calculate_overlap_ratio(det_start, det_end, gt_start, gt_end):
    """
    计算检测窗口与真实异常的重叠比例（相对于检测窗口长度）

    返回:
        overlap_ratio: 重叠部分占检测窗口长度的比例
    """
    overlap_start = max(det_start, gt_start)
    overlap_end = min(det_end, gt_end)

    if overlap_start >= overlap_end:
        return 0.0

    overlap_duration = (overlap_end - overlap_start).total_seconds()
    det_duration = (det_end - det_start).total_seconds()

    if det_duration == 0:
        return 0.0

    return overlap_duration / det_duration


def get_time_points(data_file, time_column=0):
    """
    从原始 CSV 数据中提取排序后的时间点列表

    返回:
        time_points: list of datetime
    """
    df = pd.read_csv(data_file)
    if isinstance(time_column, int):
        time_col = df.columns[time_column]
    else:
        time_col = time_column

    df['datetime'] = df[time_col].apply(timestamp_to_datetime)
    df = df.sort_values('datetime').reset_index(drop=True)

    return df['datetime'].tolist()


def count_windows_for_anomaly(anomaly_start, anomaly_end, time_points,
                              window_size, step, skip_windows=0):
    """
    计算一个真实异常时间段应该覆盖多少个有效窗口（排除初始化窗口）

    参数:
        anomaly_start, anomaly_end: 异常的起止时间
        time_points: 排序后的时间点列表
        window_size: 窗口大小（数据点数）
        step: 步长（数据点数）
        skip_windows: 跳过前 N 个窗口（I-SPOT 初始化阶段）

    返回:
        window_count: 覆盖的有效窗口数
    """
    n = len(time_points)
    window_count = 0
    win_idx = 0

    i = 0
    while i + window_size <= n:
        if win_idx >= skip_windows:
            window_start = time_points[i]
            window_end = time_points[i + window_size - 1]

            if (window_start <= anomaly_end) and (anomaly_start <= window_end):
                window_count += 1

        win_idx += 1
        i += step

    return window_count


def evaluate_detection(results, ground_truth_file, data_file,
                       window_size, step, time_column=0,
                       overlap_threshold=0.5,
                       stage='fused'):
    """
    评估检测结果的 Precision / Recall / F1
    以原始检测窗口为单位，不合并连续窗口。

    参数:
        results: pipeline.run_pipeline() 的返回值
        ground_truth_file: 异常标注 CSV（node, start, end, label）
        data_file: 原始数据 CSV
        window_size: 滑动窗口大小
        step: 滑动步长
        time_column: 时间列索引
        overlap_threshold: 重叠比例阈值（默认 0.5）
        stage: 评估哪个阶段 'fused' / 'euclidean' / 'autoencoder' / 'dbscan'

    返回:
        dict: {precision, recall, f1, tp, fp, fn, init_windows, ...}
    """
    # ========== 1. 确定要评估的检测结果 ==========
    if stage == 'fused':
        det_result = results['fused_ispot']
    elif stage in results.get('method_ispot_results', {}):
        det_result = results['method_ispot_results'][stage]
    else:
        raise ValueError(f"Unknown stage: {stage}")

    n_nodes = results['n_nodes']
    n_windows = results['n_windows']
    curve_names = results['curve_names']
    window_starts = results['window_starts']
    window_ends = results['window_ends']
    init_windows = det_result['init_windows']

    print(f"\n{'=' * 60}")
    print(f"性能评估: {stage}")
    print(f"{'=' * 60}")
    print(f"I-SPOT 初始化窗口数: {init_windows} (前 {init_windows} 个窗口排除评估)")
    print(f"有效评估窗口: {init_windows} ~ {n_windows - 1} "
          f"(共 {n_windows - init_windows} 个窗口)")

    # ========== 2. 逐个提取检测窗口（不合并），排除初始化窗口 ==========
    anomaly_matrix = det_result['anomaly_matrix']  # (n_windows, n_nodes)

    # 每个检测窗口独立记录：(node_name, start_dt, end_dt)
    det_windows_by_node = defaultdict(list)
    total_det_windows = 0

    for w in range(init_windows, n_windows):
        w_start_dt = timestamp_to_datetime(window_starts[w])
        w_end_dt = timestamp_to_datetime(window_ends[w])
        for i_node in range(n_nodes):
            if anomaly_matrix[w, i_node] == 1:
                node_name = curve_names[i_node]
                det_windows_by_node[node_name].append({
                    'start_dt': w_start_dt,
                    'end_dt': w_end_dt,
                })
                total_det_windows += 1

    print(f"检测窗口数（排除初始化后）: {total_det_windows}")

    # ========== 3. 读取真实异常标注 ==========
    gt_df = pd.read_csv(ground_truth_file)
    gt_df = gt_df[gt_df['label'] == 1]

    if gt_df.empty:
        print("警告: 真实异常标注为空!")
        return {'precision': 0, 'recall': 0, 'f1': 0,
                'tp': 0, 'fp': 0, 'fn': 0, 'init_windows': init_windows}

    gt_df['start_dt'] = gt_df['start'].apply(timestamp_to_datetime)
    gt_df['end_dt'] = gt_df['end'].apply(timestamp_to_datetime)

    gt_by_node = defaultdict(list)
    for _, row in gt_df.iterrows():
        gt_by_node[row['node']].append({
            'start_dt': row['start_dt'],
            'end_dt': row['end_dt'],
        })

    print(f"真实异常: {len(gt_df)} 条标注, 涉及 {len(gt_by_node)} 个节点")

    # ========== 4. 计算 TP / FP（以每个检测窗口为单位）==========
    tp = 0
    fp = 0

    for node, det_wins in det_windows_by_node.items():
        for det_win in det_wins:
            matched = False
            if node in gt_by_node:
                for gt_seg in gt_by_node[node]:
                    ratio = calculate_overlap_ratio(
                        det_win['start_dt'], det_win['end_dt'],
                        gt_seg['start_dt'], gt_seg['end_dt'])
                    if ratio >= overlap_threshold:
                        matched = True
                        break
            if matched:
                tp += 1
            else:
                fp += 1

    # ========== 5. 计算 FN（未被检测到的异常应覆盖的窗口数）==========
    time_points = get_time_points(data_file, time_column)
    fn = 0

    for node, gt_segs in gt_by_node.items():
        for gt_seg in gt_segs:
            detected = False
            # 检查是否有任何检测窗口（同节点）与该 ground truth 重叠达标
            if node in det_windows_by_node:
                for det_win in det_windows_by_node[node]:
                    ratio = calculate_overlap_ratio(
                        det_win['start_dt'], det_win['end_dt'],
                        gt_seg['start_dt'], gt_seg['end_dt'])
                    if ratio >= overlap_threshold:
                        detected = True
                        break

            if not detected:
                # 未检测到：计算该异常应覆盖多少个有效窗口
                wc = count_windows_for_anomaly(
                    gt_seg['start_dt'], gt_seg['end_dt'],
                    time_points, window_size, step,
                    skip_windows=init_windows)
                fn += wc

    # ========== 6. 计算指标 ==========
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    print(f"\n--- 评估结果 ({stage}) ---")
    print(f"重叠阈值: {overlap_threshold * 100:.0f}%")
    print(f"TP (正确检测窗口数): {tp}")
    print(f"FP (误报检测窗口数): {fp}")
    print(f"FN (漏检窗口数):     {fn}")
    print(f"Precision: {precision:.4f}")
    print(f"Recall:    {recall:.4f}")
    print(f"F1:        {f1:.4f}")
    print(f"{'=' * 60}")

    return {
        'stage': stage,
        'precision': precision,
        'recall': recall,
        'f1': f1,
        'tp': tp,
        'fp': fp,
        'fn': fn,
        'init_windows': init_windows,
        'total_det_windows': total_det_windows,
        'overlap_threshold': overlap_threshold,
    }


def evaluate_all_stages(results, ground_truth_file, data_file,
                        window_size, step, time_column=0,
                        overlap_threshold=0.5):
    """
    评估所有阶段（三种方法各自 + 融合）

    返回:
        all_results: dict of {stage_name: eval_result}
    """
    all_eval = {}

    # 各方法中间结果
    for method_name in results.get('method_ispot_results', {}):
        try:
            res = evaluate_detection(
                results, ground_truth_file, data_file,
                window_size, step, time_column, overlap_threshold,
                stage=method_name)
            all_eval[method_name] = res
        except Exception as e:
            print(f"[警告] {method_name} 评估失败: {e}")

    # 融合结果
    try:
        res = evaluate_detection(
            results, ground_truth_file, data_file,
            window_size, step, time_column, overlap_threshold,
            stage='fused')
        all_eval['fused'] = res
    except Exception as e:
        print(f"[警告] 融合评估失败: {e}")

    # 汇总表格
    if all_eval:
        print(f"\n{'=' * 70}")
        print("性能评估汇总")
        print(f"{'=' * 70}")
        print(f"{'阶段':<15} {'Precision':>10} {'Recall':>10} {'F1':>10} "
              f"{'TP':>6} {'FP':>6} {'FN':>6}")
        print("-" * 70)
        for name, r in all_eval.items():
            print(f"{name:<15} {r['precision']:>10.4f} {r['recall']:>10.4f} "
                  f"{r['f1']:>10.4f} {r['tp']:>6} {r['fp']:>6} {r['fn']:>6}")
        print(f"{'=' * 70}")

    return all_eval


def save_evaluation(all_eval, output_dir):
    """保存评估结果到 CSV"""
    import os
    os.makedirs(output_dir, exist_ok=True)

    rows = []
    for name, r in all_eval.items():
        rows.append({
            'stage': r['stage'],
            'precision': r['precision'],
            'recall': r['recall'],
            'f1': r['f1'],
            'tp': r['tp'],
            'fp': r['fp'],
            'fn': r['fn'],
            'init_windows': r['init_windows'],
            'det_windows': r['total_det_windows'],
            'overlap_threshold': r['overlap_threshold'],
        })

    df = pd.DataFrame(rows)
    output_file = os.path.join(output_dir, 'evaluation_results.csv')
    df.to_csv(output_file, index=False)
    print(f"\n评估结果已保存: {output_file}")
