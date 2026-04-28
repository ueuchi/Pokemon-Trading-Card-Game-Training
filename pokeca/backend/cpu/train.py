"""
PPO CPU AI 学習スクリプト

使い方:
    cd pokeca/backend
    python -m cpu.train                          # デフォルト設定
    python -m cpu.train --envs 4 --phase1 200000 --phase2 500000

学習済みモデルは cpu/models/ppo_final.zip に保存される。
API起動時に CPU_AI_MODE=ml で使用される。
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="PPO CPU AI 学習")
    parser.add_argument("--envs", type=int, default=4, help="並列環境数 (デフォルト: 4)")
    parser.add_argument("--phase1", type=int, default=200_000, help="Phase1ステップ数: vsルールベースCPU")
    parser.add_argument("--phase2", type=int, default=500_000, help="Phase2ステップ数: 自己対戦")
    parser.add_argument("--output", type=str, default="cpu/models", help="モデル保存先ディレクトリ")
    args = parser.parse_args()

    print("=" * 60)
    print("  PPO CPU AI 学習開始")
    print("=" * 60)
    print(f"  並列環境数  : {args.envs}")
    print(f"  Phase1      : {args.phase1:,} ステップ (vs ルールベースCPU)")
    print(f"  Phase2      : {args.phase2:,} ステップ (自己対戦)")
    print(f"  保存先      : {args.output}/ppo_final.zip")
    print("=" * 60)

    try:
        from cpu.selfplay_trainer import train_with_selfplay
    except ImportError as e:
        print(f"\n[エラー] 機械学習ライブラリが見つかりません: {e}")
        print("以下のコマンドでインストールしてください:")
        print("  pip install torch stable-baselines3 gymnasium numpy")
        return

    start = time.time()
    model_path = train_with_selfplay(
        output_dir=args.output,
        n_envs=args.envs,
        phase1_timesteps=args.phase1,
        phase2_timesteps=args.phase2,
    )
    elapsed = time.time() - start

    print("\n" + "=" * 60)
    print(f"  学習完了! ({elapsed / 60:.1f} 分)")
    print(f"  モデル保存先: {model_path}.zip")
    print()
    print("  CPU難易度 'ML' で使用するには:")
    print("  フロントエンドの難易度選択で「AI (学習済み)」を選んでください。")
    print("=" * 60)


if __name__ == "__main__":
    main()
