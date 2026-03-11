"""
スクレイピングしたエネルギーカードをDBに登録するスクリプト
各エネルギータイプ（草/炎/水/雷/超/闘/悪/鋼）ごとに代表1枚をcardsテーブルに登録する。
重複登録を防ぐためtype列でチェックする。
"""
import json
import sqlite3
import sys
import os

# プロジェクトルートからの相対パス
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
DB_PATH = os.path.join(BACKEND_DIR, "data", "pokemon_cards.db")
JSON_PATH = os.path.join(BACKEND_DIR, "data", "scraped", "raw", "energy_cards.json")
STATIC_BASE = "http://localhost:8000/static"

# エネルギー名 → タイプ のマッピング
NAME_TO_TYPE = {
    "基本草エネルギー": "草",
    "基本炎エネルギー": "炎",
    "基本水エネルギー": "水",
    "基本雷エネルギー": "雷",
    "基本超エネルギー": "超",
    "基本闘エネルギー": "闘",
    "基本悪エネルギー": "悪",
    "基本鋼エネルギー": "鋼",
}


def local_path_to_url(local_path: str) -> str:
    """
    "data/scraped/processed/energy/0001_基本草エネルギー.jpg"
    → "http://localhost:8000/static/scraped/processed/energy/0001_基本草エネルギー.jpg"
    """
    # local_path は "data/..." で始まるので data/ を除去
    relative = local_path.removeprefix("data/")
    return f"{STATIC_BASE}/{relative}"


def main(dry_run: bool = False):
    # JSONを読み込む
    with open(JSON_PATH, encoding="utf-8") as f:
        cards_data = json.load(f)

    # タイプごとに最初の1枚だけ選ぶ
    representative: dict[str, dict] = {}
    for card in cards_data:
        name = card.get("name", "")
        energy_type = NAME_TO_TYPE.get(name)
        if energy_type and energy_type not in representative:
            representative[energy_type] = card

    print(f"代表カード: {list(representative.keys())}")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    inserted = 0
    skipped = 0

    for energy_type, card in representative.items():
        # 既存チェック（card_type='energy' かつ type が一致）
        existing = conn.execute(
            "SELECT id FROM cards WHERE card_type='energy' AND type=?",
            (energy_type,)
        ).fetchone()

        if existing:
            print(f"  スキップ（既存）: {energy_type}エネルギー (id={existing['id']})")
            skipped += 1
            continue

        image_url = local_path_to_url(card["local_path"]) if card.get("local_path") else card.get("image_url", "")
        card_name = card["name"]

        if dry_run:
            print(f"  [DRY-RUN] 登録予定: {card_name} / type={energy_type} / image={image_url}")
        else:
            conn.execute(
                """
                INSERT INTO cards (name, card_type, energy_type, type, image_url)
                VALUES (?, 'energy', 'basic', ?, ?)
                """,
                (card_name, energy_type, image_url),
            )
            print(f"  登録: {card_name} / type={energy_type}")
            inserted += 1

    if not dry_run:
        conn.commit()
        print(f"\n完了: {inserted}件登録, {skipped}件スキップ")
    else:
        print(f"\n[DRY-RUN] {len(representative) - skipped}件登録予定, {skipped}件スキップ予定")

    conn.close()


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    main(dry_run=dry)
