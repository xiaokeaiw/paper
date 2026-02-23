"""
Generate all figures for Ch2 and Ch3:
  1. Hadoop distributed cluster architecture (Ch2) - focus on distributed nature
  2. YARN architecture with RPC Router + monitoring metrics (Ch3)
  3. Data annotation workflow (Ch3)
  4. Autoencoder algorithm diagram (Ch3)
  5. Threshold (I-SPOT) and F1 score line chart (Ch3 s3.3)
  6. CSAD-AT overall framework architecture (Ch3 s3.4)

All output to files/Img/draft/
"""

import re
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Arc
import matplotlib.patches as mpatches
import matplotlib.font_manager as fm
import os

# ── Font setup ──────────────────────────────────────────────
_cjk_path = '/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf'
_cjk_prop = fm.FontProperties(fname=_cjk_path)

plt.rcParams.update({
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'font.family': 'sans-serif',
    'font.sans-serif': ['DejaVu Sans'],
    'axes.unicode_minus': False,
})

OUT = 'files/Img/draft/'
os.makedirs(OUT, exist_ok=True)

_CJK_RE = re.compile(r'[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef\u2460-\u24ff]')

# ── Academic color palette ──────────────────────────────────
# Muted, professional palette inspired by Nature/Science figures
PAL = {
    'blue':    '#4472C4',
    'lblue':   '#5B9BD5',
    'dblue':   '#2B5797',
    'orange':  '#ED7D31',
    'green':   '#70AD47',
    'dgreen':  '#548235',
    'red':     '#C00000',
    'purple':  '#7030A0',
    'gray':    '#A5A5A5',
    'lgray':   '#D9D9D9',
    'dgray':   '#404040',
    'text':    '#333333',
    'white':   '#FFFFFF',
    'bg1':     '#F2F7FC',
    'bg2':     '#FFF8F0',
    'bg3':     '#F5FFF5',
    'bg4':     '#FFF2F0',
}


def _txt(ax, x, y, text, fontsize=11, color=PAL['white'], weight='normal', **kw):
    if _CJK_RE.search(text):
        ax.text(x, y, text, fontsize=fontsize, color=color,
                fontproperties=_cjk_prop,
                ha='center', va='center', zorder=10, **kw)
    else:
        ax.text(x, y, text, fontsize=fontsize, color=color,
                fontweight=weight, ha='center', va='center', zorder=10, **kw)


def _box(ax, x, y, w, h, color, zorder=3, alpha=0.92, ec=PAL['dgray'], lw=1.2):
    b = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.06",
                       facecolor=color, edgecolor=ec,
                       linewidth=lw, alpha=alpha, zorder=zorder)
    ax.add_patch(b)
    return b


def _bg(ax, x, y, w, h, color, ec='#CCCCCC', alpha=0.45, zorder=1):
    b = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.1",
                       facecolor=color, edgecolor=ec,
                       linewidth=1.0, alpha=alpha, zorder=zorder)
    ax.add_patch(b)
    return b


def _arrow(ax, x1, y1, x2, y2, color='#666666', lw=1.5, style='->', cs=None):
    if cs is None:
        cs = 'arc3,rad=0'
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle=style, color=color, lw=lw,
                               connectionstyle=cs), zorder=5)


def _arr_label(ax, x, y, text, fontsize=8, color=PAL['text']):
    _txt(ax, x, y, text, fontsize, color,
         bbox=dict(boxstyle='round,pad=0.12', facecolor='white',
                   edgecolor='none', alpha=0.88))


