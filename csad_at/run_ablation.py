"""
CSAD-AT 对比实验脚本

实验内容：
1. 经典SPOT vs I-SPOT（在融合分数上对比）
2. 聚合策略对比：加权平均 vs 最大值 vs 投票

用法：
    python -m csad_at.run_ablation data.csv \
        --ground-truth anomaly_data_YARN6_new.csv \
        --output ablation_results/
"""

import argparse
import os
import sys
import numpy as np
import pandas as pd

from .pipeline import (
    run_euc_detector, run_ae_detector, run_dbscan_detector,
    clip_and_minmax, weighted_fusion, scores_to_global_timeline,
    global_ispot_detect
)
from .spot import SPOT
from .ispot import ISPOT
from .evaluate import evaluate_detection


def fusion_max(method_scores, n_nodes, n_windows):
    """最大值聚合：每个(节点,窗口)取各方法分数的最大值"""
    fused = {}
    for i in range(n_nodes):
        max_scores = np.zeros(n_windows)
        for scores in method_scores:
            max_scores = np.maximum(max_scores, np.array(scores[i]))
        fused[i] = max_scores.tolist()
    return fused


def fusion_vote(method_scores, method_ispot_results, n_nodes, n_windows,
                vote_threshold=2):
    """
    投票聚合：每种方法单独跑I-SPOT，按投票决定异常

    返回伪分数：投票数 / 方法数（归一化到[0,1]），
    以便后续统一用I-SPOT做最终判定。
    """
    n_methods = len(method_ispot_results)
    vote_matrix = np.zeros((n_windows, n_nodes))

    for name, det in method_ispot_results.items():
        vote_matrix += det['anomaly_matrix']

    # 归一化为[0,1]分数
    fused = {}
    for i in range(n_nodes):
        fused[i] = (vote_matrix[:, i] / n_methods).tolist()
    return fused


def global_spot_detect(scores_dict, n_nodes, n_windows, curve_names,
                       anomaly_ratio=0.0065, level=0.98,
                       t_update=50, w_max=None):
    """用经典SPOT在全局时间线上做检测（对比用）"""
    timeline, index_map = scores_to_global_timeline(
        scores_dict, n_nodes, n_windows)

    spot = SPOT()
    spot_res = spot.run(
        timeline,
        anomaly_ratio=anomaly_ratio,
        level=level,
        t_update=t_update,
        w_max=w_max,
    )

    # 转换为 anomaly_matrix
    anomaly_matrix = np.zeros((n_windows, n_nodes), dtype=int)
    for flat_idx in spot_res['anomaly_indices']:
        if flat_idx < len(index_map):
            w, i = index_map[flat_idx]
            anomaly_matrix[w, i] = 1

    anomaly_details = []
    for flat_idx in spot_res['anomaly_indices']:
        if flat_idx < len(index_map):
            w, i = index_map[flat_idx]
            anomaly_details.append({
                'node': curve_names[i],
                'node_idx': i,
                'window_idx': w,
                'score': float(timeline[flat_idx]),
                'threshold': float(spot_res['thresholds'][flat_idx]),
            })

    anomaly_node_idxs = np.where(anomaly_matrix.sum(axis=0) > 0)[0]
    anomaly_nodes = [curve_names[i] for i in anomaly_node_idxs]

    node_anomaly_counts = {}
    for i in anomaly_node_idxs:
        node_anomaly_counts[curve_names[i]] = int(anomaly_matrix[:, i].sum())

    init_seq_len = spot_res['initial_seq_len']
    init_windows = init_seq_len // n_nodes

    return {
        'timeline': timeline,
        'index_map': index_map,
        'ispot_result': spot_res,  # 兼容evaluate接口
        'anomaly_matrix': anomaly_matrix,
        'anomaly_nodes': anomaly_nodes,
        'node_anomaly_counts': node_anomaly_counts,
        'anomaly_details': anomaly_details,
        'init_windows': init_windows,
    }


