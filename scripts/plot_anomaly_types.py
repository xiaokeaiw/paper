"""
绘制四种时间序列异常类型示意图
(a) 点异常（全局点异常 + 局部点异常）
(b) 片段异常（波形异常 + 季节性异常 + 趋势异常）
(c) 变量间关联异常
(d) 节点级异常

输出: 四张独立 PNG 图片，适合论文插图使用
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.collections import LineCollection

# ============================================================
# 全局样式设置 - 学术论文风格
# ============================================================
plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['Droid Sans Fallback', 'SimHei', 'SimSun', 'DejaVu Sans'],
    'axes.unicode_minus': False,
    'font.size': 11,
    'axes.labelsize': 12,
    'axes.titlesize': 13,
    'legend.fontsize': 10,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'axes.linewidth': 0.8,
    'lines.linewidth': 1.5,
    'axes.grid': False,
})

np.random.seed(42)
OUTPUT_DIR = 'files/Img/'


def smooth(y, window=5):
    """简单移动平均平滑"""
    kernel = np.ones(window) / window
    return np.convolve(y, kernel, mode='same')


# ============================================================
# 图 (a): 点异常 - 全局点异常 + 局部点异常
# ============================================================
def plot_point_anomaly():
    fig, ax = plt.subplots(figsize=(8, 3.2))

    T = 300
    t = np.arange(T)

    # 生成带有日周期模式的正常数据
    base = (
        50
        + 8 * np.sin(2 * np.pi * t / 60)          # 主周期
        + 3 * np.sin(2 * np.pi * t / 25 + 1.2)    # 次周期
        + np.random.normal(0, 1.5, T)              # 噪声
    )
    y = smooth(base, 3)

    # 绘制正常范围带（均值 +/- 2sigma 灰色带）
    rolling_mean = smooth(y, 15)
    rolling_std = np.full(T, np.std(y) * 0.6)
    upper = rolling_mean + 2 * rolling_std
    lower = rolling_mean - 2 * rolling_std
    ax.fill_between(t, lower, upper, color='#E8E8E8', alpha=0.6, label='正常范围')

    # 正常曲线
    ax.plot(t, y, color='#4472C4', linewidth=1.2, label='时间序列', zorder=3)

    # 全局点异常 - 远超整体分布
    global_anomaly_idx = [75, 210]
    global_anomaly_vals = [y[75] + 28, y[210] - 25]
    y_plot = y.copy()
    for idx, val in zip(global_anomaly_idx, global_anomaly_vals):
        y_plot[idx] = val

    ax.scatter(global_anomaly_idx, global_anomaly_vals,
               color='#C00000', s=60, zorder=5, edgecolors='#C00000', linewidth=1.2)
    # 标注
    ax.annotate('全局点异常', xy=(75, global_anomaly_vals[0]),
                xytext=(95, global_anomaly_vals[0] + 5),
                fontsize=9, color='#C00000', fontweight='bold',
                arrowprops=dict(arrowstyle='->', color='#C00000', lw=1.0))
    ax.annotate('全局点异常', xy=(210, global_anomaly_vals[1]),
                xytext=(225, global_anomaly_vals[1] - 6),
                fontsize=9, color='#C00000', fontweight='bold',
                arrowprops=dict(arrowstyle='->', color='#C00000', lw=1.0))

    # 局部点异常 - 在局部上下文中偏离（不超出全局范围，但偏离局部趋势）
    local_anomaly_idx = [140, 255]
    # 在局部高峰期出现低谷 / 在局部低谷期出现高值
    local_anomaly_vals = [y[140] - 14, y[255] + 13]
    ax.scatter(local_anomaly_idx, local_anomaly_vals,
               color='#ED7D31', s=60, zorder=5, marker='D',
               edgecolors='#ED7D31', linewidth=1.2)
    ax.annotate('局部点异常', xy=(140, local_anomaly_vals[0]),
                xytext=(150, local_anomaly_vals[0] - 6),
                fontsize=9, color='#ED7D31', fontweight='bold',
                arrowprops=dict(arrowstyle='->', color='#ED7D31', lw=1.0))
    ax.annotate('局部点异常', xy=(255, local_anomaly_vals[1]),
                xytext=(262, local_anomaly_vals[1] + 5),
                fontsize=9, color='#ED7D31', fontweight='bold',
                arrowprops=dict(arrowstyle='->', color='#ED7D31', lw=1.0))

    ax.set_xlabel('时间步')
    ax.set_ylabel('观测值')
    ax.set_title('(a) 点异常', fontweight='bold', pad=10)
    ax.legend(loc='upper right', framealpha=0.9, edgecolor='gray')
    ax.set_xlim(0, T)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR + 'anomaly_type_a_point.png', bbox_inches='tight')
    plt.savefig(OUTPUT_DIR + 'anomaly_type_a_point.pdf', bbox_inches='tight')
    plt.close()
    print('[OK] (a) 点异常')


# ============================================================
# 图 (b): 片段异常 - 波形异常 + 季节性异常 + 趋势异常
# ============================================================
def plot_subsequence_anomaly():
    fig, axes = plt.subplots(3, 1, figsize=(8, 7.5), sharex=True)

    T = 400
    t = np.arange(T)

    # ---------- (b1) 波形异常 ----------
    ax = axes[0]
    y1 = 50 + 10 * np.sin(2 * np.pi * t / 50) + np.random.normal(0, 1.2, T)
    y1 = smooth(y1, 3)
    # 异常段：振幅急剧增大 + 频率改变
    anom_start, anom_end = 160, 230
    y1_anom = y1.copy()
    seg = t[anom_start:anom_end] - anom_start
    y1_anom[anom_start:anom_end] = (
        50 + 22 * np.sin(2 * np.pi * seg / 20) + np.random.normal(0, 1.5, anom_end - anom_start)
    )

    ax.axvspan(anom_start, anom_end, color='#FFD6D6', alpha=0.5, zorder=1)
    ax.plot(t[:anom_start], y1_anom[:anom_start], color='#4472C4', linewidth=1.2)
    ax.plot(t[anom_start:anom_end], y1_anom[anom_start:anom_end],
            color='#C00000', linewidth=1.5, zorder=3)
    ax.plot(t[anom_end:], y1_anom[anom_end:], color='#4472C4', linewidth=1.2)
    # 虚线表示正常应有的模式
    ax.plot(t[anom_start:anom_end], y1[anom_start:anom_end],
            color='#4472C4', linewidth=1.0, linestyle='--', alpha=0.5)

    ax.annotate('波形异常\n(振幅与频率突变)',
                xy=((anom_start + anom_end) / 2, 72),
                xytext=(anom_end + 20, 75),
                fontsize=9, color='#C00000', fontweight='bold',
                ha='left', va='center',
                arrowprops=dict(arrowstyle='->', color='#C00000', lw=1.0))
    ax.set_ylabel('观测值')
    ax.set_title('(b) 片段异常（模式异常）', fontweight='bold', pad=8)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.text(0.01, 0.92, 'b-1 波形异常', transform=ax.transAxes,
            fontsize=10, fontweight='bold', color='#333333', va='top')

    # ---------- (b2) 季节性异常 ----------
    ax = axes[1]
    period = 60
    y2 = 50 + 12 * np.sin(2 * np.pi * t / period) + np.random.normal(0, 1.0, T)
    y2 = smooth(y2, 3)
    # 异常段：周期被打破（周期拉长或消失）
    anom_start2, anom_end2 = 180, 280
    y2_anom = y2.copy()
    seg2 = t[anom_start2:anom_end2] - anom_start2
    # 周期变为原来的2.5倍 + 振幅减弱
    y2_anom[anom_start2:anom_end2] = (
        50 + 5 * np.sin(2 * np.pi * seg2 / 150) + np.random.normal(0, 1.8, anom_end2 - anom_start2)
    )

    ax.axvspan(anom_start2, anom_end2, color='#FFF3CD', alpha=0.6, zorder=1)
    ax.plot(t[:anom_start2], y2_anom[:anom_start2], color='#4472C4', linewidth=1.2)
    ax.plot(t[anom_start2:anom_end2], y2_anom[anom_start2:anom_end2],
            color='#ED7D31', linewidth=1.5, zorder=3)
    ax.plot(t[anom_end2:], y2_anom[anom_end2:], color='#4472C4', linewidth=1.2)
    ax.plot(t[anom_start2:anom_end2], y2[anom_start2:anom_end2],
            color='#4472C4', linewidth=1.0, linestyle='--', alpha=0.5)

    ax.annotate('季节性异常\n(周期规律被打破)',
                xy=((anom_start2 + anom_end2) / 2, 55),
                xytext=(anom_end2 + 15, 62),
                fontsize=9, color='#ED7D31', fontweight='bold',
                ha='left', va='center',
                arrowprops=dict(arrowstyle='->', color='#ED7D31', lw=1.0))
    ax.set_ylabel('观测值')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.text(0.01, 0.92, 'b-2 季节性异常', transform=ax.transAxes,
            fontsize=10, fontweight='bold', color='#333333', va='top')

    # ---------- (b3) 趋势异常 ----------
    ax = axes[2]
    trend_normal = 0.02 * t
    y3 = (
        40 + trend_normal
        + 6 * np.sin(2 * np.pi * t / 55)
        + np.random.normal(0, 1.2, T)
    )
    y3 = smooth(y3, 3)
    # 异常段：趋势突变（突然快速上升后平台期）
    anom_start3, anom_end3 = 200, 290
    y3_anom = y3.copy()
    seg3 = t[anom_start3:anom_end3] - anom_start3
    n_seg3 = anom_end3 - anom_start3
    # 突然跳升趋势
    ramp = np.minimum(seg3 * 0.25, 15)
    y3_anom[anom_start3:anom_end3] = (
        y3[anom_start3]
        + ramp
        + 3 * np.sin(2 * np.pi * seg3 / 55)
        + np.random.normal(0, 1.2, n_seg3)
    )
    # 跳升后恢复正常趋势
    offset = y3_anom[anom_end3 - 1] - y3[anom_end3 - 1]
    recovery = np.linspace(offset, 0, min(40, T - anom_end3))
    y3_anom[anom_end3:anom_end3 + len(recovery)] += recovery

    ax.axvspan(anom_start3, anom_end3, color='#D6F0D6', alpha=0.5, zorder=1)
    ax.plot(t[:anom_start3], y3_anom[:anom_start3], color='#4472C4', linewidth=1.2)
    ax.plot(t[anom_start3:anom_end3], y3_anom[anom_start3:anom_end3],
            color='#548235', linewidth=1.5, zorder=3)
    ax.plot(t[anom_end3:], y3_anom[anom_end3:], color='#4472C4', linewidth=1.2)
    ax.plot(t[anom_start3:anom_end3], y3[anom_start3:anom_end3],
            color='#4472C4', linewidth=1.0, linestyle='--', alpha=0.5)

    ax.annotate('趋势异常\n(趋势突变)',
                xy=(250, y3_anom[250]),
                xytext=(anom_end3 + 15, y3_anom[250] + 3),
                fontsize=9, color='#548235', fontweight='bold',
                ha='left', va='center',
                arrowprops=dict(arrowstyle='->', color='#548235', lw=1.0))
    ax.set_xlabel('时间步')
    ax.set_ylabel('观测值')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.text(0.01, 0.92, 'b-3 趋势异常', transform=ax.transAxes,
            fontsize=10, fontweight='bold', color='#333333', va='top')

    # 图例（顶部子图）
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], color='#4472C4', linewidth=1.2, label='正常序列'),
        Line2D([0], [0], color='#4472C4', linewidth=1.0, linestyle='--',
               alpha=0.5, label='正常预期模式'),
        mpatches.Patch(facecolor='#FFD6D6', alpha=0.5, label='异常片段'),
    ]
    axes[0].legend(handles=legend_elements, loc='upper right',
                   framealpha=0.9, edgecolor='gray')

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR + 'anomaly_type_b_subsequence.png', bbox_inches='tight')
    plt.savefig(OUTPUT_DIR + 'anomaly_type_b_subsequence.pdf', bbox_inches='tight')
    plt.close()
    print('[OK] (b) 片段异常')


# ============================================================
# 图 (c): 变量间关联异常
# ============================================================
def plot_correlation_anomaly():
    fig, axes = plt.subplots(2, 1, figsize=(8, 5.2), sharex=True)

    T = 350
    t = np.arange(T)

    # 生成两个正相关变量
    base_signal = (
        8 * np.sin(2 * np.pi * t / 60)
        + 4 * np.sin(2 * np.pi * t / 25 + 0.8)
    )
    var1 = 50 + base_signal + np.random.normal(0, 1.5, T)
    var2 = 45 + 0.85 * base_signal + np.random.normal(0, 1.5, T)
    var1 = smooth(var1, 3)
    var2 = smooth(var2, 3)

    # 异常段：变量2的关联模式突然变化（反相关或无关）
    anom_start, anom_end = 150, 230
    var2_anom = var2.copy()
    seg = t[anom_start:anom_end] - anom_start
    # 变量2在异常段变为反相关
    var2_anom[anom_start:anom_end] = (
        45 - 0.7 * base_signal[anom_start:anom_end]
        + np.random.normal(0, 1.8, anom_end - anom_start)
    )

    # 上方子图：两个变量的时序
    ax = axes[0]
    ax.axvspan(anom_start, anom_end, color='#FFE0E0', alpha=0.5, zorder=1)
    ax.plot(t, var1, color='#4472C4', linewidth=1.3, label='变量 $X_1$', zorder=3)
    ax.plot(t[:anom_start], var2_anom[:anom_start],
            color='#ED7D31', linewidth=1.3, label='变量 $X_2$', zorder=3)
    ax.plot(t[anom_start:anom_end], var2_anom[anom_start:anom_end],
            color='#C00000', linewidth=1.8, zorder=4)
    ax.plot(t[anom_end:], var2_anom[anom_end:],
            color='#ED7D31', linewidth=1.3, zorder=3)
    # 虚线：变量2原本应有的趋势
    ax.plot(t[anom_start:anom_end], var2[anom_start:anom_end],
            color='#ED7D31', linewidth=1.0, linestyle='--', alpha=0.4)

    ax.annotate('关联异常区间\n($X_2$与$X_1$关联模式改变)',
                xy=((anom_start + anom_end) / 2, 33),
                xytext=(anom_end + 15, 30),
                fontsize=9, color='#C00000', fontweight='bold',
                ha='left',
                arrowprops=dict(arrowstyle='->', color='#C00000', lw=1.0))
    ax.set_ylabel('观测值')
    ax.set_title('(c) 变量间关联异常', fontweight='bold', pad=8)
    ax.legend(loc='upper right', framealpha=0.9, edgecolor='gray')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    # 下方子图：滑动窗口相关系数
    ax2 = axes[1]
    window_corr = 30
    corr_values = []
    corr_t = []
    for i in range(window_corr, T):
        w1 = var1[i - window_corr:i]
        w2 = var2_anom[i - window_corr:i]
        r = np.corrcoef(w1, w2)[0, 1]
        corr_values.append(r)
        corr_t.append(i)
    corr_values = np.array(corr_values)
    corr_t = np.array(corr_t)

    ax2.axvspan(anom_start, anom_end, color='#FFE0E0', alpha=0.5, zorder=1)
    ax2.axhline(0, color='gray', linewidth=0.5, linestyle='-')
    ax2.plot(corr_t, corr_values, color='#7030A0', linewidth=1.3, zorder=3)
    ax2.fill_between(corr_t, corr_values, 0, where=(corr_values < 0),
                     color='#C00000', alpha=0.15, zorder=2)
    ax2.set_ylabel('滑动相关系数')
    ax2.set_xlabel('时间步')
    ax2.set_ylim(-1.1, 1.1)
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)
    ax2.text(0.01, 0.92, '滑动窗口相关系数 (窗口=30)',
             transform=ax2.transAxes, fontsize=9, color='#333333', va='top')

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR + 'anomaly_type_c_correlation.png', bbox_inches='tight')
    plt.savefig(OUTPUT_DIR + 'anomaly_type_c_correlation.pdf', bbox_inches='tight')
    plt.close()
    print('[OK] (c) 变量间关联异常')


# ============================================================
# 图 (d): 节点级异常（分布式集群场景）
# ============================================================
def plot_node_anomaly():
    fig, ax = plt.subplots(figsize=(8, 3.8))

    T = 350
    t = np.arange(T)
    n_normal_nodes = 6

    # 共同的基础信号（集群行为）
    cluster_signal = (
        50
        + 10 * np.sin(2 * np.pi * t / 55)
        + 4 * np.sin(2 * np.pi * t / 22 + 0.5)
    )

    # 正常节点 - 围绕集群信号小幅波动
    normal_curves = []
    colors_normal = ['#A8C4E0', '#8DB4D8', '#7BA6CF', '#B8D0E8', '#9BBDE2', '#AECCF0']
    for i in range(n_normal_nodes):
        offset = np.random.uniform(-2, 2)
        scale = np.random.uniform(0.92, 1.08)
        noise = np.random.normal(0, 1.2, T)
        curve = offset + scale * cluster_signal + noise
        curve = smooth(curve, 3)
        normal_curves.append(curve)

    # 异常节点 - 前半段正常，中间开始偏离
    anom_start = 100
    anomaly_curve = np.zeros(T)
    # 正常段
    anomaly_curve[:anom_start] = (
        cluster_signal[:anom_start]
        + np.random.normal(0, 1.5, anom_start)
    )
    # 异常段：逐渐偏离，行为模式改变
    seg = t[anom_start:] - anom_start
    drift = 0.06 * seg  # 逐渐漂移
    anomaly_curve[anom_start:] = (
        cluster_signal[anom_start:]
        + drift
        + 6 * np.sin(2 * np.pi * seg / 18)  # 不同频率
        + np.random.normal(0, 2.0, T - anom_start)
    )
    anomaly_curve = smooth(anomaly_curve, 3)

    # 绘制集群均值带（正常节点的范围）
    all_normal = np.array(normal_curves)
    mean_normal = np.mean(all_normal, axis=0)
    std_normal = np.std(all_normal, axis=0)
    ax.fill_between(t, mean_normal - 2 * std_normal, mean_normal + 2 * std_normal,
                    color='#DCEAF7', alpha=0.6, label='集群正常范围', zorder=1)

    # 绘制正常节点
    for i, curve in enumerate(normal_curves):
        label = '正常节点' if i == 0 else None
        ax.plot(t, curve, color=colors_normal[i], linewidth=0.8,
                alpha=0.7, label=label, zorder=2)

    # 绘制集群均值
    ax.plot(t, mean_normal, color='#4472C4', linewidth=1.5,
            linestyle='--', alpha=0.6, label='集群均值', zorder=3)

    # 绘制异常节点
    ax.plot(t[:anom_start + 5], anomaly_curve[:anom_start + 5],
            color='#C00000', linewidth=1.8, zorder=5)
    ax.plot(t[anom_start:], anomaly_curve[anom_start:],
            color='#C00000', linewidth=2.0, label='异常节点', zorder=5)

    # 偏离起点标记
    ax.axvline(anom_start, color='#C00000', linewidth=0.8, linestyle=':', alpha=0.6)

    # 双箭头标注偏离距离
    mid_t = 260
    ax.annotate('',
                xy=(mid_t, mean_normal[mid_t]),
                xytext=(mid_t, anomaly_curve[mid_t]),
                arrowprops=dict(arrowstyle='<->', color='#C00000', lw=1.2))
    ax.text(mid_t + 5, (mean_normal[mid_t] + anomaly_curve[mid_t]) / 2,
            '偏离', fontsize=9, color='#C00000', fontweight='bold', va='center')

    ax.annotate('偏离起点', xy=(anom_start, anomaly_curve[anom_start]),
                xytext=(anom_start - 50, anomaly_curve[anom_start] + 18),
                fontsize=9, color='#C00000', fontweight='bold',
                arrowprops=dict(arrowstyle='->', color='#C00000', lw=1.0))

    ax.set_xlabel('时间步')
    ax.set_ylabel('观测值')
    ax.set_title('(d) 节点级异常', fontweight='bold', pad=10)
    ax.legend(loc='upper left', framealpha=0.9, edgecolor='gray', ncol=2)
    ax.set_xlim(0, T)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR + 'anomaly_type_d_node.png', bbox_inches='tight')
    plt.savefig(OUTPUT_DIR + 'anomaly_type_d_node.pdf', bbox_inches='tight')
    plt.close()
    print('[OK] (d) 节点级异常')


# ============================================================
# 主函数
# ============================================================
if __name__ == '__main__':
    import os
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    plot_point_anomaly()
    plot_subsequence_anomaly()
    plot_correlation_anomaly()
    plot_node_anomaly()

    print('\n全部完成！图片保存在:', OUTPUT_DIR)
    print('  anomaly_type_a_point.png / .pdf')
    print('  anomaly_type_b_subsequence.png / .pdf')
    print('  anomaly_type_c_correlation.png / .pdf')
    print('  anomaly_type_d_node.png / .pdf')