# ================================================================
# FIGURE 1: Hadoop Distributed Cluster Architecture (Ch2)
# Focus: show multiple nodes, master/slave, data replication
# ================================================================
def fig1_hadoop_cluster():
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 7.5)
    ax.axis('off')

    # --- Master node area ---
    _bg(ax, 0.3, 4.8, 11.4, 2.4, PAL['bg4'], alpha=0.35)
    _txt(ax, 6.0, 6.95, 'Master', 11, PAL['text'], weight='bold')
    _txt(ax, 6.0, 6.68, '主节点', 9.5, '#777777')

    # NameNode
    _box(ax, 0.8, 5.0, 3.0, 1.4, PAL['dblue'])
    _txt(ax, 2.3, 5.85, 'NameNode', 12, PAL['white'], weight='bold')
    _txt(ax, 2.3, 5.45, '元数据管理', 9, '#D0D8E8')

    # ResourceManager
    _box(ax, 4.5, 5.0, 3.0, 1.4, PAL['red'])
    _txt(ax, 6.0, 5.85, 'ResourceManager', 11, PAL['white'], weight='bold')
    _txt(ax, 6.0, 5.45, '资源调度', 9, '#F0C8C8')

    # Secondary NameNode
    _box(ax, 8.2, 5.0, 3.0, 1.4, PAL['blue'])
    _txt(ax, 9.7, 5.85, 'Secondary NN', 11, PAL['white'], weight='bold')
    _txt(ax, 9.7, 5.45, '元数据备份', 9, '#D0D8E8')

    # --- Slave nodes area ---
    _bg(ax, 0.3, 0.3, 11.4, 4.0, PAL['bg1'], alpha=0.35)
    _txt(ax, 6.0, 4.05, 'Slave', 11, PAL['text'], weight='bold')
    _txt(ax, 6.0, 3.78, '工作节点集群', 9.5, '#777777')

    # Draw 4 slave nodes
    slave_labels = [
        ('DataNode 1', 'NodeManager 1'),
        ('DataNode 2', 'NodeManager 2'),
        ('DataNode 3', 'NodeManager 3'),
        ('DataNode N', 'NodeManager N'),
    ]
    for i, (dn, nm) in enumerate(slave_labels):
        sx = 0.7 + i * 2.8
        # Node background
        _bg(ax, sx, 0.5, 2.5, 3.0, '#FFFFFF', ec='#BBBBBB', alpha=0.7, zorder=2)

        # DataNode box
        _box(ax, sx+0.15, 2.3, 2.2, 0.85, PAL['green'])
        _txt(ax, sx+1.25, 2.72, dn, 9.5, PAL['white'], weight='bold')

        # NodeManager box
        _box(ax, sx+0.15, 1.2, 2.2, 0.85, PAL['blue'])
        _txt(ax, sx+1.25, 1.62, nm, 9.5, PAL['white'], weight='bold')

        # Disk icon (simplified)
        _box(ax, sx+0.15, 0.6, 2.2, 0.45, PAL['lgray'], ec='#BBBBBB')
        _txt(ax, sx+1.25, 0.82, '本地磁盘', 8, PAL['dgray'])

        # Ellipsis between node 3 and N
        if i == 2:
            _txt(ax, sx+2.65, 1.8, '...', 18, PAL['gray'])

    # Arrows: Master to Slaves
    for i in range(4):
        sx = 0.7 + i * 2.8 + 1.25
        # NameNode -> DataNode
        _arrow(ax, 2.3, 5.0, sx, 3.18, PAL['dblue'], 1.0, cs='arc3,rad=0')
        # ResourceManager -> NodeManager
        _arrow(ax, 6.0, 5.0, sx, 2.08, PAL['red'], 1.0, cs='arc3,rad=0')

    # Data replication arrows between DataNodes (horizontal)
    for i in range(2):
        sx1 = 0.7 + i * 2.8 + 2.35+0.15
        sx2 = 0.7 + (i+1) * 2.8 + 0.15
        _arrow(ax, sx1, 2.72, sx2, 2.72, PAL['dgreen'], 1.0, style='<->')
    _arr_label(ax, 4.7, 2.95, '数据副本', 7.5, PAL['dgreen'])

    # Heartbeat labels
    _arr_label(ax, 1.2, 4.55, '心跳', 7.5, '#999999')

    # Network
    _txt(ax, 11.0, 4.55, '网络通信', 8, '#999999')

    # Title
    _txt(ax, 6.0, 7.35, 'Hadoop', 15, PAL['text'], weight='bold')
    _txt(ax, 8.15, 7.35, '分布式集群架构', 15, PAL['text'])

    plt.tight_layout(pad=0.3)
    plt.savefig(OUT + 'hadoop_cluster.png', bbox_inches='tight', facecolor='white')
    plt.savefig(OUT + 'hadoop_cluster.pdf', bbox_inches='tight', facecolor='white')
    plt.close()
    print('[OK] Fig1: Hadoop distributed cluster')


