# ポケモンカードゲーム バックエンド

FastAPI + SQLiteを使用したポケモンカード管理API

## 📁 ディレクトリ構成

```
backend/
├── __init__.py
├── main.py                      # FastAPIメインアプリケーション
├── requirements.txt             # Python依存関係
├── models/
│   ├── __init__.py
│   └── card.py                  # データモデル定義
├── database/
│   ├── __init__.py
│   ├── connection.py            # DB接続ユーティリティ
│   └── setup.py                 # DBセットアップスクリプト
├── repositories/
│   ├── __init__.py
│   └── card_repository.py       # カードデータアクセス層
└── data/
    ├── pokemon_cards.db         # SQLiteデータベース（自動生成）
    └── scraped/
        └── raw/
            └── pikachu_fixed.json  # スクレイピングデータ
```

## 🚀 セットアップ手順

### 1. 仮想環境の作成（推奨）

```bash
# プロジェクトルートで実行
python -m venv venv

# 仮想環境の有効化
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate
```

### 2. 依存関係のインストール

```bash
pip install -r backend/requirements.txt
```

### 3. データベースのセットアップ

```bash
# バックエンドディレクトリに移動
cd backend

# データベースを作成してサンプルデータをインポート
python -m database.setup
```

これにより以下が実行されます：
- `backend/data/pokemon_cards.db` が作成されます
- `pikachu_fixed.json` があればインポートされます
- なければサンプルデータ（3枚）がインポートされます

### 4. サーバーの起動

```bash
# バックエンドディレクトリで実行
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

# または
python main.py
```

サーバーが起動したら：
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- 別のドキュメント: http://localhost:8000/redoc

## 📡 APIエンドポイント

### カード一覧取得
```
GET /api/cards
```

### カード詳細取得
```
GET /api/cards/{card_id}
```

### タイプで検索
```
GET /api/cards/type/{card_type}
例: GET /api/cards/type/草
```

### 名前で検索
```
GET /api/cards/search?name={name}
例: GET /api/cards/search?name=ピカチュウ
```

### カード作成
```
POST /api/cards
Content-Type: application/json

{
  "name": "カード名",
  "image_url": "画像URL",
  "hp": 100,
  "type": "草",
  "evolution_stage": "たね",
  "attacks": [...],
  "weakness": {...},
  "resistance": null,
  "retreat_cost": 1
}
```

### カード更新
```
PUT /api/cards/{card_id}
```

### カード削除
```
DELETE /api/cards/{card_id}
```

### 統計情報
```
GET /api/stats
```

## 🔧 トラブルシューティング

### データベースをリセットしたい
```bash
# データベースファイルを削除
rm backend/data/pokemon_cards.db

# 再度セットアップ
python -m database.setup
```

### CORSエラーが出る
`main.py` の `allow_origins` にAngularの開発サーバーURLが含まれているか確認：
```python
allow_origins=[
    "http://localhost:4200",
]
```

### モジュールが見つからないエラー
プロジェクトルートから実行しているか確認：
```bash
# プロジェクトルート/backend で実行
python -m uvicorn main:app --reload
```

## 📝 開発メモ

### 新しいスクレイピングデータの追加
1. `backend/data/scraped/raw/` にJSONファイルを配置
2. `python -m database.setup` を実行してインポート

### カスタムクエリの追加
`backend/repositories/card_repository.py` に新しいメソッドを追加
→ `backend/main.py` に新しいエンドポイントを追加
