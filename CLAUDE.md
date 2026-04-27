# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 優先事項

### 対話・出力

- 対話は必ず日本語で行う
- 質問には指定がない限り短い文章で回答
- 「鋭い指摘です」などの感想や相槌を省き、結論から簡潔に回答
- 長文のエラーは内容をそのまま出力せず重要な部分のみ出力し、原因と対処法のみ簡潔に伝える

### MCP・コマンドの使い分け

- トークン消費を抑えるため `gh` コマンドと GitHub MCP を使い分ける
  - 単純な操作（PR作成・push・ステータス確認）→ `gh` コマンド
  - リッチな情報取得やコンテキストが必要な操作 → GitHub MCP

## Project Overview

ポケモンカードゲームのトレーニング用アプリ。Angular フロントエンドと FastAPI バックエンドで構成された CPU 対戦ゲーム。

## Commands

すべてのコマンドは `pokeca/` ディレクトリを起点に実行する。

### Frontend (Angular 21)

```bash
cd pokeca
npm install          # 依存関係インストール
npm start            # 開発サーバー起動 → http://localhost:4200
npm run build        # 本番ビルド
npm test             # Vitest でテスト実行
ng test --include="src/app/game/**" # 特定テスト実行
```

### Backend (FastAPI / Python 3.11)

```bash
cd pokeca/backend
pip install -r requirements.txt      # 依存関係インストール
python database/setup.py             # DB 初期化（初回のみ）
python main.py                       # API サーバー起動 → http://localhost:8000
                                     # API ドキュメント → http://localhost:8000/docs
```

### フルセットアップ

```bash
cd pokeca
bash install.sh      # フロント・バック一括セットアップ
```

## Architecture

### 全体構成

```
pokeca/
├── frontend/       # Angular 21 SPA
├── backend/        # FastAPI + SQLite
└── docs/           # 機能ドキュメント
```

### Backend

**データフロー**  
カード・デッキは SQLite (`backend/data/pokemon_cards.db`) に永続化される。  
対戦中のゲーム状態はメモリ上のみで管理され、DB には保存されない（`engine/models/game_state.py`）。

**レイヤー構成**

- `main.py` — FastAPI アプリ。カード CRUD + CORS 設定
- `api/game.py` — `/api/game/cpu/*` エンドポイント。セッション管理と各アクションのルーティング
- `api/deck.py` — `/api/decks/*` エンドポイント
- `engine/` — ゲームルールエンジン（API 非依存の純粋ロジック）
  - `models/` — `GameState`・`PlayerState`・各種 Enum
  - `actions/` — 各アクション（attack, evolve, retreat, attach_energy など）を独立ファイルで実装
  - `turn/turn_manager.py` — ターン開始・終了処理
  - `setup/game_setup.py` — ゲーム初期化・初期配置
  - `victory.py` — 勝敗判定
- `cpu/` — CPU AI
  - `cpu_ai.py` — ルールベース AI（EASY/NORMAL/HARD の 3 難易度）
  - `cpu_runtime.py` — ルールベース AI のゲームセッション統合
  - `ppo_agent.py` / `selfplay_trainer.py` — PPO 強化学習エージェント（stable-baselines3）
  - `battle_env.py` — Gymnasium 環境（RL 学習用）
- `repositories/card_repository.py` — SQLite アクセス層
- `database/connection.py` — DB 接続（`data/pokemon_cards.db` への相対パス固定）

### Frontend

**ルーティング**

- `/game` → `GameBoardComponent`（メイン対戦画面）
- `/creator` → `CardCreatorComponent`（カード作成）

**API 接続**  
`src/environments/environment.ts` で `apiUrl: 'http://localhost:8000/api/cards'` を設定。  
本番は `environment.prod.ts` で切り替える。

**主要コンポーネント**

- `game-board/` — 対戦画面全体（バックエンドゲームセッションと通信）
- `deck-builder/` — デッキ構築
- `card-creator/` — カード作成フォーム
- `card-list/`, `card-viewer/`, `card-detail/` — カード表示系

### Deploy

`render.yaml` で Render.com にデプロイ。バックエンドのみデプロイ対象（`pokeca/backend`）。  
ビルド時に `python database/setup.py` でDB初期化が走る。
