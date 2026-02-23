"""
Reproduce the Hadoop distributed cluster diagram from hadoop.html as a vector figure.
Shows: Client, Master Node, Secondary Master, 3 Slave Nodes, HDFS/YARN/Compute layers,
data replication arrows, and legend.
"""

import re
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle
import matplotlib.font_manager as fm
import os

_cjk_path = '/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf'
_cjk_prop = fm.FontProperties(fname=_cjk_path)

plt.rcParams.update({
    'figure.dpi': 300, 'savefig.dpi': 300,
    'font.family': 'sans-serif',
    'font.sans-serif': ['DejaVu Sans'],
    'axes.unicode_minus': False,
})

OUT = 'files/Img/draft/'
os.makedirs(OUT, exist_ok=True)

_CJK = re.compile(r'[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]')

# Colors matching the HTML
C_HDFS = '#e3f2fd'
C_YARN = '#fff3e0'
C_COMPUTE = '#e8f5e9'
C_CLIENT = '#f5f5f5'
C_HDFS_BORDER = '#2196f3'
C_YARN_BORDER = '#ff9800'
C_BORDER = '#333333'
C_TEXT = '#333333'
C_GRAY = '#666666'
C_LGRAY = '#CCCCCC'
C_WHITE = '#FFFFFF'


def txt(ax, x, y, text, fs=10, color=C_TEXT, weight='normal', ha='center', va='center', **kw):
    if _CJK.search(text):
        ax.text(x, y, text, fontsize=fs, color=color, fontproperties=_cjk_prop,
                ha=ha, va=va, zorder=10, **kw)
    else:
        ax.text(x, y, text, fontsize=fs, color=color, fontweight=weight,
                ha=ha, va=va, zorder=10, **kw)


def rbox(ax, x, y, w, h, fc=C_WHITE, ec=C_BORDER, lw=1.2, zorder=3, alpha=1.0, ls='-'):
    b = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.04",
                       facecolor=fc, edgecolor=ec, linewidth=lw,
                       alpha=alpha, zorder=zorder, linestyle=ls)
    ax.add_patch(b)


def component(ax, x, y, w, h, fc, label, fs=9):
    """Small inner component box."""
    rbox(ax, x, y, w, h, fc=fc, ec='#888888', lw=0.8, zorder=5)
    txt(ax, x+w/2, y+h/2, label, fs, C_TEXT)


def arrow(ax, x1, y1, x2, y2, color=C_GRAY, lw=1.2, dash=False, both=False):
    style = '<->' if both else '->'
    ls = (0, (4, 3)) if dash else '-'
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle=style, color=color, lw=lw,
                               linestyle=ls), zorder=4)


