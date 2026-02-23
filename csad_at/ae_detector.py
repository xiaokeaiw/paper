"""
自编码器嵌入视角 - 距离偏离度分数

核心思路：
  1. 用自编码器将每个节点的时间窗口片段编码到低维潜在空间
  2. 在潜在空间中计算节点间的欧氏距离矩阵
  3. 异常分数 = 节点在嵌入空间的平均距离 - 窗口全局平均距离

  与欧氏距离视角的区别：自编码器学到了时序数据的非线性压缩表示，
  距离度量在这个"学习到的表示空间"中进行，能捕获更复杂的异常模式。

  同样不做 Z-score，保留原始嵌入空间距离的偏离度。

对应论文第三章 3.3 节
"""

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from tqdm import tqdm

torch.manual_seed(42)
np.random.seed(42)


class AutoEncoder(nn.Module):
    """自编码器：将时间窗口片段编码到低维潜在空间"""

    def __init__(self, input_dim, latent_dim=5, hidden_dim=128):
        super(AutoEncoder, self).__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, latent_dim),
        )
        self.decoder = nn.Sequential(
            nn.Linear(latent_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, input_dim),
        )

    def encode(self, x):
        return self.encoder(x)

    def forward(self, x):
        z = self.encode(x)
        return self.decoder(z), z


def train_ae(model, dataloader, epochs=50, lr=1e-3, device='cpu'):
    """训练自编码器"""
    model.to(device)
    optimizer = optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.MSELoss(reduction='sum')

    for epoch in range(epochs):
        model.train()
        total_loss = 0
        for (batch,) in dataloader:
            batch = batch.float().to(device)
            optimizer.zero_grad()
            recon, _ = model(batch)
            loss = loss_fn(recon, batch)
            loss.backward()
            total_loss += loss.item()
            optimizer.step()

        if (epoch + 1) % 10 == 0:
            avg = total_loss / len(dataloader.dataset)
            print(f"  [AE] Epoch {epoch+1}/{epochs}, Loss: {avg:.4f}")

    return model


def normalize_windows(windows):
    """Min-max 归一化窗口数据到 [0,1]"""
    windows = np.nan_to_num(windows, nan=0.0)
    global_min = np.min(windows)
    global_max = np.max(windows)
    if global_max - global_min < 1e-8:
        return (windows - np.mean(windows)) / (np.std(windows) + 1e-8)
    return (windows - global_min) / (global_max - global_min + 1e-8)


def compute_ae_deviation_scores(window_curves, ae_model, device='cpu'):
    """
    计算单个窗口内各节点的自编码器嵌入距离偏离度分数

    参数:
        window_curves: list of ndarray, 每个元素 shape=(window_size,)
        ae_model: 已训练的 AutoEncoder
        device: 计算设备

    返回:
        deviation_scores: ndarray, shape=(N,)
    """
    n = len(window_curves)
    if n <= 1:
        return np.zeros(n)

    # 编码到潜在空间
    curve_tensor = torch.tensor(
        np.array(window_curves, dtype=np.float32)).to(device)
    with torch.no_grad():
        _, embeddings = ae_model(curve_tensor)
        embeddings = embeddings.cpu().numpy()  # (N, latent_dim)

    # 嵌入空间中的欧氏距离矩阵
    diff = embeddings[:, None, :] - embeddings[None, :, :]  # (N, N, D)
    dist_matrix = np.sqrt(np.sum(diff ** 2, axis=2))  # (N, N)

    # 节点平均距离
    node_avg_distances = dist_matrix.sum(axis=1) / (n - 1)

    # 全局平均
    global_mean = node_avg_distances.mean()

    # 偏离度
    deviation_scores = node_avg_distances - global_mean

    return deviation_scores


def run_ae_detector(curves, timestamps, window_size=20, step=10,
                    latent_dim=5, hidden_dim=128, epochs=50, lr=1e-3,
                    batch_size=32):
    """
    对完整时间序列运行自编码器嵌入偏离度检测

    参数:
        curves: list of ndarray, 每个节点的完整时序
        timestamps: ndarray, 时间戳
        window_size: 滑动窗口大小
        step: 步长
        latent_dim: 潜在空间维度
        hidden_dim: 隐藏层维度
        epochs: 训练轮数
        lr: 学习率
        batch_size: 批大小

    返回:
        dict: 检测结果
    """
    T = len(timestamps)
    n_nodes = len(curves)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # ========== 1. 准备训练数据 ==========
    print("[AE] 准备训练数据...")
    all_windows = []
    for start in range(0, T - window_size + 1, step):
        end = start + window_size
        for curve in curves:
            all_windows.append(curve[start:end].astype(np.float32))

    all_windows = np.array(all_windows)
    all_windows = normalize_windows(all_windows)

    # ========== 2. 训练自编码器 ==========
    print(f"[AE] 训练自编码器 (latent_dim={latent_dim}, epochs={epochs})...")
    dataset = TensorDataset(torch.tensor(all_windows))
    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)
    model = AutoEncoder(window_size, latent_dim, hidden_dim).to(device)
    model = train_ae(model, dataloader, epochs, lr, device)
    model.eval()

    # ========== 3. 滑动窗口检测 ==========
    total_windows = max(1, (T - window_size) // step)
    results = {
        'scores': {i: [] for i in range(n_nodes)},
        'window_starts': [],
        'window_ends': [],
    }

    for start in tqdm(range(0, T - window_size, step),
                      total=total_windows, desc="[AE] 滑动窗口"):
        end = start + window_size
        results['window_starts'].append(timestamps[start])
        results['window_ends'].append(timestamps[end - 1])

        # 提取并归一化窗口数据
        window_curves_raw = [curve[start:end].astype(np.float32)
                             for curve in curves]
        window_arr = np.array(window_curves_raw)
        window_arr = normalize_windows(window_arr)
        window_curves = [window_arr[i] for i in range(n_nodes)]

        # 计算嵌入偏离度分数
        deviation = compute_ae_deviation_scores(
            window_curves, model, device)

        for i in range(n_nodes):
            results['scores'][i].append(float(deviation[i]))

    results['n_windows'] = len(results['window_starts'])
    results['n_nodes'] = n_nodes
    return results