# ================================================================
# FIGURE 2: YARN Architecture with RPC Router & Metrics (Ch3)
# ================================================================
def fig2_yarn_rpc():
    fig, ax = plt.subplots(figsize=(13, 8.5))
    ax.set_xlim(0, 13)
    ax.set_ylim(0, 9)
    ax.axis('off')

    # --- Client ---
    _box(ax, 0.3, 7.2, 2.0, 0.9, PAL['purple'])
    _txt(ax, 1.3, 7.78, 'Client', 11, PAL['white'], weight='bold')
    _txt(ax, 1.3, 7.48, '客户端', 9, '#D8C0E8')

    # --- RPC Router ---
    _bg(ax, 2.8, 7.0, 2.6, 1.3, '#FFF8E8', alpha=0.6)
    _box(ax, 3.0, 7.15, 2.2, 0.9, PAL['orange'])
    _txt(ax, 4.1, 7.72, 'RPC Router', 11, PAL['white'], weight='bold')
    _txt(ax, 4.1, 7.42, '路由转发', 9, '#FDE8D0')

    # --- ResourceManager ---
    _bg(ax, 6.0, 6.3, 5.2, 2.2, PAL['bg4'], alpha=0.4)
    _txt(ax, 8.6, 8.28, 'ResourceManager', 10, '#555555', weight='bold')
    _txt(ax, 8.6, 8.02, '资源管理器', 8.5, '#777777')

    _box(ax, 6.3, 6.6, 2.2, 1.0, PAL['red'])
    _txt(ax, 7.4, 7.22, 'Scheduler', 11, PAL['white'], weight='bold')
    _txt(ax, 7.4, 6.92, '调度器', 9, '#F0C8C8')

    _box(ax, 8.8, 6.6, 2.2, 1.0, PAL['red'])
    _txt(ax, 9.9, 7.22, 'Apps Manager', 10, PAL['white'], weight='bold')
    _txt(ax, 9.9, 6.92, '应用管理器', 9, '#F0C8C8')

    # --- Monitoring / Metrics collection area ---
    _bg(ax, 9.5, 3.8, 3.2, 2.2, '#FFF8E8', alpha=0.5)
    _txt(ax, 11.1, 5.78, '监控指标采集', 9, '#777777')
    # Metric items
    metrics = ['CPU', '内存', '网络', '磁盘']
    met_colors = [PAL['blue'], PAL['green'], PAL['orange'], PAL['gray']]
    for i, (m, mc) in enumerate(zip(metrics, met_colors)):
        my = 5.15 - i * 0.35
        _box(ax, 9.8, my-0.12, 1.2, 0.28, mc, alpha=0.85, lw=0.8, ec='#AAAAAA')
        _txt(ax, 10.4, my+0.02, m, 8, PAL['white'])
    # Arrow from metrics to RPC Router
    _txt(ax, 11.6, 4.6, 'RPC', 8, PAL['orange'], weight='bold')
    _arrow(ax, 11.1, 5.78, 4.3, 7.15, PAL['orange'], 1.2, cs='arc3,rad=-0.3')

    # --- 3 NodeManagers ---
    nm_xs = [0.2, 3.5, 6.8]
    for idx, nmx in enumerate(nm_xs):
        nmy = 0.3
        _bg(ax, nmx, nmy, 2.9, 3.2, PAL['bg1'], alpha=0.4)
        _txt(ax, nmx+1.45, nmy+3.2-0.15, 'NodeManager %d' % (idx+1), 9, '#555555', weight='bold')
        _txt(ax, nmx+1.45, nmy+3.2-0.38, '节点管理器', 8, '#777777')

        _box(ax, nmx+0.2, nmy+2.0, 2.5, 0.65, PAL['blue'])
        _txt(ax, nmx+1.45, nmy+2.32, 'NodeManager', 9.5, PAL['white'], weight='bold')

        if idx == 0:
            # AM container
            _box(ax, nmx+0.2, nmy+1.0, 1.1, 0.75, PAL['green'])
            _txt(ax, nmx+0.75, nmy+1.5, 'AM', 9, PAL['white'], weight='bold')
            _txt(ax, nmx+0.75, nmy+1.22, '应用主节点', 6.5, '#C8E8C8')
            # Container
            _box(ax, nmx+1.5, nmy+1.0, 1.2, 0.75, PAL['lblue'])
            _txt(ax, nmx+2.1, nmy+1.5, 'Container', 8, PAL['white'], weight='bold')
            _txt(ax, nmx+2.1, nmy+1.22, '计算容器', 6.5, '#D0E8F0')
        else:
            _box(ax, nmx+0.2, nmy+1.0, 1.1, 0.75, PAL['lblue'])
            _txt(ax, nmx+0.75, nmy+1.5, 'Container', 7.5, PAL['white'], weight='bold')
            _txt(ax, nmx+0.75, nmy+1.22, '计算容器', 6.5, '#D0E8F0')
            _box(ax, nmx+1.5, nmy+1.0, 1.2, 0.75, PAL['lblue'])
            _txt(ax, nmx+2.1, nmy+1.5, 'Container', 8, PAL['white'], weight='bold')
            _txt(ax, nmx+2.1, nmy+1.22, '计算容器', 6.5, '#D0E8F0')

        # Resources
        _box(ax, nmx+0.2, nmy+0.15, 2.5, 0.55, PAL['lgray'], ec='#BBBBBB', alpha=0.8)
        _txt(ax, nmx+1.45, nmy+0.42, '本地资源', 8, PAL['dgray'])

    # --- Arrows ---
    # Client -> RPC Router
    _arrow(ax, 2.3, 7.65, 3.0, 7.65, PAL['purple'], 1.8)
    _arr_label(ax, 2.65, 7.9, '提交', 7.5, PAL['purple'])

    # RPC Router -> ResourceManager
    _arrow(ax, 5.2, 7.65, 6.05, 7.65, PAL['orange'], 1.8)
    _arr_label(ax, 5.6, 7.9, '路由', 7.5, PAL['orange'])

    # RM -> NM1 (allocate AM)
    _arrow(ax, 7.4, 6.6, 1.65, 3.55, PAL['red'], 1.5)
    _arr_label(ax, 3.8, 5.35, '分配主节点', 7.5, PAL['red'])

    # AM -> RM (request resources)
    _arrow(ax, 1.65, 3.55, 7.4, 6.6, PAL['green'], 1.2, cs='arc3,rad=0.25')
    _arr_label(ax, 3.2, 5.8, '申请资源', 7.5, PAL['green'])

    # RM -> NM2, NM3
    _arrow(ax, 8.6, 6.6, 4.95, 3.55, PAL['red'], 1.5)
    _arrow(ax, 9.9, 6.6, 8.25, 3.55, PAL['red'], 1.5)
    _arr_label(ax, 7.0, 5.35, '分配容器', 7.5, PAL['red'])

    # Heartbeat (dashed)
    for nmx in nm_xs:
        cx = nmx + 1.45
        ax.annotate('', xy=(cx, 6.3), xytext=(cx, 3.55),
                    arrowprops=dict(arrowstyle='->', color='#BBBBBB', lw=0.8,
                                   linestyle='dashed'), zorder=2)
    _txt(ax, 0.5, 5.0, '心跳', 7.5, '#AAAAAA')

    # Title
    _txt(ax, 5.5, 8.75, 'YARN', 15, PAL['text'], weight='bold')
    _txt(ax, 7.85, 8.75, '集群架构与监控数据采集', 15, PAL['text'])

    plt.tight_layout(pad=0.3)
    plt.savefig(OUT + 'yarn_rpc.png', bbox_inches='tight', facecolor='white')
    plt.savefig(OUT + 'yarn_rpc.pdf', bbox_inches='tight', facecolor='white')
    plt.close()
    print('[OK] Fig2: YARN with RPC Router')