def main():
    fig, ax = plt.subplots(figsize=(12, 8.5))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 9)
    ax.axis('off')

    # ── Cluster boundary (dashed) ──
    rbox(ax, 0.5, 0.3, 11.0, 6.8, fc='#FAFAFA', ec=C_LGRAY, lw=1.5,
         zorder=0, alpha=0.3, ls='--')
    txt(ax, 2.2, 7.0, 'Distributed Cluster (Multi-Node)', 9, '#AAAAAA', weight='bold')

    # ── Client ──
    rbox(ax, 4.5, 7.8, 3.0, 0.7, fc=C_CLIENT, ec=C_BORDER, lw=1.2, zorder=3)
    txt(ax, 6.0, 8.15, 'Hadoop Client (CLI / API)', 10, C_TEXT, weight='bold')

    # ── Master Node ──
    rbox(ax, 0.8, 5.2, 3.2, 1.7, fc=C_WHITE, ec=C_BORDER, lw=1.5, zorder=2)
    txt(ax, 2.4, 6.65, 'Master Node', 11, C_TEXT, weight='bold')
    component(ax, 1.1, 5.95, 2.6, 0.5, C_HDFS, 'NameNode (HDFS Master)', 9)
    component(ax, 1.1, 5.35, 2.6, 0.5, C_YARN, 'ResourceManager (YARN)', 9)

    # ── Secondary Master ──
    rbox(ax, 8.0, 5.2, 3.2, 1.7, fc=C_WHITE, ec=C_BORDER, lw=1.2,
         zorder=2, alpha=0.7, ls='--')
    txt(ax, 9.6, 6.65, 'Secondary Master', 10, '#888888', weight='bold')
    component(ax, 8.3, 5.95, 2.6, 0.5, C_HDFS, 'Secondary NameNode', 9)
    txt(ax, 9.6, 5.55, '(Checkpoints)', 8.5, '#999999')

    # ── Slave Nodes ──
    slave_xs = [0.5, 4.2, 7.9]
    slave_labels = ['Slave Node 1', 'Slave Node 2', 'Slave Node N']
    sw, sh = 3.0, 3.8

    for i, (sx, label) in enumerate(zip(slave_xs, slave_labels)):
        rbox(ax, sx, 0.5, sw, sh, fc=C_WHITE, ec=C_BORDER, lw=1.2, zorder=2)
        txt(ax, sx+sw/2, 4.05, label, 10, C_TEXT, weight='bold')

        cw = 2.5  # component width
        cx = sx + (sw - cw) / 2

        component(ax, cx, 3.3, cw, 0.5, C_HDFS, 'DataNode', 9)
        component(ax, cx, 2.6, cw, 0.5, C_YARN, 'NodeManager', 9)

        # Separator line
        ax.plot([sx+0.3, sx+sw-0.3], [2.35, 2.35], color='#BBBBBB', lw=0.8, zorder=5)
        txt(ax, sx+sw/2, 2.15, 'Task Execution', 8, '#888888')

        component(ax, cx, 1.35, cw, 0.5, C_COMPUTE, 'MapTask / ReduceTask', 8.5)

        # Disk/resources
        component(ax, cx, 0.65, cw, 0.5, '#f0f0f0', '本地磁盘', 8)

        # Ellipsis between node 2 and N
        if i == 1:
            txt(ax, sx+sw+0.45, 2.5, '...', 20, '#AAAAAA')

    # ── Arrows: Client to Masters ──
    arrow(ax, 5.5, 7.8, 2.8, 6.95, C_GRAY, 1.2, dash=True)
    arrow(ax, 6.5, 7.8, 9.2, 6.95, C_GRAY, 1.2, dash=True)

    # ── Arrows: Master to Slaves (HDFS metadata - blue) ──
    for sx in slave_xs:
        arrow(ax, 2.1, 5.2, sx+1.5, 3.85, C_HDFS_BORDER, 1.0)

    # ── Arrows: Master to Slaves (YARN commands - orange) ──
    for sx in slave_xs:
        arrow(ax, 2.7, 5.2, sx+1.8, 3.85, C_YARN_BORDER, 1.0)

    # ── Data Replication arrows between DataNodes ──
    arrow(ax, 3.5, 3.55, 4.2, 3.55, '#999999', 0.8, dash=True, both=True)
    arrow(ax, 7.2, 3.55, 7.9, 3.55, '#999999', 0.8, dash=True, both=True)
    txt(ax, 3.85, 3.78, 'Replica', 7, '#999999')
    txt(ax, 7.55, 3.78, 'Replica', 7, '#999999')

    # ── Legend ──
    lx, ly = 9.5, 4.55
    rbox(ax, lx, ly, 2.4, 1.6, fc='#FFFFFFEE', ec='#DDDDDD', lw=0.8, zorder=8)
    # HDFS
    rbox(ax, lx+0.15, ly+1.15, 0.3, 0.22, fc=C_HDFS, ec='#888888', lw=0.6, zorder=9)
    txt(ax, lx+0.65, ly+1.26, 'HDFS', 8, C_TEXT, ha='left')
    txt(ax, lx+1.35, ly+1.26, '存储层', 8, C_TEXT, ha='left')
    # YARN
    rbox(ax, lx+0.15, ly+0.75, 0.3, 0.22, fc=C_YARN, ec='#888888', lw=0.6, zorder=9)
    txt(ax, lx+0.65, ly+0.86, 'YARN', 8, C_TEXT, ha='left')
    txt(ax, lx+1.35, ly+0.86, '资源层', 8, C_TEXT, ha='left')
    # Compute
    rbox(ax, lx+0.15, ly+0.35, 0.3, 0.22, fc=C_COMPUTE, ec='#888888', lw=0.6, zorder=9)
    txt(ax, lx+0.65, ly+0.46, 'Compute', 8, C_TEXT, ha='left')
    txt(ax, lx+1.4, ly+0.46, '计算层', 8, C_TEXT, ha='left')

    # ── Title ──
    txt(ax, 6.0, 8.75, 'Hadoop', 14, C_TEXT, weight='bold')
    txt(ax, 8.0, 8.75, '分布式集群架构', 14, C_TEXT)

    plt.tight_layout(pad=0.3)
    plt.savefig(OUT + 'hadoop_html.png', bbox_inches='tight', facecolor='white')
    plt.savefig(OUT + 'hadoop_html.pdf', bbox_inches='tight', facecolor='white')
    plt.close()
    print('[OK] Hadoop HTML-style cluster diagram')


if __name__ == '__main__':
    main()
