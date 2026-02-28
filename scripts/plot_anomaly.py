import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties

cjk = FontProperties(fname='/tmp/NotoSansSC.ttf', size=9)

base = 'resources/data/test_data/\u6d4b\u8bd5\u6570\u636e/01'
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
    label = '\u6b63\u5e38\u8282\u70b9' if i == 0 else None
    ax.plot(subset['minutes'], subset[node], color='#90A4AE', linewidth=0.5, alpha=0.6, label=label)

ax.plot(subset['minutes'], subset[anomaly_node], color='#D32F2F', linewidth=1.8,
        label='\u5f02\u5e38\u8282\u70b9', zorder=5)

first_shaded = True
for _, row in anom_in_range.iterrows():
    a_start_m = (row['start'] - t_start) / 60.0
    a_end_m = (row['end'] - t_start) / 60.0
    lbl = '\u5f02\u5e38\u7247\u6bb5' if first_shaded else None
    ax.axvspan(a_start_m, a_end_m, color='#FFCDD2', alpha=0.6, zorder=0, label=lbl)
    first_shaded = False

ax.set_xlabel('时间（分钟）', fontsize=11, fontproperties=cjk)
ax.set_ylabel('RPC Router 连接数', fontsize=11, fontproperties=cjk)
ax.legend(loc='upper right', framealpha=0.9, prop=cjk)
ax.set_xlim(subset['minutes'].iloc[0], subset['minutes'].iloc[-1])
ax.grid(True, alpha=0.25, linestyle='--')
ax.tick_params(labelsize=9)

plt.tight_layout()
plt.savefig('files/Img/draft/dataset_anomaly_example.pdf', dpi=300, bbox_inches='tight')
plt.savefig('files/Img/draft/dataset_anomaly_example.png', dpi=200, bbox_inches='tight')
print("Saved OK")