# ================================================================
# FIGURE 3: Data Annotation Workflow (Ch3)
# ================================================================
def fig3_annotation():
    fig, ax = plt.subplots(figsize=(13, 4.5))
    ax.set_xlim(0, 13)
    ax.set_ylim(0, 4.5)
    ax.axis('off')

    # Steps: Raw data -> Sliding window -> Multi-score -> Score merge -> I-SPOT -> Anomaly labels
    steps_en = ['Raw Data', 'Sliding\nWindow', 'Multi-Method\nScoring', 'Score\nMerging', 'I-SPOT\nThreshold', 'Anomaly\nLabels']
    steps_cn = ['原始时序数据', '滑动窗口\n分割', '多方法\n异常评分', '评分\n融合', '自适应\n阈值检测', '异常\n标注结果']
    colors = [PAL['gray'], PAL['blue'], PAL['orange'], PAL['green'], PAL['red'], PAL['purple']]

    bw, bh = 1.65, 2.2
    gap = 0.35
    start_x = 0.35

    for i, (en, cn, c) in enumerate(zip(steps_en, steps_cn, colors)):
        x = start_x + i * (bw + gap)
        _box(ax, x, 1.0, bw, bh, c, alpha=0.90)
        _txt(ax, x+bw/2, 2.45, en, 9.5, PAL['white'], weight='bold')
        _txt(ax, x+bw/2, 1.55, cn, 9, '#E8E8E8')

        # Sub-details
        if i == 2:
            details = ['AE', 'Euclidean', 'Adaptive LOF']
            for j, d in enumerate(details):
                _txt(ax, x+bw/2, 1.15-j*0.22, d, 7, '#D8D8D8')

        # Arrow to next
        if i < len(steps_en) - 1:
            ax_end = start_x + (i+1) * (bw + gap)
            _arrow(ax, x+bw+0.02, 2.1, ax_end-0.02, 2.1, PAL['dgray'], 1.5)

    # Title
    _txt(ax, 6.5, 3.7, '数据标注流程', 14, PAL['text'])

    plt.tight_layout(pad=0.3)
    plt.savefig(OUT + 'annotation_flow.png', bbox_inches='tight', facecolor='white')
    plt.savefig(OUT + 'annotation_flow.pdf', bbox_inches='tight', facecolor='white')
    plt.close()
    print('[OK] Fig3: Data annotation workflow')


