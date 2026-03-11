"""
DBセットアップ＋スクレイピング済み画像データ一括インポートスクリプト
card_repository.py のスキーマに合わせたテーブルを作成し、
各JSONファイルからカードをインポートする。

実行方法（backendディレクトリから）:
    python3 scripts/setup_db_with_images.py
"""
import json
import os
import sqlite3
from pathlib import Path

# -------------------------------------------------------------------
# 設定
# -------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
DB_PATH = BASE_DIR / "data" / "pokemon_cards.db"

# ローカル画像のベースURL（バックエンドが /static/ で data/ を配信）
STATIC_BASE_URL = "http://localhost:8000/static"

# インポートするJSONファイル（パス, カード種別）
JSON_SOURCES = [
    # エネルギーカード（ローカル画像あり）
    (BASE_DIR / "data" / "scraped" / "raw" / "energy_cards.json", "energy"),
    # ポケモンカード詳細（外部URL）
    (BASE_DIR / "backend" / "data" / "scraped" / "raw" / "pikachu_fixed.json", "pokemon"),
    # ピカチュウカード一覧（外部URL、詳細なし）
    (BASE_DIR / "scripts" / "scraping" / "backend" / "data" / "scraped" / "raw" / "pikachu_cards.json", "pokemon"),
]


# -------------------------------------------------------------------
# DB作成
# -------------------------------------------------------------------
def create_tables(conn: sqlite3.Connection) -> None:
    """card_repository.py の row_to_card() が期待するスキーマを作成"""
    conn.executescript("""
        DROP TABLE IF EXISTS cards;

        CREATE TABLE cards (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            name             TEXT    NOT NULL,
            card_type        TEXT    DEFAULT 'pokemon',
            pokemon_type     TEXT    DEFAULT 'normal',
            card_rule        TEXT,
            evolution_stage  TEXT,
            evolves_from     TEXT,
            hp               INTEGER,
            type             TEXT,
            attacks          TEXT,
            ability          TEXT,
            weakness_type    TEXT,
            weakness_value   TEXT,
            resistance_type  TEXT,
            resistance_value TEXT,
            retreat_cost     INTEGER DEFAULT 0,
            energy_type      TEXT,
            trainer_type     TEXT,
            is_ace_spec      INTEGER DEFAULT 0,
            effect_description TEXT,
            image_url        TEXT,
            created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_cards_name      ON cards(name);
        CREATE INDEX IF NOT EXISTS idx_cards_type      ON cards(type);
        CREATE INDEX IF NOT EXISTS idx_cards_card_type ON cards(card_type);
    """)
    conn.commit()
    print("✅ テーブル作成完了")


# -------------------------------------------------------------------
# ローカル画像パス → URL 変換
# -------------------------------------------------------------------
def local_path_to_url(local_path: str) -> str | None:
    """
    'data/scraped/processed/energy/xxx.jpg'
       → 'http://localhost:8000/static/scraped/processed/energy/xxx.jpg'
    """
    if not local_path:
        return None
    # 先頭の "data/" を取り除いて /static/ にマッピング
    normalized = local_path.replace("\\", "/")
    if normalized.startswith("data/"):
        normalized = normalized[len("data/"):]
    full_path = BASE_DIR / "data" / normalized
    if full_path.exists():
        return f"{STATIC_BASE_URL}/{normalized}"
    return None  # ファイルが存在しなければ None


# -------------------------------------------------------------------
# エネルギーカードのインポート
# -------------------------------------------------------------------
ENERGY_TYPE_MAP = {
    "草": "grass", "炎": "fire", "水": "water",
    "雷": "lightning", "超": "psychic", "闘": "fighting",
    "悪": "darkness", "鋼": "metal", "ドラゴン": "dragon",
    "フェアリー": "fairy", "無色": "colorless",
}

def detect_energy_jp_type(name: str) -> str | None:
    """カード名からタイプを推測"""
    for jp in ENERGY_TYPE_MAP:
        if jp in name:
            return jp
    return None


def import_energy_cards(conn: sqlite3.Connection, json_path: Path) -> int:
    with open(json_path, encoding="utf-8") as f:
        cards = json.load(f)

    imported = 0
    seen_names: set[str] = set()

    for card in cards:
        name = card.get("name", "").strip()
        if not name or name in seen_names:
            continue
        seen_names.add(name)

        # 画像URL: ローカルを優先、なければ外部URL
        image_url = (
            local_path_to_url(card.get("local_path", ""))
            or card.get("image_url")
        )

        energy_jp = detect_energy_jp_type(name)

        conn.execute(
            """
            INSERT INTO cards
              (name, card_type, energy_type, image_url)
            VALUES (?, 'energy', ?, ?)
            """,
            (name, energy_jp, image_url),
        )
        imported += 1

    conn.commit()
    return imported


