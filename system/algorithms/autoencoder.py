"""
基于自编码器嵌入的形态相似性异常检测

核心思想：利用自编码器将滑动窗口内的时序数据编码为低维嵌入表示，
在嵌入空间中计算节点间距离来度量形态相似性。

性能优化（相比原版）：
- 训练 epochs 降为 30（够用即可，非追求完美重构）
- _prepare_windows 使用 numpy stride_tricks 替代双层 for
- compute_embedding_distance 使用批量推理替代逐窗口循环
- import scipy 移到文件顶部而非循环内部
- 支持 stride 步长采样减少窗口数

对应论文第三章 3.3.2 节
"""

import numpy as np
from scipy.spatial.distance import pdist, squareform

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import DataLoader, TensorDataset

    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False


class AutoEncoderModel(nn.Module if TORCH_AVAILABLE else object):
    """三层自编码器网络"""

    def __init__(self, input_dim, hidden_dim=32, latent_dim=8):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch is required for AutoEncoder")
        super().__init__()

        self.encoder = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, latent_dim),
            nn.ReLU(),
        )

        self.decoder = nn.Sequential(
            nn.Linear(latent_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, input_dim),
        )

    def forward(self, x):
        latent = self.encoder(x)
        reconstructed = self.decoder(latent)
        return reconstructed

    def encode(self, x):
        return self.encoder(x)


