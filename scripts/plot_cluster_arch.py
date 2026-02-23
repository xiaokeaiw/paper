"""
Two architecture diagrams for thesis Ch2:
(1) Hadoop ecosystem architecture (layered view)
(2) YARN cluster architecture (component view with task flow)

Dual-font strategy:
- DejaVu Sans for pure-English text (matplotlib default)
- Droid Sans Fallback for pure-Chinese text
- Mixed EN+CN strings are avoided; use two separate text calls instead
"""

import re
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import matplotlib.font_manager as fm
import os

_cjk_path = '/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf'
_cjk_prop = fm.FontProperties(fname=_cjk_path)

plt.rcParams.update({
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'font.family': 'sans-serif',
    'font.sans-serif': ['DejaVu Sans'],
    'axes.unicode_minus': False,
})

OUT = 'files/Img/'
os.makedirs(OUT, exist_ok=True)

C_TEXT = '#333333'
C_WHITE = '#FFFFFF'
C_BORDER = '#404040'

_CJK_RE = re.compile(r'[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef\u2460-\u24ff]')


def _has_cjk(text):
    return bool(_CJK_RE.search(text))


def _txt(ax, x, y, text, fontsize=12, color=C_WHITE, weight='normal', **kw):
    """Draw text, auto-selecting font. ONLY pass pure-EN or pure-CN strings."""
    if _has_cjk(text):
        ax.text(x, y, text, fontsize=fontsize, color=color,
                fontproperties=_cjk_prop,
                ha='center', va='center', zorder=10, **kw)
    else:
        ax.text(x, y, text, fontsize=fontsize, color=color,
                fontweight=weight,
                ha='center', va='center', zorder=10, **kw)


def draw_box_2line(ax, x, y, w, h, color, label_en, label_cn,
                   fontsize=13, alpha=0.88, lc=C_WHITE):
    """Draw a rounded box with EN label on top and CN sublabel below."""
    box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.08",
                         facecolor=color, edgecolor=C_BORDER,
                         linewidth=1.2, alpha=alpha, zorder=2)
    ax.add_patch(box)
    _txt(ax, x+w/2, y+h/2+0.15, label_en, fontsize, lc)
    _txt(ax, x+w/2, y+h/2-0.22, label_cn, fontsize-3, lc)


def draw_box_1line(ax, x, y, w, h, color, label, fontsize=13,
                   alpha=0.88, lc=C_WHITE):
    """Draw a rounded box with a single-line label (pure EN or pure CN)."""
    box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.08",
                         facecolor=color, edgecolor=C_BORDER,
                         linewidth=1.2, alpha=alpha, zorder=2)
    ax.add_patch(box)
    _txt(ax, x+w/2, y+h/2, label, fontsize, lc)


def draw_bg_box(ax, x, y, w, h, color):
    """Draw a light background box (no label - labels added separately)."""
    box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.1",
                         facecolor=color, edgecolor='#CCCCCC',
                         linewidth=1.0, alpha=0.5, zorder=1)
    ax.add_patch(box)


def draw_arrow(ax, x1, y1, x2, y2, color='#666666', lw=1.5, label=None,
               label_offset=(0, 0.15), curved=False):
    cs = 'arc3,rad=0.2' if curved else 'arc3,rad=0'
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle='->', color=color, lw=lw,
                               connectionstyle=cs), zorder=5)
    if label:
        mx = (x1+x2)/2 + label_offset[0]
        my = (y1+y2)/2 + label_offset[1]
        _txt(ax, mx, my, label, 8.5, color,
             bbox=dict(boxstyle='round,pad=0.15', facecolor='white',
                      edgecolor='none', alpha=0.85))


