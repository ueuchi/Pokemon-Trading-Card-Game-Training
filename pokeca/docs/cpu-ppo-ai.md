# CPU AI — 機械学習（PPO強化学習）ガイド

ポケモンカードゲームトレーニングアプリの CPU AI は、**ルールベース** と **PPO強化学習** の 2 系統に対応しています。
このドキュメントでは学習の実行方法・アーキテクチャ・カスタマイズ方法を説明します。

---

## 目次

1. [CPU難易度の種類](#1-cpu難易度の種類)
2. [クイックスタート — 学習を実行する](#2-クイックスタート--学習を実行する)
3. [学習の仕組み](#3-学習の仕組み)
4. [ファイル構成](#4-ファイル構成)
5. [アーキテクチャ詳細](#5-アーキテクチャ詳細)
6. [API・環境変数リファレンス](#6-api環境変数リファレンス)
7. [評価スクリプト](#7-評価スクリプト)
8. [トラブルシューティング](#8-トラブルシューティング)
9. [今後の改善候補](#9-今後の改善候補)

---

## 1. CPU難易度の種類

| 難易度 | UI表示 | 内容 |
|---|---|---|
| `easy` | 🟢 かんたん | ランダム寄り行動。攻撃しないことも多い |
| `normal` | 🟡 ふつう | 攻撃できれば攻撃・毎ターンエネルギー付与 |
| `hard` | 🔴 むずかしい | KO狙い・弱点計算・盤面評価で行動を選択 |
| `ml` | 🤖 AI（学習済み） | PPO強化学習モデルによる推論（要学習実行） |

> **注意**: `ml` を選択したときにモデルファイルが存在しない場合は自動的に `hard` にフォールバックします。

---

## 2. クイックスタート — 学習を実行する

### 事前準備

```bash
cd pokeca/backend
pip install torch stable-baselines3 gymnasium numpy
```

### 学習実行

```bash
# デフォルト設定（Phase1: 20万step + Phase2: 50万step）
python -m cpu.train

# カスタム設定
python -m cpu.train --envs 4 --phase1 200000 --phase2 500000

# 動作確認用（短時間で完走）
python -m cpu.train --envs 2 --phase1 10000 --phase2 20000
```

| オプション | デフォルト | 説明 |
|---|---|---|
| `--envs` | `4` | 並列対戦環境数。増やすと速いが RAM 消費大 |
| `--phase1` | `200000` | Phase 1 のステップ数（vs ルールベース CPU） |
| `--phase2` | `500000` | Phase 2 のステップ数（自己対戦） |
| `--output` | `cpu/models` | モデル保存ディレクトリ |

学習完了後、`cpu/models/ppo_final.zip` が生成されます。

### UI での使い方

1. フロントエンドを起動して `/game` を開く
2. デッキを選択する
3. CPU難易度で **「🤖 AI（学習済み）」** を選択
4. 「バトル開始！」をクリック

---

## 3. 学習の仕組み

### 2フェーズ学習

```
Phase 1: ルールベース CPU 相手に基礎行動を学習
  ↓
Phase 2: 自己対戦（前のスナップショットモデルと対戦）でさらに強化
  ↓
cpu/models/ppo_final.zip として保存
```

### 報酬設計

| 行動 | 報酬 |
|---|---|
| サイドカードを取る | +2.0 |
| 相手 HP を減らす | +0.5（正規化） |
| 自分がきぜつ | -1.0 |
| 無効な行動を選択 | -0.1 |
| 勝利 | +10.0 |
| 敗北 | -10.0 |

### 観測空間（128次元 float32）

| インデックス | 内容 |
|---|---|
| 0 | 経過ターン数（正規化） |
| 1 | 自分のターンか（0/1） |
| 2 | 先攻か（0/1） |
| 3–4 | 自分・相手のサイド残枚数 |
| 5–8 | 手札枚数・山札枚数（両者） |
| 16–55 | 自分の場（バトル場 + ベンチ5体のHP・エネルギー等） |
| 56–95 | 相手の場 |
| 96–125 | 手札10枚の種別（たね/エネルギー/トレーナー） |

### 行動空間（20種類）

| ID | 行動 |
|---|---|
| 0, 1 | ワザ 1・2 を使う |
| 2–11 | 手札スロット 1–10 を使う |
| 12 | にげる |
| 13–18 | ベンチポケモン 1–6 に交代 |
| 19 | ターン終了 |

---

## 4. ファイル構成

```
pokeca/backend/cpu/
├── train.py             # 学習エントリポイント（python -m cpu.train）
├── selfplay_trainer.py  # 2フェーズ学習ループ
├── ppo_agent.py         # stable-baselines3 PPO ラッパー
├── battle_env.py        # Gymnasium 環境・観測/行動エンコード
├── game_integration.py  # 推論ラッパー CPUPlayer
├── evaluate_agent.py    # 評価スクリプト（PPO vs ルールベース）
├── cpu_runtime.py       # API から呼ぶ CPU 実行窓口
├── cpu_ai.py            # ルールベース AI（EASY/NORMAL/HARD）
├── game_session.py      # セッション管理（CPU戦略を紐付けて保持）
└── models/              # 学習済みモデル保存先（.zip）
    ├── ppo_phase1.zip
    ├── ppo_selfplay_round_*.zip
    └── ppo_final.zip    ← API で使用されるモデル
```

---

## 5. アーキテクチャ詳細

### CPU 選択の流れ

```
フロントエンド（難易度選択UI）
    ↓ cpu_difficulty パラメータ
POST /api/game/cpu/start
    ↓
CpuRuntime(fixed_mode="ml" | "hard" | "normal" | "easy")
    ↓
ゲームセッションに紐付けて保持
    ↓
POST /api/game/cpu/{id}/end_turn
    ↓
セッションの CpuRuntime.play_turn(game_state)
```

### CpuRuntime 戦略切り替え

`fixed_mode` によって以下の戦略クラスが選ばれます：

| fixed_mode | 使用クラス |
|---|---|
| `easy` | `RuleBasedCpuPolicy(difficulty=EASY)` |
| `normal`（デフォルト） | `RuleBasedCpuPolicy(difficulty=NORMAL)` |
| `hard` | `EnhancedRuleBasedCpuPolicy`（HARD/NORMAL 動的切替） |
| `ml` | `PpoCpuPolicy`（モデル未存在時は `hard` へフォールバック） |

### PPO モデルの設定

```python
PPO(
    policy="MlpPolicy",
    net_arch=[256, 256],
    activation_fn=ReLU,
    learning_rate=3e-4,
    n_steps=2048,
    batch_size=64,
    n_epochs=10,
)
```

---

## 6. API・環境変数リファレンス

### ゲーム開始 API

```http
POST /api/game/cpu/start
Content-Type: application/json

{
  "player_deck_id": 1,
  "cpu_difficulty": "ml"   // "easy" | "normal" | "hard" | "ml"
}
```

### 環境変数（グローバル設定 / オプション）

UI の難易度選択が優先されますが、環境変数でサーバー全体のデフォルトを変えることもできます。

| 変数名 | デフォルト | 説明 |
|---|---|---|
| `CPU_AI_MODE` | `heuristic` | `heuristic` / `easy` / `hard` / `rule_plus` / `ppo` |
| `CPU_AI_MODEL_PATH` | *(空)* | PPO モデルの `.zip` パス |
| `CPU_RULE_PLUS_WEIGHTS` | *(空)* | rule_plus 重みの JSON 文字列 |
| `CPU_RULE_PLUS_HARD_THRESHOLD` | `2.0` | rule_plus で HARD を選ぶスコア閾値 |

rule_plus 重み設定例：

```bash
CPU_RULE_PLUS_WEIGHTS='{"side_behind":1.2,"can_attack":1.6,"opponent_low_hp":1.0,"self_low_hp_penalty":1.4}'
CPU_RULE_PLUS_HARD_THRESHOLD=2.4
```

---

## 7. 評価スクリプト

学習済みモデルがルールベース CPU にどれだけ勝てるか評価できます。

```bash
cd pokeca/backend

python -m cpu.evaluate_agent \
  --model-path cpu/models/ppo_final.zip \
  --games 50 \
  --ppo-side player2
```

| オプション | 説明 |
|---|---|
| `--model-path` | 評価するモデルの .zip パス |
| `--games` | 試合数（デフォルト: 20） |
| `--ppo-side` | PPO を `player1` か `player2` どちらで動かすか |
| `--max-turns` | 1試合の最大ターン数（デフォルト: 80） |

出力例：

```
=== PPO Evaluation Result ===
games: 50
ppo wins: 32 (64.0%)
heuristic wins: 16 (32.0%)
draws: 2
```

---

## 8. トラブルシューティング

### `ModuleNotFoundError: stable_baselines3`

ML ライブラリが未インストールです。

```bash
pip install torch stable-baselines3 gymnasium numpy
```

### `ml` を選んだのにルールベース CPU になる

`cpu/models/ppo_final.zip` が存在しないため `hard` にフォールバックしています。
先に `python -m cpu.train` を実行してモデルを生成してください。

### 学習が途中でクラッシュする

`--envs` の値を小さくしてメモリ使用量を抑えてください。

```bash
python -m cpu.train --envs 2 --phase1 100000 --phase2 200000
```

### Python バージョンエラー

Python 3.11 が必要です。3.14 など最新版では動作しません。

```bash
python3.11 -m cpu.train
```

---

## 9. 今後の改善候補

- **観測特徴量の強化**: ワザコスト達成率・進化可否・特性有無など
- **行動の細分化**: エネルギーの付与先指定・進化対象の明示
- **自己対戦プール**: 過去の複数モデルをランダム混合して対戦
- **実デッキでの学習**: DB のカードを使ったデッキで学習環境を構築
- **学習進捗の可視化**: TensorBoard によるリアルタイムグラフ
