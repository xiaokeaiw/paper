import matplotlib.pyplot as plt
import numpy as np

# 设置科研绘图风格
plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams['font.size'] = 10
plt.rcParams['axes.labelsize'] = 11
plt.rcParams['axes.titlesize'] = 12
plt.rcParams['xtick.labelsize'] = 9
plt.rcParams['ytick.labelsize'] = 9
plt.rcParams['legend.fontsize'] = 9

# 数据准备
thresholds_euc_ae = [3.0, 3.2, 3.4, 3.6, 3.8]  # 欧氏距离和AE方法的阈值
eps_values = [200, 400, 600, 800, 1000]  # DBSCAN方法的eps参数

# 将两种参数归一化到[0, 1]范围，实现横轴对齐
def normalize_to_range(values, target_min=0, target_max=1):
    """将数值序列归一化到指定范围"""
    min_val = min(values)
    max_val = max(values)
    if max_val == min_val:
        return [target_min] * len(values)
    return [target_min + (target_max - target_min) * (v - min_val) / (max_val - min_val) for v in values]

# 归一化后的x坐标
thresholds_norm = normalize_to_range(thresholds_euc_ae)
eps_norm = normalize_to_range(eps_values)

# 欧氏距离方法: F1值 (window size=10, 20, 30)
f1_euclidean = {
    10: [0.7084, 0.8093, 0.8960, 0.9593, 0.0000],
    20: [0.8406, 0.8822, 0.9459, 0.9741, 0.0000],
    30: [0.9020, 0.9243, 0.9614, 0.9596, 0.0000]
}

# AE方法: F1值 (window size=10, 20, 30)
f1_ae = {
    10: [0.6051, 0.7554, 0.8668, 0.9234, 0.0000],
    20: [0.7522, 0.8802, 0.9449, 0.9595, 0.0000],
    30: [0.8376, 0.9125, 0.9589, 0.9691, 0.0000]
}

# DBSCAN方法: F1值 (window size=10, 20, 30)
f1_dbscan = {
    10: [0.3735, 0.9562, 0.9745, 0.9034, 0.8691],  # eps:200,400,600,800,1000
    20: [0.0585, 0.9016, 0.9738, 0.9467, 0.9079],  # eps:200,400,600,800,1000
    30: [0.0309, 0.7260, 0.9660, 0.9591, 0.9015]   # eps:200,400,600,800,1000
}

# 创建图形和子图
fig, axes = plt.subplots(1, 3, figsize=(15, 4.5), sharey=True)

# 定义低饱和度配色方案
colors = {
    'euclidean': '#1f77b4',  # 柔和的蓝色
    'ae': '#2ca02c',         # 柔和的绿色
    'dbscan': '#d62728'      # 柔和的红色
}

# 窗口大小列表
window_sizes = [10, 20, 30]

# 绘制每个窗口大小的子图
for idx, (ax, ws) in enumerate(zip(axes, window_sizes)):
    # 欧氏距离方法 - 使用归一化的阈值作为x坐标
    euclidean_line, = ax.plot(thresholds_norm, f1_euclidean[ws], marker='o', linestyle='-', 
            color=colors['euclidean'], label='Euclidean', linewidth=2, markersize=6,
            markerfacecolor='white', markeredgewidth=1.5)
    
    # AE方法 - 使用归一化的阈值作为x坐标
    ae_line, = ax.plot(thresholds_norm, f1_ae[ws], marker='s', linestyle='--', 
            color=colors['ae'], label='AE', linewidth=2, markersize=6,
            markerfacecolor='white', markeredgewidth=1.5)
    
    # DBSCAN方法 - 使用归一化的eps作为x坐标
    dbscan_line, = ax.plot(eps_norm, f1_dbscan[ws], marker='^', linestyle=':', 
            color=colors['dbscan'], label='DBSCAN', linewidth=2, markersize=6,
            markerfacecolor='white', markeredgewidth=1.5)
    
    # 设置x轴范围和刻度
    ax.set_xlim(-0.05, 1.05)
    
    # 隐藏主x轴的刻度和标签
    ax.set_xticks([])
    
    # 创建底部x轴显示原始阈值
    ax_thresh = ax.secondary_xaxis('bottom')
    # 移除底部x轴的标签文字
    ax_thresh.set_xlabel('')
    # 隐藏底部x轴的刻度标签
    ax_thresh.set_xticks([])
    ax_thresh.set_xticklabels([])
    
    # 创建顶部x轴显示原始eps值
    ax_eps = ax.secondary_xaxis('top')
    # 移除顶部x轴的标签文字
    ax_eps.set_xlabel('')
    # 隐藏顶部x轴的刻度标签
    ax_eps.set_xticks([])
    ax_eps.set_xticklabels([])
    
    # 在数据点附近标注数值
    # 标注欧氏距离方法的阈值
    for i, (x, y) in enumerate(zip(thresholds_norm, f1_euclidean[ws])):
        if y > 0:  # 只标注非零值
            ax.annotate(f'{thresholds_euc_ae[i]}', xy=(x, y), xytext=(0, 8),
                       textcoords='offset points', ha='center', va='bottom',
                       fontsize=7, color=colors['euclidean'], fontweight='bold')
    
    # 标注AE方法的阈值
    for i, (x, y) in enumerate(zip(thresholds_norm, f1_ae[ws])):
        if y > 0:  # 只标注非零值
            ax.annotate(f'{thresholds_euc_ae[i]}', xy=(x, y), xytext=(0, -12),
                       textcoords='offset points', ha='center', va='top',
                       fontsize=7, color=colors['ae'], fontweight='bold')
    
    # 标注DBSCAN方法的eps值（移除边框）
    for i, (x, y) in enumerate(zip(eps_norm, f1_dbscan[ws])):
        if y > 0:  # 只标注非零值
            ax.annotate(f'{eps_values[i]}', xy=(x, y), xytext=(0, 8),
                       textcoords='offset points', ha='center', va='bottom',
                       fontsize=7, color=colors['dbscan'], fontweight='bold')
    
    # 设置y轴
    if idx == 0:
        ax.set_ylabel('F1 Score', fontsize=11)
    ax.set_ylim(0, 1.05)
    ax.set_yticks(np.arange(0, 1.1, 0.2))
    
    # 设置网格
    ax.grid(True, linestyle='--', alpha=0.5, linewidth=0.5)
    
    # 设置子图标题
    ax.set_title(f'Window Size = {ws}', fontsize=12, fontweight='normal', pad=15)
    
    # 添加图例 - 向右移动以避免遮挡曲线
    ax.legend(loc='lower left', bbox_to_anchor=(0.25, 0.0), fontsize=9, 
              framealpha=0.9, edgecolor='gray')

# 调整布局
plt.tight_layout()

# 显示图形
plt.show()

# 可选：保存图片
# plt.savefig('threshold_f1_curves_clean.png', dpi=300, bbox_inches='tight', 
#            transparent=False, facecolor='white')