# ================================================================
# FIGURE 4: Autoencoder Algorithm Diagram (Ch3)
# ================================================================
def fig4_autoencoder():
    fig, ax = plt.subplots(figsize=(11, 5.5))
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 5.5)
    ax.axis('off')

    # Input layer (60 dim)
    _box(ax, 0.3, 0.6, 1.4, 4.0, PAL['blue'], alpha=0.85)
    _txt(ax, 1.0, 2.9, 'Input', 10, PAL['white'], weight='bold')
    _txt(ax, 1.0, 2.55, '(60)', 9, '#C8D8E8')

    # Encoder layers
    _box(ax, 2.2, 1.0, 1.2, 3.2, PAL['lblue'], alpha=0.85)
    _txt(ax, 2.8, 2.85, '128', 10, PAL['white'], weight='bold')
    _txt(ax, 2.8, 2.55, 'ReLU', 8, '#D0E0F0')

    _box(ax, 3.8, 1.4, 1.0, 2.4, PAL['lblue'], alpha=0.85)
    _txt(ax, 4.3, 2.85, '128', 10, PAL['white'], weight='bold')
    _txt(ax, 4.3, 2.55, 'ReLU', 8, '#D0E0F0')

    # Latent space (bottleneck)
    _box(ax, 5.2, 1.9, 0.8, 1.4, PAL['orange'], alpha=0.92)
    _txt(ax, 5.6, 2.8, '5', 12, PAL['white'], weight='bold')
    _txt(ax, 5.6, 2.35, '隐空间', 7.5, '#FDE8D0')

    # Decoder layers
    _box(ax, 6.4, 1.4, 1.0, 2.4, PAL['lblue'], alpha=0.85)
    _txt(ax, 6.9, 2.85, '128', 10, PAL['white'], weight='bold')
    _txt(ax, 6.9, 2.55, 'ReLU', 8, '#D0E0F0')

    _box(ax, 7.8, 1.0, 1.2, 3.2, PAL['lblue'], alpha=0.85)
    _txt(ax, 8.4, 2.85, '128', 10, PAL['white'], weight='bold')
    _txt(ax, 8.4, 2.55, 'ReLU', 8, '#D0E0F0')

    # Output (reconstruction)
    _box(ax, 9.5, 0.6, 1.4, 4.0, PAL['green'], alpha=0.85)
    _txt(ax, 10.2, 2.9, 'Output', 10, PAL['white'], weight='bold')
    _txt(ax, 10.2, 2.55, '(60)', 9, '#C8E8C8')

    # Arrows
    pairs = [(1.7, 2.2), (3.4, 3.8), (4.8, 5.2), (6.0, 6.4), (7.4, 7.8), (9.0, 9.5)]
    for x1, x2 in pairs:
        _arrow(ax, x1, 2.6, x2, 2.6, PAL['dgray'], 1.3)

    # Labels: Encoder / Decoder
    _txt(ax, 3.2, 4.8, 'Encoder', 12, PAL['dblue'], weight='bold')
    _txt(ax, 3.2, 4.45, '编码器', 10, PAL['text'])
    _txt(ax, 8.0, 4.8, 'Decoder', 12, PAL['dgreen'], weight='bold')
    _txt(ax, 8.0, 4.45, '解码器', 10, PAL['text'])

    # Bottleneck label
    _txt(ax, 5.6, 4.8, 'Latent', 10, PAL['orange'], weight='bold')

    # MSE Loss arrow
    ax.annotate('', xy=(10.2, 0.55), xytext=(1.0, 0.55),
                arrowprops=dict(arrowstyle='<->', color=PAL['red'], lw=1.5,
                               linestyle='dashed'), zorder=5)
    _txt(ax, 5.6, 0.25, 'MSE Loss', 9, PAL['red'], weight='bold')

    # Title
    _txt(ax, 5.5, 5.3, '自编码器算法结构', 14, PAL['text'])

    plt.tight_layout(pad=0.3)
    plt.savefig(OUT + 'autoencoder.png', bbox_inches='tight', facecolor='white')
    plt.savefig(OUT + 'autoencoder.pdf', bbox_inches='tight', facecolor='white')
    plt.close()
    print('[OK] Fig4: Autoencoder diagram')