# -------------------------------------------------------------------
# ポケモンカード詳細付き（pikachu_fixed.json フォーマット）
# -------------------------------------------------------------------
def import_pokemon_detailed(conn: sqlite3.Connection, json_path: Path) -> int:
    with open(json_path, encoding="utf-8") as f:
        cards = json.load(f)

    imported = 0
    for card in cards:
        name = card.get("name", "").strip()
        if not name:
            continue

        # weakness: string型（タイプのみ）
        weakness = card.get("weakness")
        weakness_type = None
        if isinstance(weakness, str):
            weakness_type = weakness or None
        elif isinstance(weakness, list) and weakness:  # 旧フォーマット互換
            weakness_type = weakness[0]
        elif isinstance(weakness, dict):               # 旧フォーマット互換
            weakness_type = weakness.get("type")
        weakness_value = None  # 不使用（typeのみ保持）

        # resistance
        resistance = card.get("resistance")
        resistance_type = resistance_value = None
        if isinstance(resistance, list) and resistance:
            resistance_type = resistance[0]
            resistance_value = "-30"
        elif isinstance(resistance, dict):
            resistance_type = resistance.get("type")
            resistance_value = resistance.get("value", "-30")

        # attacks
        attacks_raw = card.get("attacks", [])
        attacks_json = json.dumps(attacks_raw, ensure_ascii=False)

        conn.execute(
            """
            INSERT INTO cards
              (name, card_type, evolution_stage, hp, type,
               attacks, weakness_type, weakness_value,
               resistance_type, resistance_value,
               retreat_cost, image_url)
            VALUES (?, 'pokemon', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                card.get("evolution_stage"),
                card.get("hp"),
                card.get("type"),
                attacks_json,
                weakness_type, weakness_value,
                resistance_type, resistance_value,
                card.get("retreat_cost", 0),
                card.get("image_url"),
            ),
        )
        imported += 1

    conn.commit()
    return imported


# -------------------------------------------------------------------
# ポケモンカード一覧のみ（pikachu_cards.json フォーマット）
# -------------------------------------------------------------------
def import_pokemon_list(conn: sqlite3.Connection, json_path: Path) -> int:
    with open(json_path, encoding="utf-8") as f:
        cards = json.load(f)

    # 既存の名前を取得（重複回避）
    existing = {row[0] for row in conn.execute("SELECT name FROM cards")}

    imported = 0
    for card in cards:
        name = card.get("name", "").strip()
        if not name or name in existing:
            continue
        existing.add(name)

        conn.execute(
            """
            INSERT INTO cards (name, card_type, image_url)
            VALUES (?, 'pokemon', ?)
            """,
            (name, card.get("image_url")),
        )
        imported += 1

    conn.commit()
    return imported


# -------------------------------------------------------------------
# メイン
# -------------------------------------------------------------------
def main() -> None:
    print("=" * 60)
    print("ポケモンカード DB セットアップ（画像URL付き）")
    print("=" * 60)

    # DB ディレクトリ作成
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # テーブル作成（DROP & CREATE）
    print("\n[1/2] テーブルを作成中...")
    create_tables(conn)

    # データインポート
    print("\n[2/2] カードデータをインポート中...")
    total = 0

    for json_path, card_type in JSON_SOURCES:
        if not json_path.exists():
            print(f"  ⚠️  ファイルなし: {json_path.relative_to(BASE_DIR)}")
            continue

        print(f"  📥 {json_path.relative_to(BASE_DIR)}")

        if card_type == "energy":
            count = import_energy_cards(conn, json_path)
        else:
            # 詳細ありかどうかを判断（attacks フィールドの有無）
            with open(json_path, encoding="utf-8") as f:
                sample = json.load(f)
            if sample and "attacks" in sample[0]:
                count = import_pokemon_detailed(conn, json_path)
            else:
                count = import_pokemon_list(conn, json_path)

        print(f"     → {count} 件インポート")
        total += count

    # サマリー
    cur = conn.execute("SELECT card_type, COUNT(*) FROM cards GROUP BY card_type")
    print("\n" + "=" * 60)
    print(f"✅ 合計 {total} 件インポート完了")
    for row in cur.fetchall():
        print(f"   {row[0]:10s}: {row[1]} 件")

    # image_url が設定されているカード数
    cur2 = conn.execute("SELECT COUNT(*) FROM cards WHERE image_url IS NOT NULL")
    print(f"   画像URL設定済み: {cur2.fetchone()[0]} 件")
    print(f"   DB: {DB_PATH}")
    print("=" * 60)

    conn.close()


if __name__ == "__main__":
    main()
