"""
初期デッキ作成スクリプト

実行方法: backend/ ディレクトリで
  python scripts/create_initial_deck.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import get_db_connection
from repositories.card_repository import CardRepository

CARDS = [
    {
        "name": "ピカチュウ", "card_type": "pokemon", "pokemon_type": "normal",
        "card_rule": None, "evolution_stage": "たね", "evolves_from": None,
        "hp": 70, "type": "雷",
        "attacks": [
            {"name": "でんきショック", "energy": ["雷"], "energy_count": 1, "damage": 20,
             "description": "コインを1回投げオモテなら、相手のバトルポケモンをマヒにする。"},
            {"name": "かみなり", "energy": ["雷", "雷", "無色"], "energy_count": 3, "damage": 60,
             "description": "コインを1回投げウラなら、このポケモンにも30ダメージ。"},
        ],
        "ability": None, "weakness": {"type": "闘", "value": 2},
        "resistance": None, "retreat_cost": 1, "image_url": None,
    },
    {
        "name": "ライチュウ", "card_type": "pokemon", "pokemon_type": "normal",
        "card_rule": None, "evolution_stage": "1進化", "evolves_from": "ピカチュウ",
        "hp": 100, "type": "雷",
        "attacks": [
            {"name": "エレクトロバーン", "energy": ["雷", "無色", "無色"], "energy_count": 3, "damage": 80, "description": ""},
            {"name": "サンダーボルト", "energy": ["雷", "雷", "無色", "無色"], "energy_count": 4, "damage": 120,
             "description": "このポケモンについているエネルギーをすべてトラッシュする。"},
        ],
        "ability": None, "weakness": {"type": "闘", "value": 2},
        "resistance": None, "retreat_cost": 2, "image_url": None,
    },
    {
        "name": "雷エネルギー", "card_type": "energy", "pokemon_type": None,
        "card_rule": None, "evolution_stage": None, "evolves_from": None,
        "hp": None, "type": "雷", "attacks": [], "ability": None,
        "weakness": None, "resistance": None, "retreat_cost": 0,
        "energy_type": "basic", "image_url": None,
    },
    {
        "name": "ヒトカゲ", "card_type": "pokemon", "pokemon_type": "normal",
        "card_rule": None, "evolution_stage": "たね", "evolves_from": None,
        "hp": 60, "type": "炎",
        "attacks": [
            {"name": "ひっかく", "energy": ["無色"], "energy_count": 1, "damage": 10, "description": ""},
            {"name": "かえんほうしゃ", "energy": ["炎", "炎"], "energy_count": 2, "damage": 40, "description": ""},
        ],
        "ability": None, "weakness": {"type": "水", "value": 2},
        "resistance": None, "retreat_cost": 1, "image_url": None,
    },
    {
        "name": "リザード", "card_type": "pokemon", "pokemon_type": "normal",
        "card_rule": None, "evolution_stage": "1進化", "evolves_from": "ヒトカゲ",
        "hp": 90, "type": "炎",
        "attacks": [
            {"name": "ほのおのうず", "energy": ["炎", "無色"], "energy_count": 2, "damage": 30, "description": ""},
            {"name": "フレイムテール", "energy": ["炎", "炎", "無色"], "energy_count": 3, "damage": 60, "description": ""},
        ],
        "ability": None, "weakness": {"type": "水", "value": 2},
        "resistance": None, "retreat_cost": 2, "image_url": None,
    },
    {
        "name": "リザードン", "card_type": "pokemon", "pokemon_type": "normal",
        "card_rule": None, "evolution_stage": "2進化", "evolves_from": "リザード",
        "hp": 160, "type": "炎",
        "attacks": [
            {"name": "ほのおのつばさ", "energy": ["炎", "炎", "無色"], "energy_count": 3, "damage": 90, "description": ""},
            {"name": "ごうかのうず", "energy": ["炎", "炎", "炎", "無色"], "energy_count": 4, "damage": 150,
             "description": "このポケモンについている炎エネルギーを2枚トラッシュする。"},
        ],
        "ability": {"name": "かえんのよろい", "description": "このポケモンが受けるダメージを-20する。（Phase 11で実装）"},
        "weakness": {"type": "水", "value": 2},
        "resistance": None, "retreat_cost": 3, "image_url": None,
    },
    {
        "name": "炎エネルギー", "card_type": "energy", "pokemon_type": None,
        "card_rule": None, "evolution_stage": None, "evolves_from": None,
        "hp": None, "type": "炎", "attacks": [], "ability": None,
        "weakness": None, "resistance": None, "retreat_cost": 0,
        "energy_type": "basic", "image_url": None,
    },
]

DECK_PIKACHU = {"ピカチュウ": 4, "ライチュウ": 2, "雷エネルギー": 54}
DECK_HITOKAGE = {"ヒトカゲ": 4, "リザード": 2, "リザードン": 2, "炎エネルギー": 52}


def run():
    with get_db_connection() as conn:
        repo = CardRepository(conn)
        print("============================================")
        print("🃏 初期デッキ作成スクリプト")
        print("============================================")

        card_id_map = {}
        created = skipped = 0

        for card_data in CARDS:
            existing = [c for c in repo.get_cards_by_name(card_data["name"]) if c.name == card_data["name"]]
            if existing:
                card_id_map[card_data["name"]] = existing[0].id
                print(f"  ⚠️  スキップ (既存): {card_data['name']} (ID: {existing[0].id})")
                skipped += 1
            else:
                card_id = repo.create_card(card_data)
                card_id_map[card_data["name"]] = card_id
                print(f"  ✅ 作成: {card_data['name']} (ID: {card_id})")
                created += 1

        print(f"\n📦 カード: 作成 {created} 枚 / スキップ {skipped} 枚")
        _create_deck(conn, "ピカチュウデッキ（雷）", DECK_PIKACHU, card_id_map)
        _create_deck(conn, "リザードンデッキ（炎）", DECK_HITOKAGE, card_id_map)
        print("\n============================================")
        print("✅ 完了！デッキが作成されました")
        print("============================================")


def _create_deck(conn, deck_name, deck_config, card_id_map):
    if conn.execute("SELECT id FROM decks WHERE name = ?", (deck_name,)).fetchone():
        print(f"\n  ⚠️  デッキ既存: {deck_name} (スキップ)")
        return
    cursor = conn.execute("INSERT INTO decks (name) VALUES (?)", (deck_name,))
    deck_id = cursor.lastrowid
    conn.commit()
    for card_name, quantity in deck_config.items():
        card_id = card_id_map.get(card_name)
        if card_id:
            conn.execute(
                "INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (?, ?, ?)",
                (deck_id, card_id, quantity)
            )
    conn.commit()
    total = sum(deck_config.values())
    print(f"\n  ✅ デッキ作成: {deck_name} ({total}枚) ID: {deck_id}")
    for n, q in deck_config.items():
        print(f"     {n} × {q}")


if __name__ == "__main__":
    run()