# ================================================================
# FIGURE 5: Threshold (I-SPOT) and F1 Score Line Chart (Ch3 s3.3)
# ================================================================
def fig5_threshold_f1():
    """Simulated I-SPOT dynamic threshold + F1 score chart."""
    np.random.seed(42)

    # Simulate anomaly scores
    n = 500
    base = np.random.exponential(1.0, n)
    # Inject anomalies
    anomaly_idx = [120, 121, 122, 200, 201, 280, 281, 282, 350, 351, 420, 421]
    for i in anomaly_idx:
        if i < n:
            base[i] += np.random.uniform(3.5, 6.0)

    # Simulate I-SPOT threshold (gradually adapting)
    threshold = np.zeros(n)
    t0 = np.percentile(base[:100], 96)
    threshold[:100] = t0
    zq = t0 + 1.5
    for i in range(100, n):
        noise = np.random.normal(0, 0.02)
        if base[i] > zq:
            zq = zq + 0.05  # slight increase after anomaly
        elif base[i] > t0:
            zq = zq - 0.01 + noise  # gradual adaptation
        else:
            zq = zq + noise * 0.5
        zq = max(zq, t0 + 0.3)
        threshold[i] = zq

    # Compute F1 for various static thresholds
    thresholds_test = np.linspace(1.0, 6.0, 80)
    f1_scores = []
    gt_set = set(anomaly_idx)
    for th in thresholds_test:
        detected = set(np.where(base > th)[0])
        tp = len(detected & gt_set)
        fp = len(detected - gt_set)
        fn = len(gt_set - detected)
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0
        f1_scores.append(f1)

    # Create figure with 2 subplots
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.2))

    # Left: Score + threshold over time
    ax1.plot(base, color=PAL['blue'], alpha=0.5, linewidth=0.6, label='Anomaly Score')
    ax1.plot(threshold, color=PAL['red'], linewidth=1.8, label='I-SPOT Threshold')
    ax1.axhline(y=t0, color=PAL['orange'], linestyle='--', linewidth=1.0, alpha=0.7, label='Initial $t_0$')

    # Mark anomalies
    det_mask = base > threshold
    ax1.scatter(np.where(det_mask)[0], base[det_mask], c=PAL['red'], s=15, zorder=5, label='Detected Anomaly')

    ax1.set_xlabel('Time Window', fontsize=10)
    ax1.set_ylabel('Anomaly Score', fontsize=10)
    ax1.legend(loc='upper right', fontsize=8)
    ax1.set_title('I-SPOT Dynamic Threshold', fontsize=12)
    ax1.grid(True, alpha=0.2)

    # Right: F1 vs threshold
    ax2.plot(thresholds_test, f1_scores, color=PAL['blue'], linewidth=2.0)
    best_idx = np.argmax(f1_scores)
    ax2.axvline(x=thresholds_test[best_idx], color=PAL['red'], linestyle='--', linewidth=1.2, alpha=0.7)
    ax2.scatter([thresholds_test[best_idx]], [f1_scores[best_idx]], color=PAL['red'], s=60, zorder=5)
    ax2.annotate(f'Best F1={f1_scores[best_idx]:.2f}',
                 xy=(thresholds_test[best_idx], f1_scores[best_idx]),
                 xytext=(thresholds_test[best_idx]+0.8, f1_scores[best_idx]-0.1),
                 fontsize=9, color=PAL['red'],
                 arrowprops=dict(arrowstyle='->', color=PAL['red'], lw=1.0))

    ax2.set_xlabel('Threshold', fontsize=10)
    ax2.set_ylabel('F1 Score', fontsize=10)
    ax2.set_title('Threshold vs F1 Score', fontsize=12)
    ax2.grid(True, alpha=0.2)
    ax2.set_ylim(-0.05, 1.05)

    plt.tight_layout(pad=0.5)
    plt.savefig(OUT + 'threshold_f1.png', bbox_inches='tight', facecolor='white')
    plt.savefig(OUT + 'threshold_f1.pdf', bbox_inches='tight', facecolor='white')
    plt.close()
    print('[OK] Fig5: Threshold & F1 chart')