def run_ablation(csv_file, ground_truth_file, data_file=None,
                 output_dir='ablation_results',
                 window_size=20, step=10,
                 weights=None,
                 k_neighbors=5,
                 ae_latent_dim=5, ae_epochs=50, ae_lr=1e-3,
                 anomaly_ratio=0.0065, ispot_level=0.98,
                 ispot_t_update=50, ispot_w_max=None,
                 overlap_threshold=0.1):
    """运行全部对比实验"""

    if data_file is None:
        data_file = csv_file
    if weights is None:
        weights = [1.0/3, 1.0/3, 1.0/3]

    os.makedirs(output_dir, exist_ok=True)

    # ========== 0. 加载数据 & 三种方法计算分数 ==========
    print("=" * 70)
    print("CSAD-AT 对比实验")
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

    # 三种方法计算原始分数
    print("\n[1/3] 欧氏距离偏离度...")
    euc_res = run_euc_detector(curves, timestamps, window_size, step)
    n_windows = euc_res['n_windows']

    print("[2/3] 自编码器嵌入偏离度...")
    ae_res = run_ae_detector(
        curves, timestamps, window_size, step,
        latent_dim=ae_latent_dim, epochs=ae_epochs, lr=ae_lr)

    print("[3/3] DBSCAN 密度偏离度...")
    db_res = run_dbscan_detector(
        curves, timestamps, window_size, step, k_neighbors)

    method_results = {
        'euclidean': euc_res,
        'autoencoder': ae_res,
        'dbscan': db_res,
    }

    # 归一化
    print("\n[归一化] 截断负值 + MinMax...")
    normalized_scores = {}
    method_scores = []
    for name, res in method_results.items():
        normed = clip_and_minmax(res['scores'], n_nodes, n_windows)
        normalized_scores[name] = normed
        method_scores.append(normed)

    # 各方法单独I-SPOT（投票聚合需要用到）
    print("\n[各方法单独I-SPOT]...")
    method_ispot_results = {}
    for name, normed in normalized_scores.items():
        det = global_ispot_detect(
            normed, n_nodes, n_windows, curve_names,
            anomaly_ratio=anomaly_ratio,
            level=ispot_level,
            t_update=ispot_t_update,
            w_max=ispot_w_max,
        )
        method_ispot_results[name] = det
        print(f"  {name}: {len(det['anomaly_nodes'])} 异常节点")

    window_starts = euc_res['window_starts']
    window_ends = euc_res['window_ends']

    # 构造基础results结构（供evaluate_detection使用）
    base_results = {
        'curve_names': curve_names,
        'n_nodes': n_nodes,
        'n_windows': n_windows,
        'window_starts': window_starts,
        'window_ends': window_ends,
        'method_results': method_results,
        'normalized_scores': normalized_scores,
        'method_ispot_results': method_ispot_results,
    }

    all_eval = {}

    # ========== 实验1: 经典SPOT vs I-SPOT ==========
    print("\n" + "=" * 70)
    print("实验1: 经典SPOT vs I-SPOT（融合分数上对比）")
    print("=" * 70)

    # 加权平均融合
    fused_scores = weighted_fusion(
        method_scores, weights, n_nodes, n_windows)

    # I-SPOT（标准流程）
    print("\n[I-SPOT]...")
    fused_ispot = global_ispot_detect(
        fused_scores, n_nodes, n_windows, curve_names,
        anomaly_ratio=anomaly_ratio,
        level=ispot_level,
        t_update=ispot_t_update,
        w_max=ispot_w_max,
    )

    results_ispot = {**base_results, 'fused_ispot': fused_ispot,
                     'fused_scores': fused_scores}
    eval_ispot = evaluate_detection(
        results_ispot, ground_truth_file, data_file,
        window_size, step, overlap_threshold=overlap_threshold,
        stage='fused')
    eval_ispot['stage'] = 'fused_ispot'
    all_eval['fused_ispot'] = eval_ispot

    # 经典SPOT
    print("\n[经典SPOT]...")
    fused_spot = global_spot_detect(
        fused_scores, n_nodes, n_windows, curve_names,
        anomaly_ratio=anomaly_ratio,
        level=ispot_level,
        t_update=ispot_t_update,
        w_max=ispot_w_max,
    )

    results_spot = {**base_results, 'fused_ispot': fused_spot,
                    'fused_scores': fused_scores}
    eval_spot = evaluate_detection(
        results_spot, ground_truth_file, data_file,
        window_size, step, overlap_threshold=overlap_threshold,
        stage='fused')
    eval_spot['stage'] = 'fused_classic_spot'
    all_eval['fused_classic_spot'] = eval_spot

    # ========== 实验2: 聚合策略对比 ==========
    print("\n" + "=" * 70)
    print("实验2: 聚合策略对比（均使用I-SPOT）")
    print("=" * 70)

    # 2a. 加权平均（已有）
    print("\n[加权平均] (已计算)")
    all_eval['agg_weighted_avg'] = {**eval_ispot, 'stage': 'agg_weighted_avg'}

    # 2b. 最大值聚合
    print("\n[最大值聚合]...")
    fused_max = fusion_max(method_scores, n_nodes, n_windows)
    fused_max_ispot = global_ispot_detect(
        fused_max, n_nodes, n_windows, curve_names,
        anomaly_ratio=anomaly_ratio,
        level=ispot_level,
        t_update=ispot_t_update,
        w_max=ispot_w_max,
    )
    results_max = {**base_results, 'fused_ispot': fused_max_ispot,
                   'fused_scores': fused_max}
    eval_max = evaluate_detection(
        results_max, ground_truth_file, data_file,
        window_size, step, overlap_threshold=overlap_threshold,
        stage='fused')
    eval_max['stage'] = 'agg_max'
    all_eval['agg_max'] = eval_max

    # 2c. 投票聚合
    print("\n[投票聚合]...")
    fused_vote = fusion_vote(
        method_scores, method_ispot_results, n_nodes, n_windows)
    fused_vote_ispot = global_ispot_detect(
        fused_vote, n_nodes, n_windows, curve_names,
        anomaly_ratio=anomaly_ratio,
        level=ispot_level,
        t_update=ispot_t_update,
        w_max=ispot_w_max,
    )
    results_vote = {**base_results, 'fused_ispot': fused_vote_ispot,
                    'fused_scores': fused_vote}
    eval_vote = evaluate_detection(
        results_vote, ground_truth_file, data_file,
        window_size, step, overlap_threshold=overlap_threshold,
        stage='fused')
    eval_vote['stage'] = 'agg_vote'
    all_eval['agg_vote'] = eval_vote

    # ========== 汇总 ==========
    print("\n" + "=" * 70)
    print("全部对比实验结果汇总")
    print("=" * 70)
    print(f"{'实验':<25} {'Precision':>10} {'Recall':>10} {'F1':>10} "
          f"{'TP':>5} {'FP':>5} {'FN':>5}")
    print("-" * 70)

    display_order = [
        ('fused_ispot', '融合+I-SPOT (CSAD-AT)'),
        ('fused_classic_spot', '融合+经典SPOT'),
        ('agg_weighted_avg', '聚合:加权平均+I-SPOT'),
        ('agg_max', '聚合:最大值+I-SPOT'),
        ('agg_vote', '聚合:投票+I-SPOT'),
    ]

    for key, label in display_order:
        if key in all_eval:
            r = all_eval[key]
            print(f"{label:<25} {r['precision']:>10.4f} {r['recall']:>10.4f} "
                  f"{r['f1']:>10.4f} {r['tp']:>5} {r['fp']:>5} {r['fn']:>5}")

    print("=" * 70)

    # 保存CSV
    rows = []
    for key, label in display_order:
        if key in all_eval:
            r = all_eval[key]
            rows.append({
                'experiment': key,
                'label': label,
                'precision': r['precision'],
                'recall': r['recall'],
                'f1': r['f1'],
                'tp': r['tp'],
                'fp': r['fp'],
                'fn': r['fn'],
            })

    result_df = pd.DataFrame(rows)
    csv_path = os.path.join(output_dir, 'ablation_results.csv')
    result_df.to_csv(csv_path, index=False)
    print(f"\n结果已保存: {csv_path}")

    return all_eval