# ============================================================
# (1) Hadoop Ecosystem Architecture
# ============================================================
def plot_hadoop():
    fig, ax = plt.subplots(figsize=(12, 7.5))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 8)
    ax.axis('off')

    C_APP = '#5B9BD5'
    C_COMPUTE = '#4472C4'
    C_RESOURCE = '#ED7D31'
    C_STORAGE = '#70AD47'
    C_INFRA = '#A5A5A5'

    y_infra, y_storage, y_resource, y_compute, y_app = 0.5, 1.8, 3.3, 4.8, 6.3
    h = 1.1

    # === Application layer ===
    draw_box_2line(ax, 0.8, y_app, 2.4, h, C_APP, 'Hive', '数据仓库')
    draw_box_2line(ax, 3.5, y_app, 2.4, h, C_APP, 'HBase', '分布式数据库')
    draw_box_2line(ax, 6.2, y_app, 2.4, h, C_APP, 'Spark SQL', '交互式查询')
    draw_box_2line(ax, 8.9, y_app, 2.4, h, C_APP, 'Flink', '流式计算')
    _txt(ax, -0.05, y_app+h/2, '应用层', 10.5, '#888888')

    # === Computing layer ===
    draw_box_2line(ax, 0.8, y_compute, 3.4, h, C_COMPUTE, 'MapReduce', '批处理框架')
    draw_box_2line(ax, 4.5, y_compute, 3.1, h, C_COMPUTE, 'Spark', '内存计算框架')
    draw_box_2line(ax, 7.9, y_compute, 3.4, h, C_COMPUTE, 'Tez', '有向无环图框架')
    _txt(ax, -0.05, y_compute+h/2, '计算层', 10.5, '#888888')

    # === Resource layer (YARN) ===
    box = FancyBboxPatch((0.8, y_resource), 10.5, h, boxstyle="round,pad=0.08",
                         facecolor=C_RESOURCE, edgecolor=C_BORDER,
                         linewidth=1.2, alpha=0.88, zorder=2)
    ax.add_patch(box)
    _txt(ax, 6.05, y_resource+h/2+0.15,
         'YARN (Yet Another Resource Negotiator)', 14, C_WHITE)
    _txt(ax, 6.05, y_resource+h/2-0.22, '统一资源管理与调度', 11, C_WHITE)
    _txt(ax, -0.05, y_resource+h/2, '资源层', 10.5, '#888888')

    # === Storage layer (HDFS) ===
    box = FancyBboxPatch((0.8, y_storage), 10.5, h, boxstyle="round,pad=0.08",
                         facecolor=C_STORAGE, edgecolor=C_BORDER,
                         linewidth=1.2, alpha=0.88, zorder=2)
    ax.add_patch(box)
    _txt(ax, 6.05, y_storage+h/2+0.15,
         'HDFS (Hadoop Distributed File System)', 14, C_WHITE)
    _txt(ax, 6.05, y_storage+h/2-0.22, '分布式文件存储系统', 11, C_WHITE)
    _txt(ax, -0.05, y_storage+h/2, '存储层', 10.5, '#888888')

    # === Infrastructure layer ===
    for i in range(5):
        x = 0.8 + i * 2.25
        box = FancyBboxPatch((x, y_infra), 1.8, h, boxstyle="round,pad=0.08",
                             facecolor=C_INFRA, edgecolor=C_BORDER,
                             linewidth=1.2, alpha=0.88, zorder=2)
        ax.add_patch(box)
        # Node number is pure EN, description is pure CN
        _txt(ax, x+0.9, y_infra+h/2+0.15, 'Node %d' % (i+1), 11, C_WHITE)
        _txt(ax, x+0.9, y_infra+h/2-0.22, '物理服务器', 8, C_WHITE)
    _txt(ax, -0.05, y_infra+h/2, '硬件层', 10.5, '#888888')

    # Arrows between layers
    for yf, yt in [(y_infra+h, y_storage), (y_storage+h, y_resource),
                    (y_resource+h, y_compute), (y_compute+h, y_app)]:
        for xp in [3.0, 6.0, 9.0]:
            ax.annotate('', xy=(xp, yt+0.05), xytext=(xp, yf-0.05),
                       arrowprops=dict(arrowstyle='->', color='#CCCCCC', lw=0.7))

    # Title: split EN and CN for correct fonts
    _txt(ax, 5.0, 7.85, 'Hadoop', 16, C_TEXT, weight='bold')
    _txt(ax, 7.1, 7.85, '生态系统架构', 16, C_TEXT)

    plt.tight_layout(pad=0.3)
    plt.savefig(OUT + 'hadoop_arch.png', bbox_inches='tight', facecolor='white')
    plt.savefig(OUT + 'hadoop_arch.pdf', bbox_inches='tight', facecolor='white')
    plt.close()
    print('[OK] Hadoop architecture')


