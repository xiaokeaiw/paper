"""
CSAD-AT Visualization Module

Plot style:
  - Blue curve: score series
  - Red dashed line: t threshold (POT initial threshold)
  - Orange solid line: z_q dynamic threshold
  - Red scatter: anomaly points
  - Gray shaded region: SPOT initialization phase

All node names are desensitized (Node 1, Node 2, ...).
"""

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os


try:
    plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
except Exception:
    pass


def _desensitize_names(curve_names):
    """Map real node names to Node 1, Node 2, ..."""
    return [f'Node {i+1}' for i in range(len(curve_names))]


def plot_ispot_detection(timeline, ispot_result, index_map, n_nodes, n_windows,
                         curve_names, title, output_path,
                         anomaly_matrix=None):
    """
    Plot I-SPOT detection result (single panel).
    Includes initialization phase shading. Node names desensitized.
    """
    display_names = _desensitize_names(curve_names)

    thresholds = np.array(ispot_result['thresholds'])
    t0_values = np.array(ispot_result['t0_values'])
    anomaly_idxs = np.array(ispot_result['anomaly_indices'])
    init_len = ispot_result.get('initial_seq_len', 0)

    total_len = len(timeline)
    x = np.arange(total_len)

    fig, ax = plt.subplots(figsize=(24, 8))

    # 0. Shade initialization phase
    if init_len > 0:
        ax.axvspan(0, init_len, color='#E0E0E0', alpha=0.5, zorder=0,
                   label='Initialization')

    # 1. Score series
    ax.plot(x, timeline, color='#4A90D9', alpha=0.7, linewidth=0.8,
            label='Score', zorder=2)

    # 2. t0 threshold (red dashed)
    ax.plot(x, t0_values, 'r--', linewidth=1.0, alpha=0.6,
            label='$t$ (initial threshold)', zorder=3)

    # 3. z_q dynamic threshold (orange solid)
    ax.plot(x, thresholds, color='orange', linewidth=2.0, alpha=0.8,
            label='$z_q$ (dynamic threshold)', zorder=4)

    # 4. Anomaly points (red scatter)
    if len(anomaly_idxs) > 0:
        ax.scatter(anomaly_idxs, timeline[anomaly_idxs],
                   c='red', s=25, zorder=5, edgecolors='darkred',
                   linewidths=0.5,
                   label=f'Anomaly ({len(anomaly_idxs)} pts)')

    # 5. Window boundaries
    if n_nodes > 1:
        for w in range(1, n_windows):
            boundary = w * n_nodes
            if boundary < total_len:
                ax.axvline(x=boundary, color='gray', alpha=0.15,
                           linewidth=0.5, linestyle=':')

    # 6. Window labels
    label_interval = max(1, n_windows // 20)
    for w in range(0, n_windows, label_interval):
        center = w * n_nodes + n_nodes // 2
        if center < total_len:
            ax.text(center, ax.get_ylim()[0], f'W{w}',
                    ha='center', va='top', fontsize=6, color='gray', alpha=0.7)

    ax.set_xlabel('Global Timeline Index (window $\\times$ node)', fontsize=11)
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
    Anomaly heatmap: x=window, y=node, red=anomaly. Node names desensitized.
    """
    display_names = _desensitize_names(curve_names)
    n_windows, n_nodes = anomaly_matrix.shape

    fig_height = max(4, n_nodes * 0.4 + 2)
    fig, ax = plt.subplots(figsize=(min(24, n_windows * 0.15 + 4), fig_height))

    cmap = plt.cm.colors.ListedColormap(['white', '#FF4444'])
    im = ax.imshow(anomaly_matrix.T, aspect='auto', cmap=cmap,
                   interpolation='nearest', vmin=0, vmax=1)

    ax.set_yticks(range(n_nodes))
    ax.set_yticklabels(display_names, fontsize=8)

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
    Per-node score line chart. Node names desensitized.
    """
    display_names = _desensitize_names(curve_names)
    fig, ax = plt.subplots(figsize=(20, 8))

    colors = plt.cm.tab20(np.linspace(0, 1, n_nodes))
    x = np.arange(n_windows)

    for i in range(n_nodes):
        scores = np.array(scores_dict[i])
        anomaly_wins = np.where(anomaly_matrix[:, i] == 1)[0]

        ax.plot(x, scores, color=colors[i], alpha=0.6, linewidth=1.0,
                label=display_names[i])

        if len(anomaly_wins) > 0:
            ax.scatter(anomaly_wins, scores[anomaly_wins],
                       color='red', s=40, zorder=5, edgecolors='darkred',
                       linewidths=0.5)

    ax.set_xlabel('Window Index', fontsize=11)
    ax.set_ylabel('Score', fontsize=11)
    ax.set_title(title, fontsize=14, fontweight='bold')

    if n_nodes <= 15:
        ax.legend(loc='upper right', fontsize=8, ncol=2)
    else:
        ax.legend(loc='upper right', fontsize=7, ncol=3,
                  title=f'{n_nodes} nodes')

    ax.grid(True, alpha=0.2)
    plt.tight_layout()
    plt.savefig(output_path, dpi=200, bbox_inches='tight')
    plt.close(fig)
    print(f"  Node comparison saved: {output_path}")


def plot_spot_vs_ispot(timeline, spot_result, ispot_result,
                       n_nodes, n_windows, title, output_path):
    """
    SPOT vs I-SPOT comparison: top panel = classic SPOT, bottom panel = I-SPOT.
    Both share x-axis. Initialization phase shaded in both.
    No weight labels in title.
    """
    fig, (ax_top, ax_bot) = plt.subplots(2, 1, figsize=(24, 12),
                                          sharex=True)

    total_len = len(timeline)
    x = np.arange(total_len)

    for ax, result, method_label in [
        (ax_top, spot_result, 'Classic SPOT'),
        (ax_bot, ispot_result, 'I-SPOT'),
    ]:
        thresholds = np.array(result['thresholds'])
        t0_values = np.array(result['t0_values'])
        anomaly_idxs = np.array(result['anomaly_indices'])
        init_len = result.get('initial_seq_len', 0)

        # Initialization shading
        if init_len > 0:
            ax.axvspan(0, init_len, color='#E0E0E0', alpha=0.5, zorder=0,
                       label='Initialization')

        # Score
        ax.plot(x, timeline, color='#4A90D9', alpha=0.7, linewidth=0.8,
                label='Score', zorder=2)

        # t0
        ax.plot(x, t0_values, 'r--', linewidth=1.0, alpha=0.6,
                label='$t$ (initial threshold)', zorder=3)

        # z_q
        ax.plot(x, thresholds, color='orange', linewidth=2.0, alpha=0.8,
                label='$z_q$ (dynamic threshold)', zorder=4)

        # Anomaly points
        if len(anomaly_idxs) > 0:
            ax.scatter(anomaly_idxs, timeline[anomaly_idxs],
                       c='red', s=25, zorder=5, edgecolors='darkred',
                       linewidths=0.5,
                       label=f'Anomaly ({len(anomaly_idxs)} pts)')

        # Window boundaries
        if n_nodes > 1:
            for w in range(1, n_windows):
                boundary = w * n_nodes
                if boundary < total_len:
                    ax.axvline(x=boundary, color='gray', alpha=0.15,
                               linewidth=0.5, linestyle=':')

        ax.set_ylabel('Score', fontsize=11)
        ax.set_title(method_label, fontsize=13, fontweight='bold', loc='left')
        ax.legend(loc='upper right', fontsize=9)
        ax.grid(True, alpha=0.2)

    # Window labels on bottom axis
    label_interval = max(1, n_windows // 20)
    for w in range(0, n_windows, label_interval):
        center = w * n_nodes + n_nodes // 2
        if center < total_len:
            ax_bot.text(center, ax_bot.get_ylim()[0], f'W{w}',
                        ha='center', va='top', fontsize=6,
                        color='gray', alpha=0.7)

    ax_bot.set_xlabel('Global Timeline Index (window $\\times$ node)',
                      fontsize=11)

    fig.suptitle(title, fontsize=14, fontweight='bold', y=1.01)
    plt.tight_layout()
    plt.savefig(output_path, dpi=200, bbox_inches='tight')
    plt.close(fig)
    print(f"  SPOT vs I-SPOT comparison saved: {output_path}")


def generate_all_plots(results, output_dir):
    """
    Generate all visualization charts.
    Node names desensitized. SPOT vs I-SPOT comparison included.
    """
    from .spot import SPOT

    plot_dir = os.path.join(output_dir, 'plots')
    os.makedirs(plot_dir, exist_ok=True)

    curve_names = results['curve_names']
    display_names = _desensitize_names(curve_names)
    n_nodes = results['n_nodes']
    n_windows = results['n_windows']

    print("\n[Visualization] Generating detection result charts...")

    # ========== 1. Per-method detection plots ==========
    for method_name, det in results['method_ispot_results'].items():
        print(f"\n  --- {method_name} ---")

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

        plot_anomaly_heatmap(
            anomaly_matrix=det['anomaly_matrix'],
            curve_names=curve_names,
            title=f'Anomaly Heatmap: {method_name}',
            output_path=os.path.join(plot_dir, f'{method_name}_heatmap.png'),
            window_starts=results['window_starts'],
        )

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

    # ========== 2. Fused detection plots (no weight in title) ==========
    fused_ispot = results['fused_ispot']
    print(f"\n  --- Fused ---")

    plot_ispot_detection(
        timeline=fused_ispot['timeline'],
        ispot_result=fused_ispot['ispot_result'],
        index_map=fused_ispot['index_map'],
        n_nodes=n_nodes,
        n_windows=n_windows,
        curve_names=curve_names,
        title='I-SPOT Detection: Fused Scores',
        output_path=os.path.join(plot_dir, 'fused_ispot.png'),
        anomaly_matrix=fused_ispot['anomaly_matrix'],
    )

    plot_anomaly_heatmap(
        anomaly_matrix=fused_ispot['anomaly_matrix'],
        curve_names=curve_names,
        title='Anomaly Heatmap: Fused Result',
        output_path=os.path.join(plot_dir, 'fused_heatmap.png'),
        window_starts=results['window_starts'],
    )

    plot_node_scores_comparison(
        scores_dict=results['fused_scores'],
        n_nodes=n_nodes,
        n_windows=n_windows,
        curve_names=curve_names,
        anomaly_matrix=fused_ispot['anomaly_matrix'],
        title='Node Scores: Fused (anomalies in red)',
        output_path=os.path.join(plot_dir, 'fused_node_scores.png'),
    )

    # ========== 3. Method comparison overview ==========
    print(f"\n  --- Summary comparison ---")
    _plot_method_comparison(results, plot_dir)

    # ========== 4. SPOT vs I-SPOT comparison ==========
    print(f"\n  --- SPOT vs I-SPOT comparison ---")
    fused_timeline = fused_ispot['timeline']
    fused_ispot_result = fused_ispot['ispot_result']

    # Run classic SPOT on the same fused timeline
    spot = SPOT()
    spot_result = spot.run(
        fused_timeline,
        anomaly_ratio=0.0085,
        level=0.98,
        t_update=50,
    )

    plot_spot_vs_ispot(
        timeline=fused_timeline,
        spot_result=spot_result,
        ispot_result=fused_ispot_result,
        n_nodes=n_nodes,
        n_windows=n_windows,
        title='Fused Scores: Classic SPOT vs I-SPOT',
        output_path=os.path.join(plot_dir, 'spot_vs_ispot_fused.png'),
    )

    # Per-method SPOT vs I-SPOT
    for method_name, det in results['method_ispot_results'].items():
        method_timeline = det['timeline']
        method_ispot_result = det['ispot_result']

        spot_res_method = spot.run(
            method_timeline,
            anomaly_ratio=0.0085,
            level=0.98,
            t_update=50,
        )

        plot_spot_vs_ispot(
            timeline=method_timeline,
            spot_result=spot_res_method,
            ispot_result=method_ispot_result,
            n_nodes=n_nodes,
            n_windows=n_windows,
            title=f'{method_name}: Classic SPOT vs I-SPOT',
            output_path=os.path.join(
                plot_dir, f'{method_name}_spot_vs_ispot.png'),
        )

    print(f"\n[Visualization] All charts saved to: {plot_dir}/")


def _plot_method_comparison(results, plot_dir):
    """
    Method comparison overview heatmap. Node names desensitized. No weight labels.
    """
    method_names = list(results['method_ispot_results'].keys())
    n_methods = len(method_names) + 1
    n_nodes = results['n_nodes']
    n_windows = results['n_windows']
    display_names = _desensitize_names(results['curve_names'])

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
        ax.set_yticklabels(display_names, fontsize=7)
        ax.set_ylabel(method_name, fontsize=10, fontweight='bold')

        n_det = det['anomaly_matrix'].sum()
        ax.set_title(f'{method_name}: {int(n_det)} anomaly (node, window) pairs',
                     fontsize=10, loc='left')

    ax = axes[-1]
    fused_ispot = results['fused_ispot']
    ax.imshow(fused_ispot['anomaly_matrix'].T, aspect='auto', cmap=cmap,
              interpolation='nearest', vmin=0, vmax=1)
    ax.set_yticks(range(n_nodes))
    ax.set_yticklabels(display_names, fontsize=7)
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