def main():
    parser = argparse.ArgumentParser(description='CSAD-AT 对比实验')
    parser.add_argument('csv_file', help='输入CSV文件')
    parser.add_argument('--ground-truth', required=True, help='异常标注文件')
    parser.add_argument('--output', '-o', default='ablation_results', help='输出目录')
    parser.add_argument('--window', type=int, default=20, help='窗口大小')
    parser.add_argument('--step', type=int, default=10, help='步长')
    parser.add_argument('--weights', nargs='+', type=float, default=None)
    parser.add_argument('--k-neighbors', type=int, default=5)
    parser.add_argument('--ae-latent-dim', type=int, default=5)
    parser.add_argument('--ae-epochs', type=int, default=50)
    parser.add_argument('--ae-lr', type=float, default=1e-3)
    parser.add_argument('--anomaly-ratio', type=float, default=0.0065)
    parser.add_argument('--ispot-level', type=float, default=0.98)
    parser.add_argument('--ispot-t-update', type=int, default=50)
    parser.add_argument('--ispot-w-max', type=int, default=None)
    parser.add_argument('--overlap-threshold', type=float, default=0.1)

    args = parser.parse_args()

    weights = args.weights
    if weights is None:
        weights = [1.0/3, 1.0/3, 1.0/3]

    run_ablation(
        csv_file=args.csv_file,
        ground_truth_file=args.ground_truth,
        output_dir=args.output,
        window_size=args.window,
        step=args.step,
        weights=weights,
        k_neighbors=args.k_neighbors,
        ae_latent_dim=args.ae_latent_dim,
        ae_epochs=args.ae_epochs,
        ae_lr=args.ae_lr,
        anomaly_ratio=args.anomaly_ratio,
        ispot_level=args.ispot_level,
        ispot_t_update=args.ispot_t_update,
        ispot_w_max=args.ispot_w_max,
        overlap_threshold=args.overlap_threshold,
    )


if __name__ == '__main__':
    main()