# ============================================================
# (2) YARN Cluster Architecture
# ============================================================
def plot_yarn():
    fig, ax = plt.subplots(figsize=(13, 8.5))
    ax.set_xlim(0, 13)
    ax.set_ylim(0, 9)
    ax.axis('off')

    C_RM = '#C00000'
    C_NM = '#4472C4'
    C_CONT = '#5B9BD5'
    C_AM = '#70AD47'
    C_CLI = '#7030A0'

    # === Client ===
    draw_box_2line(ax, 0.5, 7.0, 2.2, 1.0, C_CLI, 'Client', '客户端')

    # === ResourceManager ===
    draw_bg_box(ax, 3.8, 6.3, 5.4, 2.2, '#FFF2F0')
    _txt(ax, 6.5, 8.28, 'ResourceManager', 10, '#555555', weight='bold')
    _txt(ax, 6.5, 8.02, '资源管理器', 9, '#555555')

    draw_box_2line(ax, 4.1, 6.6, 2.3, 1.0, C_RM, 'Scheduler', '调度器')
    draw_box_2line(ax, 6.6, 6.6, 2.3, 1.0, C_RM, 'Apps Manager', '应用管理器', fontsize=11)

    # === NodeManager 1 ===
    nm1x, nm1y = 0.3, 0.5
    draw_bg_box(ax, nm1x, nm1y, 3.8, 4.8, '#F2F7FC')
    _txt(ax, nm1x+1.9, nm1y+4.8-0.15, 'NodeManager 1', 9.5, '#555555', weight='bold')
    _txt(ax, nm1x+1.9, nm1y+4.8-0.40, '节点管理器', 8.5, '#555555')

    draw_box_1line(ax, nm1x+0.3, nm1y+3.2, 3.2, 0.8, C_NM, 'NodeManager', 11)
    draw_box_2line(ax, nm1x+0.3, nm1y+1.7, 1.4, 1.1, C_AM, 'AM', '应用主节点', fontsize=11)
    draw_box_2line(ax, nm1x+1.9, nm1y+1.7, 1.6, 1.1, C_CONT, 'Container', '计算容器', fontsize=10)
    # Resources bar
    box = FancyBboxPatch((nm1x+0.3, nm1y+0.3), 3.2, 0.9, boxstyle="round,pad=0.08",
                         facecolor='#A5A5A5', edgecolor=C_BORDER,
                         linewidth=1.2, alpha=0.88, zorder=2)
    ax.add_patch(box)
    _txt(ax, nm1x+1.9, nm1y+0.75, '本地资源', 10, C_WHITE)

    # === NodeManager 2 ===
    nm2x, nm2y = 4.6, 0.5
    draw_bg_box(ax, nm2x, nm2y, 3.8, 4.8, '#F2F7FC')
    _txt(ax, nm2x+1.9, nm2y+4.8-0.15, 'NodeManager 2', 9.5, '#555555', weight='bold')
    _txt(ax, nm2x+1.9, nm2y+4.8-0.40, '节点管理器', 8.5, '#555555')

    draw_box_1line(ax, nm2x+0.3, nm2y+3.2, 3.2, 0.8, C_NM, 'NodeManager', 11)
    draw_box_2line(ax, nm2x+0.3, nm2y+1.7, 1.4, 1.1, C_CONT, 'Container', '计算容器', fontsize=10)
    draw_box_2line(ax, nm2x+1.9, nm2y+1.7, 1.6, 1.1, C_CONT, 'Container', '计算容器', fontsize=10)
    box = FancyBboxPatch((nm2x+0.3, nm2y+0.3), 3.2, 0.9, boxstyle="round,pad=0.08",
                         facecolor='#A5A5A5', edgecolor=C_BORDER,
                         linewidth=1.2, alpha=0.88, zorder=2)
    ax.add_patch(box)
    _txt(ax, nm2x+1.9, nm2y+0.75, '本地资源', 10, C_WHITE)

    # === NodeManager 3 ===
    nm3x, nm3y = 8.9, 0.5
    draw_bg_box(ax, nm3x, nm3y, 3.8, 4.8, '#F2F7FC')
    _txt(ax, nm3x+1.9, nm3y+4.8-0.15, 'NodeManager 3', 9.5, '#555555', weight='bold')
    _txt(ax, nm3x+1.9, nm3y+4.8-0.40, '节点管理器', 8.5, '#555555')

    draw_box_1line(ax, nm3x+0.3, nm3y+3.2, 3.2, 0.8, C_NM, 'NodeManager', 11)
    draw_box_2line(ax, nm3x+0.3, nm3y+1.7, 1.4, 1.1, C_CONT, 'Container', '计算容器', fontsize=10)
    draw_box_2line(ax, nm3x+1.9, nm3y+1.7, 1.6, 1.1, C_CONT, 'Container', '计算容器', fontsize=10)
    box = FancyBboxPatch((nm3x+0.3, nm3y+0.3), 3.2, 0.9, boxstyle="round,pad=0.08",
                         facecolor='#A5A5A5', edgecolor=C_BORDER,
                         linewidth=1.2, alpha=0.88, zorder=2)
    ax.add_patch(box)
    _txt(ax, nm3x+1.9, nm3y+0.75, '本地资源', 10, C_WHITE)

    # === Arrows with numbered steps ===
    draw_arrow(ax, 2.7, 7.5, 3.85, 7.5, C_CLI, 2.0,
               '提交应用', (0, 0.25))
    draw_arrow(ax, 5.2, 6.6, 2.2, 5.3, C_RM, 1.8,
               '分配主节点', (-0.3, 0.2))
    draw_arrow(ax, 1.5, 5.3, 4.5, 6.6, C_AM, 1.5,
               '申请资源', (0.3, 0.2), curved=True)
    draw_arrow(ax, 6.5, 6.6, 6.5, 5.3, C_RM, 1.8,
               '分配容器', (0.6, 0))
    draw_arrow(ax, 7.8, 6.6, 10.0, 5.3, C_RM, 1.8,
               '分配容器', (0.3, 0.2))

    # Step numbers (pure EN, placed near arrow labels)
    _txt(ax, 2.85, 7.95, '1', 9, C_CLI, weight='bold')
    _txt(ax, 3.0, 6.25, '2', 9, C_RM, weight='bold')
    _txt(ax, 2.5, 6.40, '3', 9, C_AM, weight='bold')
    _txt(ax, 7.35, 6.05, '4', 9, C_RM, weight='bold')
    _txt(ax, 9.65, 6.25, '4', 9, C_RM, weight='bold')

    # Heartbeat (dashed)
    for cx in [2.2, 6.5, 10.8]:
        ax.annotate('', xy=(cx, 6.35), xytext=(cx, 5.35),
                    arrowprops=dict(arrowstyle='->', color='#AAAAAA', lw=1.0,
                                   linestyle='dashed'), zorder=2)
    _txt(ax, 11.6, 5.85, '心跳汇报', 8, '#999999')

    # Title
    _txt(ax, 5.7, 8.8, 'YARN', 16, C_TEXT, weight='bold')
    _txt(ax, 7.3, 8.8, '集群架构', 16, C_TEXT)

    plt.tight_layout(pad=0.3)
    plt.savefig(OUT + 'yarn_arch.png', bbox_inches='tight', facecolor='white')
    plt.savefig(OUT + 'yarn_arch.pdf', bbox_inches='tight', facecolor='white')
    plt.close()
    print('[OK] YARN architecture')


if __name__ == '__main__':
    plot_hadoop()
    plot_yarn()
    print('\nDone!')
