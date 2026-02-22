"""
CSAD-AT 可视化模块

绘图风格参照 spot-draw-new.py：
  - 蓝色曲线：分数序列
  - 红色虚线：t 阈值（POT 初始阈值）
  - 橙色实线：z_q 动态阈值
  - 红色散点：异常点

每个检测阶段（三种方法各自 + 融合）都输出一张图。
图中 x 轴是全局时间线索引（窗口 * 节点交替），标注窗口分界线。
"""

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os


# 中文字体设置（如果可用）
try:
    plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
except Exception:
    pass


def plot_ispot_detection(timeline, ispot_result, index_map, n_nodes, n_windows,
                         curve_names, title, output_path,
                         anomaly_matrix=None):
    """
    绘制 I-SPOT 检测结果图（参照 spot-draw-new 风格）

    参数:
        timeline: ndarray, 全局分数序列
        ispot_result: I-SPOT 返回的 dict
        index_map: list of (window_idx, node_idx)
        n_nodes: 节点数
        n_windows: 窗口数
        curve_names: 节点名列表
        title: 图标题
        output_path: 输出路径
        anomaly_matrix: (n_windows, n_nodes) 矩阵（可选，用于标注）
    """
    flags = np.array(ispot_result['anomaly_flags'])
    thresholds = np.array(ispot_result['thresholds'])
    t0_values = np.array(ispot_result['t0_values'])
    anomaly_idxs = np.array(ispot_result['anomaly_indices'])

    total_len = len(timeline)
    x = np.arange(total_len)

    fig, ax = plt.subplots(figsize=(24, 8))

    # 1. 绘制分数序列
    ax.plot(x, timeline, color='#4A90D9', alpha=0.7, linewidth=0.8,
            label='Score', zorder=2)

    # 2. 绘制 t0 阈值线（红色虚线）
    ax.plot(x, t0_values, 'r--', linewidth=1.0, alpha=0.6,
            label='t (initial threshold)', zorder=3)

    # 3. 绘制 z_q 动态阈值线（橙色实线）
    ax.plot(x, thresholds, color='orange', linewidth=2.0, alpha=0.8,
            label='z_q (dynamic threshold)', zorder=4)

    # 4. 标记异常点（红色散点）
    if len(anomaly_idxs) > 0:
        ax.scatter(anomaly_idxs, timeline[anomaly_idxs],
                   c='red', s=25, zorder=5, edgecolors='darkred',
                   linewidths=0.5,
                   label=f'Anomaly ({len(anomaly_idxs)} points)')

    # 5. 添加窗口分界线（浅灰色竖线）
    if n_nodes > 1:
        for w in range(1, n_windows):
            boundary = w * n_nodes
            if boundary < total_len:
                ax.axvline(x=boundary, color='gray', alpha=0.15,
                           linewidth=0.5, linestyle=':')

    # 6. 添加窗口编号标注（间隔标注，避免拥挤）
    label_interval = max(1, n_windows // 20)
    for w in range(0, n_windows, label_interval):
        center = w * n_nodes + n_nodes // 2
        if center < total_len:
            ax.text(center, ax.get_ylim()[0], f'W{w}',
                    ha='center', va='top', fontsize=6, color='gray', alpha=0.7)

    ax.set_xlabel('Global Timeline Index (window x node)', fontsize=11)
    ax.set_ylabel('Score', fontsize=11)
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.legend(loc='upper right', fontsize=10)
    ax.grid(True, alpha=0.2)

    plt.tight_layout()
    plt.savefig(output_path, dpi=200, bbox_inches='tight')
    plt.close(fig)
    print(f"  Plot saved: {output_path}")


def plot_anomaly_heatmap(anomaly_matrix, curve_names, title, output_path,
                         window_starts=None):
    """
    绘制异常热力图：x=窗口，y=节点，红色=异常

    参数:
        anomaly_matrix: ndarray (n_windows, n_nodes), 0/1
        curve_names: 节点名列表
        title: 图标题
        output_path: 输出路径
        window_starts: 窗口起始时间（用于 x 轴标签）
    """
    n_windows, n_nodes = anomaly_matrix.shape

    fig_height = max(4, n_nodes * 0.4 + 2)
    fig, ax = plt.subplots(figsize=(min(24, n_windows * 0.15 + 4), fig_height))

    # 使用红白配色
    cmap = plt.cm.colors.ListedColormap(['white', '#FF4444'])
    im = ax.imshow(anomaly_matrix.T, aspect='auto', cmap=cmap,
                   interpolation='nearest', vmin=0, vmax=1)

    ax.set_yticks(range(n_nodes))
    ax.set_yticklabels(curve_names, fontsize=8)

    # x 轴标签
    if n_windows <= 30:
        ax.set_xticks(range(n_windows))
        if window_starts is not None:
            labels = [str(ws)[:10] for ws in window_starts]
            ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=6)
        else:
            ax.set_xticklabels([f'W{w}' for w in range(n_windows)], fontsize=7)
    else:
        tick_interval = max(1, n_windows // 20)
        ticks = list(range(0, n_windows, tick_interval))
        ax.set_xticks(ticks)
        ax.set_xticklabels([f'W{w}' for w in ticks], fontsize=7)

    ax.set_xlabel('Window', fontsize=11)
    ax.set_ylabel('Node', fontsize=11)
    ax.set_title(title, fontsize=13, fontweight='bold')

    # 标注异常数量
    for i in range(n_nodes):
        cnt = anomaly_matrix[:, i].sum()
        if cnt > 0:
            ax.text(n_windows + 0.5, i, f'{int(cnt)}',
                    va='center', fontsize=8, color='red', fontweight='bold')

    plt.tight_layout()
    plt.savefig(output_path, dpi=200, bbox_inches='tight')
    plt.close(fig)
    print(f"  Heatmap saved: {output_path}")


def plot_node_scores_comparison(scores_dict, n_nodes, n_windows, curve_names,
                                anomaly_matrix, title, output_path):
    """
    绘制各节点分数随窗口变化的折线图，异常窗口标红

    参数:
        scores_dict: {node_idx: list of float}
        n_nodes, n_windows: 尺寸
        curve_names: 节点名列表
        anomaly_matrix: (n_windows, n_nodes), 0/1
        title: 图标题
        output_path: 输出路径
    """
    fig, ax = plt.subplots(figsize=(20, 8))

    colors = plt.cm.tab20(np.linspace(0, 1, n_nodes))
    x = np.arange(n_windows)

    for i in range(n_nodes):
        scores = np.array(scores_dict[i])
        anomaly_wins = np.where(anomaly_matrix[:, i] == 1)[0]

        ax.plot(x, scores, color=colors[i], alpha=0.6, linewidth=1.0,
                label=curve_names[i])

        if len(anomaly_wins) > 0:
            ax.scatter(anomaly_wins, scores[anomaly_wins],
                       color='red', s=40, zorder=5, edgecolors='darkred',
                       linewidths=0.5)

    ax.set_xlabel('Window Index', fontsize=11)
    ax.set_ylabel('Score', fontsize=11)
    ax.set_title(title, fontsize=14, fontweight='bold')

    # 图例：如果节点太多只显示前10个
    if n_nodes <= 15:
        ax.legend(loc='upper right', fontsize=8, ncol=2)
    else:
        ax.legend(loc='upper right', fontsize=7, ncol=3,
                  title=f'{n_nodes} nodes (top shown)')

    ax.grid(True, alpha=0.2)
    plt.tight_layout()
    plt.savefig(output_path, dpi=200, bbox_inches='tight')
    plt.close(fig)
    print(f"  Node comparison saved: {output_path}")


def generate_all_plots(results, output_dir):
    """
    生成所有可视化图表

    参数:
        results: pipeline.run_pipeline() 的返回值
        output_dir: 输出目录
    """
    plot_dir = os.path.join(output_dir, 'plots')
    os.makedirs(plot_dir, exist_ok=True)

    curve_names = results['curve_names']
    n_nodes = results['n_nodes']
    n_windows = results['n_windows']

    print("\n[可视化] 生成检测结果图表...")

    # ========== 1. 各方法单独检测图 ==========
    for method_name, det in results['method_ispot_results'].items():
        print(f"\n  --- {method_name} ---")

        # 1a. I-SPOT 检测图（全局时间线）
        plot_ispot_detection(
            timeline=det['timeline'],
            ispot_result=det['ispot_result'],
            index_map=det['index_map'],
            n_nodes=n_nodes,
            n_windows=n_windows,
            curve_names=curve_names,
            title=f'I-SPOT Detection: {method_name} (normalized scores)',
            output_path=os.path.join(plot_dir, f'{method_name}_ispot.png'),
            anomaly_matrix=det['anomaly_matrix'],
        )

        # 1b. 异常热力图
        plot_anomaly_heatmap(
            anomaly_matrix=det['anomaly_matrix'],
            curve_names=curve_names,
            title=f'Anomaly Heatmap: {method_name}',
            output_path=os.path.join(plot_dir, f'{method_name}_heatmap.png'),
            window_starts=results['window_starts'],
        )

        # 1c. 节点分数折线对比图
        plot_node_scores_comparison(
            scores_dict=results['normalized_scores'][method_name],
            n_nodes=n_nodes,
            n_windows=n_windows,
            curve_names=curve_names,
            anomaly_matrix=det['anomaly_matrix'],
            title=f'Node Scores: {method_name} (anomalies in red)',
            output_path=os.path.join(
                plot_dir, f'{method_name}_node_scores.png'),
        )

    # ========== 2. 融合后检测图 ==========
    fused_ispot = results['fused_ispot']
    print(f"\n  --- Fused (weighted average) ---")

    # 2a. I-SPOT 检测图
    plot_ispot_detection(
        timeline=fused_ispot['timeline'],
        ispot_result=fused_ispot['ispot_result'],
        index_map=fused_ispot['index_map'],
        n_nodes=n_nodes,
        n_windows=n_windows,
        curve_names=curve_names,
        title=f'I-SPOT Detection: Fused Scores (weights={results["active_weights"]})',
        output_path=os.path.join(plot_dir, 'fused_ispot.png'),
        anomaly_matrix=fused_ispot['anomaly_matrix'],
    )

    # 2b. 融合异常热力图
    plot_anomaly_heatmap(
        anomaly_matrix=fused_ispot['anomaly_matrix'],
        curve_names=curve_names,
        title='Anomaly Heatmap: Fused Result',
        output_path=os.path.join(plot_dir, 'fused_heatmap.png'),
        window_starts=results['window_starts'],
    )

    # 2c. 融合分数节点折线图
    plot_node_scores_comparison(
        scores_dict=results['fused_scores'],
        n_nodes=n_nodes,
        n_windows=n_windows,
        curve_names=curve_names,
        anomaly_matrix=fused_ispot['anomaly_matrix'],
        title='Node Scores: Fused (anomalies in red)',
        output_path=os.path.join(plot_dir, 'fused_node_scores.png'),
    )

    # ========== 3. 综合对比图 ==========
    print(f"\n  --- Summary comparison ---")
    _plot_method_comparison(results, plot_dir)

    print(f"\n[可视化] 所有图表已保存到: {plot_dir}/")


def _plot_method_comparison(results, plot_dir):
    """
    各方法检测结果对比总览：每个方法一行热力图，最后一行是融合结果
    """
    method_names = list(results['method_ispot_results'].keys())
    n_methods = len(method_names) + 1  # +1 for fused
    n_nodes = results['n_nodes']
    n_windows = results['n_windows']
    curve_names = results['curve_names']

    fig_height = max(6, n_methods * (n_nodes * 0.3 + 1.5))
    fig, axes = plt.subplots(n_methods, 1,
                             figsize=(min(20, n_windows * 0.12 + 4), fig_height),
                             sharex=True)

    if n_methods == 1:
        axes = [axes]

    cmap = plt.cm.colors.ListedColormap(['#F0F0F0', '#FF4444'])

    for idx, method_name in enumerate(method_names):
        det = results['method_ispot_results'][method_name]
        ax = axes[idx]
        ax.imshow(det['anomaly_matrix'].T, aspect='auto', cmap=cmap,
                  interpolation='nearest', vmin=0, vmax=1)
        ax.set_yticks(range(n_nodes))
        ax.set_yticklabels(curve_names, fontsize=7)
        ax.set_ylabel(method_name, fontsize=10, fontweight='bold')

        n_det = det['anomaly_matrix'].sum()
        ax.set_title(f'{method_name}: {int(n_det)} anomaly (node, window) pairs',
                     fontsize=10, loc='left')

    # 融合结果
    ax = axes[-1]
    fused_ispot = results['fused_ispot']
    ax.imshow(fused_ispot['anomaly_matrix'].T, aspect='auto', cmap=cmap,
              interpolation='nearest', vmin=0, vmax=1)
    ax.set_yticks(range(n_nodes))
    ax.set_yticklabels(curve_names, fontsize=7)
    ax.set_ylabel('FUSED', fontsize=10, fontweight='bold', color='darkblue')
    n_det = fused_ispot['anomaly_matrix'].sum()
    ax.set_title(f'Fused: {int(n_det)} anomaly (node, window) pairs',
                 fontsize=10, loc='left', color='darkblue')
    ax.set_xlabel('Window Index', fontsize=10)

    plt.suptitle('CSAD-AT Detection Results Comparison',
                 fontsize=14, fontweight='bold', y=1.01)
    plt.tight_layout()
    plt.savefig(os.path.join(plot_dir, 'comparison_overview.png'),
                dpi=200, bbox_inches='tight')
    plt.close(fig)
    print(f"  Comparison overview saved: {plot_dir}/comparison_overview.png")
