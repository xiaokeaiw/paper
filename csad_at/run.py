"""
CSAD-AT 命令行入口

用法:
    python -m csad_at.run data.csv --output results/
    python -m csad_at.run data.csv --window 60 --step 30 --weights 0.4 0.3 0.3
    python -m csad_at.run data.csv --no-plot  # 不生成可视化
"""

import argparse
import os
import sys
import time

from .pipeline import run_pipeline, save_results
from .visualize import generate_all_plots


def parse_args():
    parser = argparse.ArgumentParser(
        description='CSAD-AT: 基于曲线相似性的自适应阈值异常检测框架',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 使用默认参数运行（含可视化）
  python -m csad_at.run input.csv --output results/

  # 自定义窗口和权重
  python -m csad_at.run input.csv --window 120 --step 60 --weights 0.5 0.3 0.2

  # 只使用欧氏距离和自编码器
  python -m csad_at.run input.csv --methods euclidean autoencoder --output results/

  # 不生成可视化图表
  python -m csad_at.run input.csv --no-plot
        """)

    # 数据输入
    parser.add_argument('csv_file', help='输入 CSV 文件路径（首列时间戳，其余列为节点时序）')
    parser.add_argument('--output', '-o', default='csad_at_results',
                        help='输出目录（默认: csad_at_results）')

    # 滑动窗口参数
    parser.add_argument('--window', type=int, default=60,
                        help='滑动窗口大小（默认: 60）')
    parser.add_argument('--step', type=int, default=30,
                        help='窗口滑动步长（默认: 30）')

    # 方法选择与权重
    parser.add_argument('--methods', nargs='+',
                        choices=['euclidean', 'autoencoder', 'dbscan'],
                        default=['euclidean', 'autoencoder', 'dbscan'],
                        help='启用的检测方法（默认: 全部三种）')
    parser.add_argument('--weights', nargs='+', type=float,
                        default=None,
                        help='各方法权重，与 --methods 顺序对应（默认: 等权）')

    # DBSCAN 参数
    parser.add_argument('--k-neighbors', type=int, default=5,
                        help='DBSCAN k 近邻数（默认: 5）')

    # 自编码器参数
    parser.add_argument('--ae-latent-dim', type=int, default=5,
                        help='自编码器潜在空间维度（默认: 5）')
    parser.add_argument('--ae-epochs', type=int, default=50,
                        help='自编码器训练轮数（默认: 50）')
    parser.add_argument('--ae-lr', type=float, default=1e-3,
                        help='自编码器学习率（默认: 0.001）')

    # I-SPOT 参数
    parser.add_argument('--anomaly-ratio', type=float, default=0.0085,
                        help='I-SPOT 目标误报率 q（默认: 0.0085）')
    parser.add_argument('--ispot-level', type=float, default=0.98,
                        help='I-SPOT 初始阈值分位数（默认: 0.98）')
    parser.add_argument('--ispot-t-update', type=int, default=50,
                        help='I-SPOT GPD 重估间隔（默认: 50）')
    parser.add_argument('--ispot-w-max', type=int, default=None,
                        help='I-SPOT 数据池最大容量（默认: 无限制）')

    # 可视化
    parser.add_argument('--no-plot', action='store_true',
                        help='不生成可视化图表')

    return parser.parse_args()


def main():
    args = parse_args()

    # 检查输入文件
    if not os.path.exists(args.csv_file):
        print(f"错误: 输入文件不存在: {args.csv_file}")
        sys.exit(1)

    # 设置默认权重
    weights = args.weights
    if weights is None:
        n_methods = len(args.methods)
        weights = [1.0 / n_methods] * n_methods
    elif len(weights) != len(args.methods):
        print(f"错误: 权重数量({len(weights)})与方法数量({len(args.methods)})不匹配")
        sys.exit(1)

    # 补全权重到三维（pipeline 需要三个权重对应三种方法）
    full_weights = [0.0, 0.0, 0.0]
    method_indices = {'euclidean': 0, 'autoencoder': 1, 'dbscan': 2}
    for i, method in enumerate(args.methods):
        full_weights[method_indices[method]] = weights[i]

    start_time = time.time()

    # ========== 运行检测流水线 ==========
    results = run_pipeline(
        csv_file=args.csv_file,
        window_size=args.window,
        step=args.step,
        weights=full_weights,
        k_neighbors=args.k_neighbors,
        ae_latent_dim=args.ae_latent_dim,
        ae_epochs=args.ae_epochs,
        ae_lr=args.ae_lr,
        anomaly_ratio=args.anomaly_ratio,
        ispot_level=args.ispot_level,
        ispot_t_update=args.ispot_t_update,
        ispot_w_max=args.ispot_w_max,
        methods=args.methods,
    )

    elapsed = time.time() - start_time
    print(f"\n检测耗时: {elapsed:.2f} 秒")

    # ========== 保存结果 ==========
    save_results(results, args.output)

    # ========== 生成可视化 ==========
    if not args.no_plot:
        try:
            generate_all_plots(results, args.output)
        except Exception as e:
            print(f"\n[警告] 可视化生成失败: {e}")
            print("检测结果已正常保存，可手动检查 CSV 文件。")

    print(f"\n总耗时: {time.time() - start_time:.2f} 秒")
    print(f"所有结果已保存到: {args.output}/")


if __name__ == '__main__':
    main()