# ================================================================
# FIGURE 6: CSAD-AT Overall Framework Architecture (Ch3 s3.4)
# ================================================================
def fig6_framework():
    fig, ax = plt.subplots(figsize=(13, 8))
    ax.set_xlim(0, 13)
    ax.set_ylim(0, 8.5)
    ax.axis('off')

    # ── Stage 1: Data Input (left) ──
    _bg(ax, 0.2, 5.6, 2.8, 2.4, PAL['bg1'], alpha=0.4)
    _txt(ax, 1.6, 7.78, '数据输入', 10, '#555555', weight='bold')

    # Multiple node curves
    _box(ax, 0.5, 6.65, 2.2, 0.7, PAL['blue'], alpha=0.85)
    _txt(ax, 1.6, 7.0, '多节点时序数据', 9, PAL['white'])

    _box(ax, 0.5, 5.8, 2.2, 0.7, PAL['lblue'], alpha=0.85)
    _txt(ax, 1.6, 6.15, '滑动窗口分割', 9, PAL['white'])

    # ── Stage 2: Scoring Module (center top) ──
    _bg(ax, 3.5, 5.1, 6.0, 3.0, PAL['bg2'], alpha=0.35)
    _txt(ax, 6.5, 7.9, '多方法异常评分模块', 10, '#555555', weight='bold')

    # Three scoring methods
    _box(ax, 3.8, 6.7, 1.7, 0.9, PAL['green'])
    _txt(ax, 4.65, 7.28, 'AE', 10, PAL['white'], weight='bold')
    _txt(ax, 4.65, 6.98, '自编码器评分', 8, '#C8E8C8')

    _box(ax, 5.7, 6.7, 1.7, 0.9, PAL['blue'])
    _txt(ax, 6.55, 7.28, 'Euclidean', 10, PAL['white'], weight='bold')
    _txt(ax, 6.55, 6.98, '欧氏距离评分', 8, '#C8D8F0')

    _box(ax, 7.6, 6.7, 1.7, 0.9, PAL['orange'])
    _txt(ax, 8.45, 7.28, 'Adaptive', 10, PAL['white'], weight='bold')
    _txt(ax, 8.45, 6.98, '自适应密度评分', 7.5, '#FDE8D0')

    # Z-score calculation
    _box(ax, 4.8, 5.4, 3.4, 0.85, PAL['lblue'])
    _txt(ax, 6.5, 5.95, 'Z-Score', 10, PAL['white'], weight='bold')
    _txt(ax, 6.5, 5.65, '标准化异常评分', 8, '#D0E0F0')

    # Arrows from methods to Z-score
    for mx in [4.65, 6.55, 8.45]:
        _arrow(ax, mx, 6.7, 6.5, 6.28, PAL['dgray'], 1.0)

    # ── Stage 3: Score Merging ──
    _bg(ax, 3.5, 3.3, 6.0, 1.5, PAL['bg3'], alpha=0.35)
    _txt(ax, 6.5, 4.6, '评分融合模块', 10, '#555555', weight='bold')
    _box(ax, 4.5, 3.5, 4.0, 0.85, PAL['dgreen'])
    _txt(ax, 6.5, 4.05, 'Weighted Merge', 10, PAL['white'], weight='bold')
    _txt(ax, 6.5, 3.75, '加权融合评分', 8, '#C8E8C8')

    # ── Stage 4: Threshold Detection ──
    _bg(ax, 3.5, 1.0, 6.0, 1.8, PAL['bg4'], alpha=0.35)
    _txt(ax, 6.5, 2.6, '自适应阈值检测模块', 10, '#555555', weight='bold')
    _box(ax, 4.2, 1.2, 2.0, 1.0, PAL['red'])
    _txt(ax, 5.2, 1.82, 'I-SPOT', 11, PAL['white'], weight='bold')
    _txt(ax, 5.2, 1.5, 'GPD', 9, '#F0C8C8')

    _box(ax, 6.8, 1.2, 2.4, 1.0, PAL['red'], alpha=0.8)
    _txt(ax, 8.0, 1.82, '动态阈值', 10, PAL['white'])
    _txt(ax, 8.0, 1.5, '异常判定', 9, '#F0C8C8')

    _arrow(ax, 6.2, 1.7, 6.8, 1.7, PAL['dgray'], 1.3)

    # ── Stage 5: Output (right) ──
    _bg(ax, 10.0, 0.8, 2.8, 2.4, '#F8F0FF', alpha=0.4)
    _txt(ax, 11.4, 3.0, '检测输出', 10, '#555555', weight='bold')
    _box(ax, 10.3, 1.8, 2.2, 0.7, PAL['purple'])
    _txt(ax, 11.4, 2.15, '异常节点', 9.5, PAL['white'])
    _box(ax, 10.3, 0.95, 2.2, 0.7, PAL['purple'], alpha=0.7)
    _txt(ax, 11.4, 1.3, '异常时段', 9.5, PAL['white'])

    # ── Distributed Processing (bottom right) ──
    _bg(ax, 10.0, 4.5, 2.8, 3.5, '#F0F0F0', alpha=0.4)
    _txt(ax, 11.4, 7.78, '分布式计算', 10, '#555555', weight='bold')
    _box(ax, 10.3, 6.8, 2.2, 0.65, PAL['gray'])
    _txt(ax, 11.4, 7.12, 'Spark', 9, PAL['white'], weight='bold')
    _box(ax, 10.3, 6.0, 2.2, 0.65, PAL['gray'])
    _txt(ax, 11.4, 6.32, 'YARN', 9, PAL['white'], weight='bold')
    _box(ax, 10.3, 5.2, 2.2, 0.65, PAL['gray'])
    _txt(ax, 11.4, 5.52, 'HDFS', 9, PAL['white'], weight='bold')
    _box(ax, 10.3, 4.65, 2.2, 0.4, PAL['lgray'], ec='#BBBBBB')
    _txt(ax, 11.4, 4.85, '集群节点', 8, PAL['dgray'])

    # ── Main flow arrows ──
    # Data input -> Scoring
    _arrow(ax, 2.7, 6.5, 3.5, 6.5, PAL['dgray'], 1.5)
    # Scoring -> Merging
    _arrow(ax, 6.5, 5.4, 6.5, 4.85, PAL['dgray'], 1.5)
    # Merging -> Threshold
    _arrow(ax, 6.5, 3.5, 6.5, 2.85, PAL['dgray'], 1.5)
    # Threshold -> Output
    _arrow(ax, 9.2, 1.7, 10.3, 1.7, PAL['dgray'], 1.5)

    # Distributed -> all stages (dashed)
    for ty in [6.5, 4.0, 1.7]:
        ax.annotate('', xy=(9.55, ty), xytext=(10.0, ty),
                    arrowprops=dict(arrowstyle='<-', color='#BBBBBB', lw=0.8,
                                   linestyle='dashed'), zorder=2)

    # Title
    _txt(ax, 4.0, 8.3, 'CSAD-AT', 15, PAL['text'], weight='bold')
    _txt(ax, 7.65, 8.3, '框架整体架构', 15, PAL['text'])

    plt.tight_layout(pad=0.3)
    plt.savefig(OUT + 'csad_framework.png', bbox_inches='tight', facecolor='white')
    plt.savefig(OUT + 'csad_framework.pdf', bbox_inches='tight', facecolor='white')
    plt.close()
    print('[OK] Fig6: CSAD-AT Framework')


# ================================================================
# Main
# ================================================================
if __name__ == '__main__':
    fig1_hadoop_cluster()
    fig2_yarn_rpc()
    fig3_annotation()
    fig4_autoencoder()
    fig5_threshold_f1()
    fig6_framework()
    print('\nAll 6 figures done!')
