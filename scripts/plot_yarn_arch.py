"""
YARN cluster architecture diagram for thesis Ch2.
Shows ResourceManager, NodeManagers, Containers, task flow.
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

plt.rcParams.update({
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'font.family': 'sans-serif',
    'font.sans-serif': ['Droid Sans Fallback', 'SimHei', 'DejaVu Sans'],
    'axes.unicode_minus': False,
})

OUT = 'files/Img/'
fig, ax = plt.subplots(figsize=(13, 8.5))
ax.set_xlim(0, 13)
ax.set_ylim(0, 9)
ax.axis('off')

# Colors
C_RM = '#C00000'        # ResourceManager - dark red
C_SCHED = '#ED7D31'     # Scheduler - orange
C_NM = '#4472C4'        # NodeManager - blue
C_CONTAINER = '#5B9BD5' # Container - light blue
C_AM = '#70AD47'        # ApplicationMaster - green
C_CLIENT = '#7030A0'    # Client - purple
C_TEXT = '#333333'
C_WHITE = '#FFFFFF'
C_BORDER = '#404040'
C_NODE_BG = '#F2F7FC'   # Node background
C_RM_BG = '#FFF2F0'     # RM background

def draw_box(ax, x, y, w, h, color, label, fontsize=11, sublabel=None,
             edgecolor=None, textcolor=None):
    ec = edgecolor or C_BORDER
    tc = textcolor or C_WHITE
    box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.06",
                         facecolor=color, edgecolor=ec,
                         linewidth=1.2, alpha=0.9, zorder=3)
    ax.add_patch(box)
    if sublabel:
        ax.text(x + w/2, y + h/2 + 0.13, label, ha='center', va='center',
                fontsize=fontsize, fontweight='bold', color=tc, zorder=4)
        ax.text(x + w/2, y + h/2 - 0.15, sublabel, ha='center', va='center',
                fontsize=fontsize - 2.5, color=tc, zorder=4, alpha=0.85)
    else:
        ax.text(x + w/2, y + h/2, label, ha='center', va='center',
                fontsize=fontsize, fontweight='bold', color=tc, zorder=4)

def draw_bg_box(ax, x, y, w, h, color, label=None, fontsize=10):
    box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.1",
                         facecolor=color, edgecolor='#CCCCCC',
                         linewidth=1.0, alpha=0.5, zorder=1)
    ax.add_patch(box)
    if label:
        ax.text(x + w/2, y + h - 0.22, label, ha='center', va='center',
                fontsize=fontsize, fontweight='bold', color='#555555', zorder=2)

def draw_arrow(ax, x1, y1, x2, y2, color='#666666', style='->', lw=1.5, label=None,
               label_offset=(0, 0.15), curved=False):
    if curved:
        cs = 'arc3,rad=0.2'
    else:
        cs = 'arc3,rad=0'
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle=style, color=color, lw=lw,
                               connectionstyle=cs), zorder=5)
    if label:
        mx, my = (x1 + x2) / 2 + label_offset[0], (y1 + y2) / 2 + label_offset[1]
        ax.text(mx, my, label, ha='center', va='center', fontsize=8.5,
                color=color, zorder=5,
                bbox=dict(boxstyle='round,pad=0.15', facecolor='white',
                         edgecolor='none', alpha=0.85))

# ==========================================
# Client (top left)
# ==========================================
draw_box(ax, 0.5, 7.0, 2.2, 1.0, C_CLIENT, '客户端', fontsize=13, sublabel='Client')

# ==========================================
# ResourceManager (top center) with background
# ==========================================
draw_bg_box(ax, 3.8, 6.3, 5.4, 2.2, C_RM_BG, 'ResourceManager (资源管理器)')
draw_box(ax, 4.1, 6.6, 2.3, 1.0, C_RM, '调度器', fontsize=12, sublabel='Scheduler')
draw_box(ax, 6.6, 6.6, 2.3, 1.0, C_RM, '应用管理器', fontsize=11, sublabel='Apps Manager')

# ==========================================
# Node Manager 1 (bottom left)
# ==========================================
nm1_x, nm1_y = 0.3, 0.5
draw_bg_box(ax, nm1_x, nm1_y, 3.8, 4.8, C_NODE_BG, 'NodeManager 1 (节点管理器)')
draw_box(ax, nm1_x + 0.3, nm1_y + 3.2, 3.2, 0.8, C_NM, 'NodeManager', fontsize=11)

# AM container
draw_box(ax, nm1_x + 0.3, nm1_y + 1.7, 1.4, 1.1, C_AM, 'AM', fontsize=11,
         sublabel='应用主节点')
# Regular container
draw_box(ax, nm1_x + 1.9, nm1_y + 1.7, 1.6, 1.1, C_CONTAINER, 'Container', fontsize=10,
         sublabel='计算容器')

# Resources bar
draw_box(ax, nm1_x + 0.3, nm1_y + 0.3, 3.2, 0.9, '#A5A5A5', 'CPU / 内存 / 磁盘',
         fontsize=10, sublabel='本地资源')

# ==========================================
# Node Manager 2 (bottom center)
# ==========================================
nm2_x, nm2_y = 4.6, 0.5
draw_bg_box(ax, nm2_x, nm2_y, 3.8, 4.8, C_NODE_BG, 'NodeManager 2 (节点管理器)')
draw_box(ax, nm2_x + 0.3, nm2_y + 3.2, 3.2, 0.8, C_NM, 'NodeManager', fontsize=11)

# Containers
draw_box(ax, nm2_x + 0.3, nm2_y + 1.7, 1.4, 1.1, C_CONTAINER, 'Container', fontsize=10,
         sublabel='计算容器')
draw_box(ax, nm2_x + 1.9, nm2_y + 1.7, 1.6, 1.1, C_CONTAINER, 'Container', fontsize=10,
         sublabel='计算容器')

# Resources bar
draw_box(ax, nm2_x + 0.3, nm2_y + 0.3, 3.2, 0.9, '#A5A5A5', 'CPU / 内存 / 磁盘',
         fontsize=10, sublabel='本地资源')

# ==========================================
# Node Manager 3 (bottom right)
# ==========================================
nm3_x, nm3_y = 8.9, 0.5
draw_bg_box(ax, nm3_x, nm3_y, 3.8, 4.8, C_NODE_BG, 'NodeManager 3 (节点管理器)')
draw_box(ax, nm3_x + 0.3, nm3_y + 3.2, 3.2, 0.8, C_NM, 'NodeManager', fontsize=11)

# Containers
draw_box(ax, nm3_x + 0.3, nm3_y + 1.7, 1.4, 1.1, C_CONTAINER, 'Container', fontsize=10,
         sublabel='计算容器')
draw_box(ax, nm3_x + 1.9, nm3_y + 1.7, 1.6, 1.1, C_CONTAINER, 'Container', fontsize=10,
         sublabel='计算容器')

# Resources bar
draw_box(ax, nm3_x + 0.3, nm3_y + 0.3, 3.2, 0.9, '#A5A5A5', 'CPU / 内存 / 磁盘',
         fontsize=10, sublabel='本地资源')

# ==========================================
# Arrows - Task submission flow
# ==========================================

# 1. Client -> ResourceManager (submit application)
draw_arrow(ax, 2.7, 7.5, 3.85, 7.5, color=C_CLIENT, lw=2.0,
           label='① 提交应用', label_offset=(0, 0.25))

# 2. ResourceManager -> NodeManager1 AM (allocate AM)
draw_arrow(ax, 5.2, 6.6, 2.2, 5.3, color=C_RM, lw=1.8,
           label='② 分配AM', label_offset=(-0.3, 0.2))

# 3. AM -> ResourceManager (request resources)
draw_arrow(ax, 1.5, 5.3, 4.5, 6.6, color=C_AM, lw=1.5,
           label='③ 申请资源', label_offset=(0.3, 0.2), curved=True)

# 4. ResourceManager -> NodeManager2 (allocate containers)
draw_arrow(ax, 6.5, 6.6, 6.5, 5.3, color=C_RM, lw=1.8,
           label='④ 分配容器', label_offset=(0.6, 0))

# 5. ResourceManager -> NodeManager3 (allocate containers)
draw_arrow(ax, 7.8, 6.6, 10.0, 5.3, color=C_RM, lw=1.8,
           label='④ 分配容器', label_offset=(0.3, 0.2))

# 6. NM heartbeat arrows (dashed, subtle)
for nm_cx in [2.2, 6.5, 10.8]:
    ax.annotate('', xy=(nm_cx, 6.35), xytext=(nm_cx, 5.35),
                arrowprops=dict(arrowstyle='->', color='#AAAAAA', lw=1.0,
                               linestyle='dashed'), zorder=2)

# Heartbeat label
ax.text(11.6, 5.85, '心跳汇报', ha='center', va='center', fontsize=8,
        color='#999999', style='italic', zorder=3)

# Title
ax.text(6.5, 8.8, 'YARN集群架构', ha='center', va='center',
        fontsize=16, fontweight='bold', color=C_TEXT)

plt.tight_layout(pad=0.3)
plt.savefig(OUT + 'yarn_arch.png', bbox_inches='tight', facecolor='white')
plt.savefig(OUT + 'yarn_arch.pdf', bbox_inches='tight', facecolor='white')
plt.close()
print('[OK] YARN architecture diagram')
