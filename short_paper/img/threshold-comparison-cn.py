import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np

# === 关键设置：确保 PDF 中文字以 TrueType 字体嵌入，可编辑 ===
matplotlib.rcParams['pdf.fonttype'] = 42
matplotlib.rcParams['ps.fonttype'] = 42

# 混合字体
font_path = '/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf'
fm.fontManager.addfont(font_path)
plt.rcParams['font.family'] = ['DejaVu Sans', 'Droid Sans Fallback']
plt.rcParams['axes.unicode_minus'] = False

plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams['font.family'] = ['DejaVu Sans', 'Droid Sans Fallback']
plt.rcParams['axes.unicode_minus'] = False

# 数据准备
thresholds_euc_ae = [3.0, 3.2, 3.4, 3.6, 3.8]
eps_values = [200, 400, 600, 800, 1000]

def normalize_to_range(values, target_min=0, target_max=1):
    min_val = min(values)
    max_val = max(values)
    if max_val == min_val:
        return [target_min] * len(values)
    return [target_min + (target_max - target_min) * (v - min_val) / (max_val - min_val) for v in values]

thresholds_norm = normalize_to_range(thresholds_euc_ae)
eps_norm = normalize_to_range(eps_values)

f1_euclidean = {
    10: [0.7084, 0.8093, 0.8960, 0.9593, 0.0000],
    20: [0.8406, 0.8822, 0.9459, 0.9741, 0.0000],
    30: [0.9020, 0.9243, 0.9614, 0.9596, 0.0000]
}

f1_ae = {
    10: [0.6051, 0.7554, 0.8668, 0.9234, 0.0000],
    20: [0.7522, 0.8802, 0.9449, 0.9595, 0.0000],
    30: [0.8376, 0.9125, 0.9589, 0.9691, 0.0000]
}

f1_dbscan = {
    10: [0.3735, 0.9562, 0.9745, 0.9034, 0.8691],
    20: [0.0585, 0.9016, 0.9738, 0.9467, 0.9079],
    30: [0.0309, 0.7260, 0.9660, 0.9591, 0.9015]
}

# 恢复原始比例：宽15 高4.5，和之前一致
fig, axes = plt.subplots(1, 3, figsize=(15, 4.5), sharey=True)

colors = {
    'euclidean': '#1f77b4',
    'ae': '#2ca02c',
    'dbscan': '#d62728'
}

window_sizes = [10, 20, 30]

for idx, (ax, ws) in enumerate(zip(axes, window_sizes)):
    ax.plot(thresholds_norm, f1_euclidean[ws], marker='o', linestyle='-',
            color=colors['euclidean'], label='Euclidean', linewidth=2, markersize=6,
            markerfacecolor='white', markeredgewidth=1.5)

    ax.plot(thresholds_norm, f1_ae[ws], marker='s', linestyle='--',
            color=colors['ae'], label='AE', linewidth=2, markersize=6,
            markerfacecolor='white', markeredgewidth=1.5)

    ax.plot(eps_norm, f1_dbscan[ws], marker='^', linestyle=':',
            color=colors['dbscan'], label='DBSCAN', linewidth=2, markersize=6,
            markerfacecolor='white', markeredgewidth=1.5)

    ax.set_xlim(-0.05, 1.05)
    ax.set_xticks([])

    ax_thresh = ax.secondary_xaxis('bottom')
    ax_thresh.set_xlabel('')
    ax_thresh.set_xticks([])
    ax_thresh.set_xticklabels([])

    ax_eps = ax.secondary_xaxis('top')
    ax_eps.set_xlabel('')
    ax_eps.set_xticks([])
    ax_eps.set_xticklabels([])

    # 标注欧氏距离
    for i, (x, y) in enumerate(zip(thresholds_norm, f1_euclidean[ws])):
        if y > 0:
            ax.annotate(f'{thresholds_euc_ae[i]}', xy=(x, y), xytext=(0, 9),
                       textcoords='offset points', ha='center', va='bottom',
                       fontsize=9, color=colors['euclidean'], fontweight='bold')
        else:
            ax.annotate(f'{thresholds_euc_ae[i]}', xy=(x, y), xytext=(-8, 6),
                       textcoords='offset points', ha='center', va='bottom',
                       fontsize=9, color=colors['euclidean'], fontweight='bold')

    # 标注AE
    for i, (x, y) in enumerate(zip(thresholds_norm, f1_ae[ws])):
        if y > 0:
            ax.annotate(f'{thresholds_euc_ae[i]}', xy=(x, y), xytext=(0, -13),
                       textcoords='offset points', ha='center', va='top',
                       fontsize=9, color=colors['ae'], fontweight='bold')
        else:
            ax.annotate(f'{thresholds_euc_ae[i]}', xy=(x, y), xytext=(8, 6),
                       textcoords='offset points', ha='center', va='bottom',
                       fontsize=9, color=colors['ae'], fontweight='bold')

    # 标注DBSCAN
    for i, (x, y) in enumerate(zip(eps_norm, f1_dbscan[ws])):
        ax.annotate(f'{eps_values[i]}', xy=(x, y), xytext=(0, 9),
                   textcoords='offset points', ha='center', va='bottom',
                   fontsize=9, color=colors['dbscan'], fontweight='bold')

    if idx == 0:
        ax.set_ylabel('F1 \u5206\u6570', fontsize=17)
    ax.set_ylim(-0.05, 1.08)
    ax.set_yticks(np.arange(0, 1.1, 0.2))
    ax.tick_params(axis='y', labelsize=11)

    ax.grid(True, linestyle='--', alpha=0.5, linewidth=0.5)

    ax.set_title(f'\u7a97\u53e3\u5927\u5c0f = {ws}', fontsize=18, fontweight='normal', pad=15)

    ax.legend(loc='lower left', bbox_to_anchor=(0.22, 0.0), fontsize=12,
              framealpha=0.9, edgecolor='gray')

plt.tight_layout()
plt.savefig('files/short_paper/img/threshold_sensitivity.pdf', dpi=300, bbox_inches='tight',
           transparent=False, facecolor='white')
plt.savefig('files/short_paper/img/threshold_sensitivity.png', dpi=300, bbox_inches='tight',
           transparent=False, facecolor='white')
print('Done! PDF with editable text generated.')
