# CPU対戦AI（PPO）実装メモ

このドキュメントは、ポケモンカードCPU対戦に追加したPPOベースAIの構成、接続方法、学習手順をまとめたものです。

## 1. 追加したファイル

- backend/cpu/battle_env.py
- backend/cpu/ppo_agent.py
- backend/cpu/selfplay_trainer.py
- backend/cpu/game_integration.py
- backend/cpu/evaluate_agent.py

## 2. アーキテクチャ概要

### battle_env.py

役割:

- Gymnasium環境 PokemonBattleEnv の提供
- 既存ゲームエンジンをRL向けに接続する EngineBattleAdapter の提供
- 観測ベクトル化・有効行動列挙・アクション適用の共通処理

主な仕様:

- observation_space: Box(shape=(128,), dtype=float32)
- action_space: Discrete(20)
- 無効行動: -0.1
- 報酬:
  - サイド取得: +2.0
  - 相手HP減少: +0.5（正規化）
  - 自分がきぜつ: -1.0
  - 勝利: +10.0
  - 敗北: -10.0

### ppo_agent.py

役割:

- stable-baselines3 PPOの初期化・学習・推論のラッパー

設定:

- net_arch=[256, 256]
- activation_fn=ReLU
- learning_rate=3e-4
- n_steps=2048
- batch_size=64
- n_epochs=10

### selfplay_trainer.py

役割:

- 8並列環境（SubprocVecEnv）で2段階学習を実行

学習フェーズ:

- Phase1: ヒューリスティックCPU相手に500,000 step
- Phase2: スナップショット自己対戦で1,000,000 step

出力:

- backend/cpu/models/ppo_phase1
- backend/cpu/models/ppo*selfplay_round*\*
- backend/cpu/models/ppo_final

### game_integration.py

役割:

- 学習済みモデルをロードしてゲーム中に推論を行う CPUPlayer を提供

公開メソッド:

- decide_action(game_state) -> int
  - 現在状態から action_id（0..19）を返す
- play_turn(game_state, max_steps=20) -> list[dict]
  - CPUターンを終了まで実行

## 3. 既存バトルロジック接続インターフェース

battle_env.py で以下インターフェースを定義:

- get_state() -> np.ndarray
  - 128次元のfloat32観測ベクトル
- get_valid_actions() -> set[int]
  - 現在状態で選択可能な action_id 集合
- apply_action(action_id: int) -> ActionOutcome
  - 行動適用結果（成功/失敗、報酬計算用情報含む）
- is_over() -> bool
  - ゲーム終了判定

## 4. Action ID定義（20個）

- 0: 攻撃0
- 1: 攻撃1
- 2-11: 手札スロット0-9を使用
- 12: 逃げる
- 13-18: ベンチ候補0-5へ交代/補充
- 19: ターン終了

## 5. API統合（CPU対戦）

backend/api/game.py にCPU実行ヘルパーを追加。

切替方式:

- CPU_AI_MODE=heuristic（デフォルト）
  - 従来ルールベースCPUを使用
- CPU_AI_MODE=ppo
  - CPU_AI_MODEL_PATH が設定されていればPPO推論を使用
  - 読み込み失敗時は自動でheuristicへフォールバック

## 6. 学習・実行の例

### 学習

backendディレクトリで実行:

python -m cpu.selfplay_trainer

### APIでPPO CPUを有効化

例:

- CPU_AI_MODE=ppo
- CPU_AI_MODEL_PATH=backend/cpu/models/ppo_final.zip

この状態でCPU対戦APIを呼ぶと、CPUターンでモデル推論が使われる。

### 評価（PPO vs 既存CPU）

追加した評価スクリプト:

- backend/cpu/evaluate_agent.py

実行例:

python -m cpu.evaluate_agent --model-path backend/cpu/models/ppo_final.zip --games 50 --ppo-side player2

出力内容:

- 総試合数
- PPO勝利数と勝率
- 既存（heuristic）CPU勝利数と勝率
- 引き分け数

## 7. 依存関係

追加した主要依存:

- stable-baselines3
- gymnasium
- torch
- numpy

requirements:

- pokeca/requirements.txt
- pokeca/backend/requirements.txt

## 8. 今後の改善候補

- 観測ベクトルの特徴量強化（ワザコスト達成率、進化可否、盤面テンポ）
- Action IDの細分化（対象指定や複数候補の明示）
- 自己対戦プール（過去複数モデルを確率混合）
- 評価用スクリプト（勝率、平均取得サイド、平均ターン数）

## 9. 運用上の注意

- PPOモデルのロードに失敗した場合、APIは自動で既存CPUへフォールバックする。
- APIでPPOモードにするには、CPU_AI_MODE=ppo と CPU_AI_MODEL_PATH の両方が必要。
- CPU_AI_MODEL_PATH は stable-baselines3 の PPO.load() が読める .zip パスを指定する。