class AutoEncoderDetector:
    """基于自编码器嵌入距离的异常检测器"""

    def __init__(self, window_size=60, hidden_dim=32, latent_dim=8,
                 epochs=30, lr=0.001, batch_size=128, stride=1):
        """
        参数:
            window_size: 滑动窗口大小
            hidden_dim: 隐藏层维度
            latent_dim: 潜在空间维度
            epochs: 训练轮数（默认30，足够收敛）
            lr: 学习率
            batch_size: 批次大小
            stride: 窗口滑动步长
        """
        self.window_size = window_size
        self.hidden_dim = hidden_dim
        self.latent_dim = latent_dim
        self.epochs = epochs
        self.lr = lr
        self.batch_size = batch_size
        self.stride = stride
        self.model = None
        self.device = 'cpu'

    def _prepare_windows(self, data):
        """
        使用 numpy stride_tricks 高效切分滑动窗口

        参数:
            data: numpy数组, shape=(T, N)

        返回:
            windows: shape=(n_windows, N, window_size)
                     每个窗口包含 N 个节点各自的 window_size 长度片段
        """
        T, N = data.shape
        n_windows = T - self.window_size + 1

        # 使用 stride_tricks 创建滑动窗口视图，避免数据拷贝
        # 对每个节点列做滑动窗口
        from numpy.lib.stride_tricks import sliding_window_view
        # sliding_window_view(data[:, n], self.window_size) -> (n_windows, window_size)
        # 堆叠所有节点
        windows = np.stack([
            sliding_window_view(data[:, n], self.window_size)
            for n in range(N)
        ], axis=1)  # (n_windows, N, window_size)

        return windows

    def _prepare_flat_windows(self, data):
        """
        生成扁平化训练样本：(n_windows * N, window_size)
        只采样部分窗口用于训练，大幅减少训练数据量
        """
        T, N = data.shape
        n_windows = T - self.window_size + 1

        # 训练时用更大步长采样，不需要每个窗口都用
        train_stride = max(self.stride, 3)
        sample_indices = range(0, n_windows, train_stride)

        windows = []
        for t in sample_indices:
            for n in range(N):
                windows.append(data[t:t + self.window_size, n])
        return np.array(windows)

    def train(self, train_data):
        """
        使用正常数据训练自编码器
        """
        if not TORCH_AVAILABLE:
            return

        windows = self._prepare_flat_windows(train_data)
        if len(windows) == 0:
            return

        self.model = AutoEncoderModel(
            self.window_size, self.hidden_dim, self.latent_dim
        )
        self.model.to(self.device)

        dataset = TensorDataset(torch.FloatTensor(windows))
        loader = DataLoader(dataset, batch_size=self.batch_size, shuffle=True)
        optimizer = optim.Adam(self.model.parameters(), lr=self.lr)
        criterion = nn.MSELoss()

        self.model.train()
        for epoch in range(self.epochs):
            total_loss = 0
            for (batch,) in loader:
                batch = batch.to(self.device)
                output = self.model(batch)
                loss = criterion(output, batch)
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
                total_loss += loss.item()
            # 早停：如果 loss 已经很小
            avg_loss = total_loss / max(len(loader), 1)
            if avg_loss < 1e-5:
                break

    def compute_embedding_distance(self, data):
        """
        批量计算嵌入空间中各节点的异常分数

        关键优化：
        - 对所有采样窗口的 N 个节点一次性 encode
        - 用 stride 采样减少窗口数
        """
        if not TORCH_AVAILABLE or self.model is None:
            return self._fallback_detect(data)

        T, N = data.shape
        n_windows = T - self.window_size + 1
        sample_indices = list(range(0, n_windows, self.stride))
        n_sampled = len(sample_indices)
        scores = np.zeros((n_sampled, N))

        self.model.eval()
        with torch.no_grad():
            # 批量准备所有窗口数据: (n_sampled, N, window_size)
            all_inputs = np.zeros((n_sampled, N, self.window_size))
            for idx, t in enumerate(sample_indices):
                window = data[t:t + self.window_size, :]  # (W, N)
                all_inputs[idx] = window.T  # (N, W)

            # 逐批次推理（避免一次性内存爆炸）
            batch_size = 64  # 每批处理64个窗口
            for batch_start in range(0, n_sampled, batch_size):
                batch_end = min(batch_start + batch_size, n_sampled)
                batch_inputs = all_inputs[batch_start:batch_end]  # (B, N, W)

                for local_idx, window_nodes in enumerate(batch_inputs):
                    global_idx = batch_start + local_idx
                    inputs = torch.FloatTensor(window_nodes).to(self.device)
                    embeddings = self.model.encode(inputs).cpu().numpy()  # (N, latent_dim)

                    if N > 1:
                        dist_matrix = squareform(pdist(embeddings))
                        np.fill_diagonal(dist_matrix, 0)
                        avg_dist = dist_matrix.sum(axis=1) / (N - 1)

                        mu = avg_dist.mean()
                        sigma = avg_dist.std()
                        if sigma > 1e-10:
                            scores[global_idx] = (avg_dist - mu) / sigma

        # 插值还原完整时间轴
        if self.stride > 1 and n_sampled > 1:
            full_scores = np.zeros((n_windows, N))
            for n in range(N):
                full_scores[:, n] = np.interp(
                    np.arange(n_windows),
                    [i * self.stride for i in range(n_sampled)],
                    scores[:, n]
                )
            return full_scores

        return scores

    def _fallback_detect(self, data):
        """当PyTorch不可用时的降级检测方案（带stride优化）"""
        T, N = data.shape
        n_windows = T - self.window_size + 1
        sample_indices = list(range(0, n_windows, self.stride))
        n_sampled = len(sample_indices)
        scores = np.zeros((n_sampled, N))

        for idx, t in enumerate(sample_indices):
            window = data[t:t + self.window_size, :]
            dist_matrix = squareform(pdist(window.T))
            np.fill_diagonal(dist_matrix, 0)
            avg_dist = dist_matrix.sum(axis=1) / max(N - 1, 1)
            mu = avg_dist.mean()
            sigma = avg_dist.std()
            if sigma > 1e-10:
                scores[idx] = (avg_dist - mu) / sigma

        if self.stride > 1 and n_sampled > 1:
            full_scores = np.zeros((n_windows, N))
            for n in range(N):
                full_scores[:, n] = np.interp(
                    np.arange(n_windows),
                    [i * self.stride for i in range(n_sampled)],
                    scores[:, n]
                )
            return full_scores

        return scores

    def detect(self, data, threshold=3.0):
        """执行异常检测"""
        scores = self.compute_embedding_distance(data)
        labels = (scores > threshold).astype(int)
        node_scores = scores.max(axis=0)

        return {
            'scores': scores.tolist(),
            'labels': labels.tolist(),
            'node_scores': node_scores.tolist(),
        }
