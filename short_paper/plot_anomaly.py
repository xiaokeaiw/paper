import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# ---- 关键：确保输出的 PDF/EPS 中文字可编辑（不转曲线） ----
matplotlib.rcParams['pdf.fonttype'] = 42     # TrueType，文字可编辑
matplotlib.rcParams['ps.fonttype'] = 42      # EPS 同理
matplotlib.rcParams['svg.fonttype'] = 'none' # SVG 保留文字对象

# 字体配置：DejaVu Sans 处理英文/数字，Droid Sans Fallback 处理中文
matplotlib.rcParams['font.family'] = ['DejaVu Sans', 'Droid Sans Fallback']
matplotlib.rcParams['axes.unicode_minus'] = False
matplotlib.rcParams['font.size'] = 11

base = 'resources/data/test_data/测试数据/01'
test = pd.read_csv(f'{base}/test-data.csv')
anom = pd.read_csv(f'{base}/anomaly-data.csv')

anomaly_node = 'hx-0018'
t_start = 1751685000
t_end = 1751698000
mask = (test['Time'] >= t_start) & (test['Time'] <= t_end)
subset = test[mask].copy()
subset['minutes'] = (subset['Time'] - t_start) / 60.0

anom_in_range = anom[(anom['start'] >= t_start - 600) & (anom['end'] <= t_end + 600)]
other_nodes = [c for c in test.columns if c != 'Time' and c != anomaly_node]

fig, ax = plt.subplots(1, 1, figsize=(10, 4.2))

for i, node in enumerate(other_nodes):
    label = '正常节点' if i == 0 else None
    ax.plot(subset['minutes'], subset[node], color='#90A4AE', linewidth=0.5, alpha=0.6, label=label)

ax.plot(subset['minutes'], subset[anomaly_node], color='#D32F2F', linewidth=1.8,
        label='异常节点', zorder=5)

first_shaded = True
for _, row in anom_in_range.iterrows():
    a_start_m = (row['start'] - t_start) / 60.0
    a_end_m = (row['end'] - t_start) / 60.0
    lbl = '异常片段' if first_shaded else None
    ax.axvspan(a_start_m, a_end_m, color='#FFCDD2', alpha=0.6, zorder=0, label=lbl)
    first_shaded = False

ax.set_xlabel('时间（分钟）', fontsize=12)
ax.set_ylabel('RPC Router 连接数', fontsize=12)
ax.legend(loc='upper right', framealpha=0.9, fontsize=10)
ax.set_xlim(subset['minutes'].iloc[0], subset['minutes'].iloc[-1])
ax.grid(True, alpha=0.25, linestyle='--')
ax.tick_params(labelsize=10)

plt.tight_layout()

# 输出多种矢量格式，文字均可编辑
plt.savefig('files/short_paper/img/dataset_anomaly_example.pdf',
            dpi=300, bbox_inches='tight')
plt.savefig('files/short_paper/img/dataset_anomaly_example.eps',
            dpi=300, bbox_inches='tight')
plt.savefig('files/short_paper/img/dataset_anomaly_example.svg',
            dpi=300, bbox_inches='tight')
# PNG 备用
plt.savefig('files/short_paper/img_png/dataset_anomaly_example.png',
            dpi=300, bbox_inches='tight')

print("Saved: PDF / EPS / SVG / PNG")
