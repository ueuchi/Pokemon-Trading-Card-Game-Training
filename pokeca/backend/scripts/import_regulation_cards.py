"""
スクレイピングしたレギュレーション別カードデータをDBに登録する。

処理フロー:
  1. data/scraped/raw/regulation_{mark}_cards.json を読み込む
  2. 既存カードと名前で照合し、重複をスキップ
  3. 新規カードのみ INSERT
  4. 登録後の件数を報告

使い方:
  python import_regulation_cards.py                           # Aレギュ
  python import_regulation_cards.py --regulation B            # Bレギュ
  python import_regulation_cards.py --dry-run                 # DBを書き換えずに確認
  python import_regulation_cards.py --file path/to/cards.json # ファイル直接指定
"""

import sys
import os
import json
import sqlite3
import argparse
import re

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
DB_PATH = os.path.join(BACKEND_DIR, "data", "pokemon_cards.db")
RAW_DIR = os.path.join(BACKEND_DIR, "data", "scraped", "raw")


# ──────────────────────────────────────────────
# DB ユーティリティ
# ──────────────────────────────────────────────

def get_existing_names(conn) -> set[str]:
    rows = conn.execute("SELECT name FROM cards").fetchall()
    return {r[0] for r in rows}


def insert_card(conn, card: dict, dry_run: bool = False) -> int | None:
    """
    card: スクレイピングした辞書 → DB に INSERT する。
    returns: 新しい id (dry_run 時は None)
    """
    attacks_raw = card.get("attacks", [])
    # 正規化
    attacks_normalized = []
    for a in attacks_raw:
        if not isinstance(a, dict):
            continue
        dmg_raw = a.get("damage", 0)
        if isinstance(dmg_raw, str):
            dmg_num = re.sub(r"[^\d]", "", dmg_raw)
            dmg = int(dmg_num) if dmg_num else 0
        else:
            dmg = int(dmg_raw) if dmg_raw else 0

        attacks_normalized.append({
            "name": str(a.get("name", "")),
            "energy": a.get("energy", []),
            "energy_count": int(a.get("energy_count", len(a.get("energy", [])))),
            "damage": dmg,
            "description": str(a.get("description", "")),
            "effect_steps": [],   # convert_effects.py で後から付与
        })

    attacks_json = json.dumps(attacks_normalized, ensure_ascii=False)

    ability_raw = card.get("ability")
    ability_json = None
    if ability_raw and isinstance(ability_raw, dict):
        ability_json = json.dumps(ability_raw, ensure_ascii=False)
    elif ability_raw and isinstance(ability_raw, str):
        ability_json = ability_raw

    # カードタイプ判定
    card_type = card.get("card_type", "pokemon")
    if card_type not in ("pokemon", "trainer", "energy"):
        card_type = "pokemon"

    # ポケモンタイプ（基本 normal / supporter / item など）
    pokemon_type = "normal"
    if card_type == "trainer":
        pokemon_type = "supporter"  # スクレイパーが判定できない場合デフォルト

    # 進化段階を正規化
    evo = card.get("evolution_stage")
    if evo and isinstance(evo, str):
        evo = evo.strip()

    # 弱点
    weakness = card.get("weakness") or {}
    if isinstance(weakness, (list, tuple)):
        weakness = weakness[0] if weakness else {}
    weakness_type = card.get("weakness_type") or (weakness.get("type") if isinstance(weakness, dict) else None)
    weakness_value = card.get("weakness_value") or (weakness.get("value") if isinstance(weakness, dict) else "×2")

    # 抵抗力
    resistance = card.get("resistance") or {}
    if isinstance(resistance, (list, tuple)):
        resistance = resistance[0] if resistance else {}
    resistance_type = card.get("resistance_type") or (resistance.get("type") if isinstance(resistance, dict) else None)
    resistance_value = card.get("resistance_value") or (resistance.get("value") if isinstance(resistance, dict) else "-30")

    # HP
    hp = card.get("hp")
    if isinstance(hp, str):
        hp_num = re.sub(r"[^\d]", "", hp)
        hp = int(hp_num) if hp_num else None

    retreat_cost = card.get("retreat_cost", 0)
    if isinstance(retreat_cost, str):
        rc = re.sub(r"[^\d]", "", retreat_cost)
        retreat_cost = int(rc) if rc else 0

    params = (
        card.get("name", ""),
        card_type,
        pokemon_type,
        card.get("card_rule"),
        evo,
        card.get("evolves_from"),
        hp,
        card.get("type"),
        attacks_json,
        ability_json,
        weakness_type,
        str(weakness_value) if weakness_value is not None else None,
        resistance_type,
        str(resistance_value) if resistance_value is not None else None,
        retreat_cost,
        card.get("energy_type"),
        card.get("trainer_type"),
        1 if card.get("is_ace_spec") else 0,
        card.get("effect_description"),
        card.get("image_url"),
    )

    if dry_run:
        return None

    cursor = conn.execute("""
        INSERT INTO cards (
            name, card_type, pokemon_type, card_rule,
            evolution_stage, evolves_from, hp, type,
            attacks, ability,
            weakness_type, weakness_value,
            resistance_type, resistance_value,
            retreat_cost, energy_type,
            trainer_type, is_ace_spec, effect_description,
            image_url
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, params)
    conn.commit()
    return cursor.lastrowid


# ──────────────────────────────────────────────
# メイン
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="スクレイピング済みカードデータをDBに登録")
    parser.add_argument("--regulation", default="A", help="レギュレーションマーク (A/B/C/D/E/F/G/H)")
    parser.add_argument("--file", default=None, help="JSONファイルパスを直接指定（省略するとregulationから自動決定）")
    parser.add_argument("--dry-run", action="store_true", help="DBを書き換えずに内容確認のみ")
    parser.add_argument("--overwrite", action="store_true", help="同名カードを上書き更新（デフォルト: スキップ）")
    args = parser.parse_args()

    # JSONファイルパスを決定
    if args.file:
        json_path = args.file
    else:
        json_path = os.path.join(RAW_DIR, f"regulation_{args.regulation.upper()}_cards.json")

    if not os.path.exists(json_path):
        print(f"[ERROR] JSONファイルが見つかりません: {json_path}")
        print(f"  先に scrape_regulation_cards.py を実行してください。")
        sys.exit(1)

    with open(json_path, encoding="utf-8") as f:
        cards = json.load(f)

    print(f"読み込み完了: {len(cards)}件 ({json_path})")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    existing_names = get_existing_names(conn)
    print(f"既存DB件数: {len(existing_names)}件")

    stats = {"inserted": 0, "skipped": 0, "overwritten": 0, "invalid": 0}

    for i, card in enumerate(cards, 1):
        name = card.get("name", "").strip()
        if not name:
            print(f"  [{i}] 名前なし → スキップ")
            stats["invalid"] += 1
            continue

        if name in existing_names and not args.overwrite:
            if args.dry_run:
                print(f"  [{i}] スキップ: {name} (既存)")
            stats["skipped"] += 1
            continue

        # 既存カードの上書き処理
        if name in existing_names and args.overwrite:
            if not args.dry_run:
                row = conn.execute("SELECT id FROM cards WHERE name = ?", (name,)).fetchone()
                if row:
                    conn.execute("DELETE FROM cards WHERE id = ?", (row["id"],))
                    conn.commit()
            stats["overwritten"] += 1
            print(f"  [{i}] 上書き: {name}")
        else:
            print(f"  [{i}] 登録: {name} "
                  f"[{card.get('card_type', '?')}] "
                  f"HP:{card.get('hp', '-')} "
                  f"タイプ:{card.get('type', '-')} "
                  f"ワザ:{len(card.get('attacks', []))}個")

        new_id = insert_card(conn, card, dry_run=args.dry_run)
        if not args.dry_run:
            existing_names.add(name)
        stats["inserted"] += 1

    conn.close()

    print("\n" + "=" * 50)
    if args.dry_run:
        print("【DRY-RUN】実際のDB変更はありません")
    print(f"  新規登録: {stats['inserted']}件")
    print(f"  スキップ: {stats['skipped']}件（既存・重複）")
    if stats["overwritten"]:
        print(f"  上書き: {stats['overwritten']}件")
    if stats["invalid"]:
        print(f"  無効（名前なし等）: {stats['invalid']}件")

    if not args.dry_run:
        conn2 = sqlite3.connect(DB_PATH)
        total = conn2.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
        conn2.close()
        print(f"\n  DB総件数: {total}件")
    print("=" * 50)


if __name__ == "__main__":
    main()
