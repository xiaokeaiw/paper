"""
Hadoop ecosystem architecture diagram for thesis Ch2.
Shows layered structure of a Hadoop distributed cluster.
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch

plt.rcParams.update({
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'font.family': 'sans-serif',
    'font.sans-serif': ['Droid Sans Fallback', 'SimHei', 'DejaVu Sans'],
    'axes.unicode_minus': False,
})

OUT = 'files/Img/'
fig, ax = plt.subplots(figsize=(12, 7.5))
ax.set_xlim(0, 12)
ax.set_ylim(0, 8)
ax.axis('off')

# Color palette - academic blues/grays
C_APP = '#5B9BD5'      # application layer - medium blue
C_COMPUTE = '#4472C4'  # computing framework - strong blue
C_RESOURCE = '#ED7D31'  # resource management - orange
C_STORAGE = '#70AD47'   # storage layer - green
C_INFRA = '#A5A5A5'     # infrastructure - gray
C_TEXT = '#333333'
C_WHITE = '#FFFFFF'
C_BORDER = '#404040'

def draw_box(ax, x, y, w, h, color, label, fontsize=13, alpha=0.85, sublabel=None):
    box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.08",
                         facecolor=color, edgecolor=C_BORDER,
                         linewidth=1.2, alpha=alpha, zorder=2)
    ax.add_patch(box)
    if sublabel:
        ax.text(x + w/2, y + h/2 + 0.15, label, ha='center', va='center',
                fontsize=fontsize, fontweight='bold', color=C_WHITE, zorder=3)
        ax.text(x + w/2, y + h/2 - 0.2, sublabel, ha='center', va='center',
                fontsize=fontsize - 3, color=C_WHITE, zorder=3, alpha=0.9)
    else:
        ax.text(x + w/2, y + h/2, label, ha='center', va='center',
                fontsize=fontsize, fontweight='bold', color=C_WHITE, zorder=3)

def draw_layer_label(ax, x, y, label, fontsize=11):
    ax.text(x, y, label, ha='center', va='center',
            fontsize=fontsize, color='#666666', style='italic', zorder=3)

# Layer heights (bottom to top)
y_infra = 0.5
y_storage = 1.8
y_resource = 3.3
y_compute = 4.8
y_app = 6.3
h_layer = 1.1

# ========== Layer 5: Application Layer ==========
draw_box(ax, 0.8, y_app, 2.4, h_layer, C_APP, 'Hive', sublabel='数据仓库')
draw_box(ax, 3.5, y_app, 2.4, h_layer, C_APP, 'HBase', sublabel='分布式数据库')
draw_box(ax, 6.2, y_app, 2.4, h_layer, C_APP, 'Spark SQL', sublabel='交互式查询')
draw_box(ax, 8.9, y_app, 2.4, h_layer, C_APP, 'Flink', sublabel='流式计算')
draw_layer_label(ax, -0.1, y_app + h_layer/2, '应用层')

# ========== Layer 4: Computing Framework ==========
draw_box(ax, 0.8, y_compute, 3.4, h_layer, C_COMPUTE, 'MapReduce', sublabel='批处理框架')
draw_box(ax, 4.5, y_compute, 3.1, h_layer, C_COMPUTE, 'Spark', sublabel='内存计算框架')
draw_box(ax, 7.9, y_compute, 3.4, h_layer, C_COMPUTE, 'Tez', sublabel='DAG计算框架')
draw_layer_label(ax, -0.1, y_compute + h_layer/2, '计算层')

# ========== Layer 3: Resource Management ==========
draw_box(ax, 0.8, y_resource, 10.5, h_layer, C_RESOURCE, 'YARN (Yet Another Resource Negotiator)',
         sublabel='统一资源管理与调度', fontsize=14)
draw_layer_label(ax, -0.1, y_resource + h_layer/2, '资源层')

# ========== Layer 2: Storage Layer ==========
draw_box(ax, 0.8, y_storage, 10.5, h_layer, C_STORAGE, 'HDFS (Hadoop Distributed File System)',
         sublabel='分布式文件存储系统', fontsize=14)
draw_layer_label(ax, -0.1, y_storage + h_layer/2, '存储层')

# ========== Layer 1: Infrastructure ==========
# Draw multiple server nodes
node_w = 1.8
node_gap = 0.45
start_x = 0.8
for i in range(5):
    x = start_x + i * (node_w + node_gap)
    draw_box(ax, x, y_infra, node_w, h_layer, C_INFRA, f'节点 {i+1}', fontsize=11,
             sublabel='物理服务器')
# Ellipsis between node 3 and node 4 area
draw_layer_label(ax, -0.1, y_infra + h_layer/2, '硬件层')

# Draw vertical arrows between layers
arrow_props = dict(arrowstyle='->', color='#888888', lw=1.5,
                   connectionstyle='arc3,rad=0')
for y_from, y_to in [(y_infra + h_layer, y_storage),
                      (y_storage + h_layer, y_resource),
                      (y_resource + h_layer, y_compute),
                      (y_compute + h_layer, y_app)]:
    for x_pos in [3.0, 6.0, 9.0]:
        ax.annotate('', xy=(x_pos, y_to + 0.05), xytext=(x_pos, y_from - 0.05),
                   arrowprops=dict(arrowstyle='->', color='#BBBBBB', lw=0.8))

# Title
ax.text(6.0, 7.85, 'Hadoop生态系统架构', ha='center', va='center',
        fontsize=16, fontweight='bold', color=C_TEXT)

plt.tight_layout(pad=0.3)
plt.savefig(OUT + 'hadoop_arch.png', bbox_inches='tight', facecolor='white')
plt.savefig(OUT + 'hadoop_arch.pdf', bbox_inches='tight', facecolor='white')
plt.close()
print('[OK] Hadoop architecture diagram')
