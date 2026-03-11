"""
スターターデッキ作成スクリプト

草タイプと雷タイプのスターターデッキを2種類登録します。
"""
import json
import sqlite3
import sys
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "pokemon_cards.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ==============================================================
# 新規カードデータ定義
# ==============================================================

NEW_POKEMON_GRASS = [
    {
        "name": "フシギダネ",
        "hp": 70, "type": "草", "evolution_stage": "たね",
        "weakness_type": "炎", "weakness_value": "×2",
        "retreat_cost": 1,
        "attacks": json.dumps([
            {"name": "はっぱカッター", "energy": ["草"], "energy_count": 1,
             "damage": 30, "description": ""},
            {"name": "タネばくだん", "energy": ["草", "草"], "energy_count": 2,
             "damage": 50, "description": "相手のベンチポケモン1体に20ダメージ。"},
        ]),
    },
    {
        "name": "フシギソウ",
        "hp": 90, "type": "草", "evolution_stage": "1 進化",
        "weakness_type": "炎", "weakness_value": "×2",
        "retreat_cost": 2,
        "attacks": json.dumps([
            {"name": "なぎはらう", "energy": ["草"], "energy_count": 1,
             "damage": 40, "description": ""},
            {"name": "どくのはな", "energy": ["草", "草"], "energy_count": 2,
             "damage": 70, "description": "相手のバトルポケモンをどくにする。"},
        ]),
    },
    {
        "name": "フシギバナ",
        "hp": 160, "type": "草", "evolution_stage": "2 進化",
        "weakness_type": "炎", "weakness_value": "×2",
        "retreat_cost": 3,
        "attacks": json.dumps([
            {"name": "フラワーストーム", "energy": ["草", "草"], "energy_count": 2,
             "damage": 100, "description": "自分のベンチポケモン全員のHPを30回復する。"},
            {"name": "ソーラービーム", "energy": ["草", "草", "草"], "energy_count": 3,
             "damage": 160, "description": ""},
        ]),
    },
    {
        "name": "ナエトル",
        "hp": 60, "type": "草", "evolution_stage": "たね",
        "weakness_type": "炎", "weakness_value": "×2",
        "retreat_cost": 1,
        "attacks": json.dumps([
            {"name": "たいあたり", "energy": ["無"], "energy_count": 1,
             "damage": 10, "description": ""},
            {"name": "はっぱカッター", "energy": ["草"], "energy_count": 1,
             "damage": 30, "description": ""},
        ]),
    },
    {
        "name": "ハヤシガメ",
        "hp": 90, "type": "草", "evolution_stage": "1 進化",
        "weakness_type": "炎", "weakness_value": "×2",
        "retreat_cost": 2,
        "attacks": json.dumps([
            {"name": "シェルのまもり", "energy": ["草"], "energy_count": 1,
             "damage": 20, "description": "次の相手の番、このポケモンが受けるワザのダメージを-30する。"},
            {"name": "エナジーハンマー", "energy": ["草", "草"], "energy_count": 2,
             "damage": 80, "description": ""},
        ]),
    },
    {
        "name": "ドダイトス",
        "hp": 170, "type": "草", "evolution_stage": "2 進化",
        "weakness_type": "炎", "weakness_value": "×2",
        "retreat_cost": 4,
        "attacks": json.dumps([
            {"name": "リーフストーム", "energy": ["草", "草"], "energy_count": 2,
             "damage": 120, "description": "自分の草ポケモン全員のHPを20回復する。"},
            {"name": "だいちのつき", "energy": ["草", "草", "草"], "energy_count": 3,
             "damage": 180, "description": "次の自分の番、このポケモンはワザが使えない。"},
        ]),
    },
]

NEW_POKEMON_ELECTRIC = [
    {
        "name": "ピカチュウ",
        "hp": 60, "type": "雷", "evolution_stage": "たね",
        "weakness_type": "闘", "weakness_value": "×2",
        "retreat_cost": 1,
        "attacks": json.dumps([
            {"name": "でんきショック", "energy": ["雷"], "energy_count": 1,
             "damage": 20, "description": "コインを1回投げオモテなら、相手のバトルポケモンをマヒにする。"},
            {"name": "かみなり", "energy": ["雷", "雷"], "energy_count": 2,
             "damage": 50, "description": "コインを1回投げウラなら、自分のバトルポケモンにも20ダメージ。"},
        ]),
    },
    {
        "name": "ライチュウ",
        "hp": 120, "type": "雷", "evolution_stage": "1 進化",
        "weakness_type": "闘", "weakness_value": "×2",
        "retreat_cost": 1,
        "attacks": json.dumps([
            {"name": "サンダーパンチ", "energy": ["雷", "無"], "energy_count": 2,
             "damage": 60, "description": "コインを1回投げオモテなら、相手のバトルポケモンをマヒにする。"},
            {"name": "　じゅうまんボルト", "energy": ["雷", "雷", "無"], "energy_count": 3,
             "damage": 130, "description": "次の自分の番、このポケモンはワザが使えない。"},
        ]),
    },
    {
        "name": "コイル",
        "hp": 50, "type": "雷", "evolution_stage": "たね",
        "weakness_type": "闘", "weakness_value": "×2",
        "retreat_cost": 1,
        "attacks": json.dumps([
            {"name": "でんじは", "energy": ["雷"], "energy_count": 1,
             "damage": 10, "description": "相手のバトルポケモンをマヒにする。"},
            {"name": "ほうでん", "energy": ["雷", "雷"], "energy_count": 2,
             "damage": 30, "description": "相手のベンチポケモン1体に10ダメージ。"},
        ]),
    },
    {
        "name": "レアコイル",
        "hp": 90, "type": "雷", "evolution_stage": "1 進化",
        "weakness_type": "闘", "weakness_value": "×2",
        "retreat_cost": 2,
        "attacks": json.dumps([
            {"name": "マグネットボム", "energy": ["雷", "無"], "energy_count": 2,
             "damage": 60, "description": "次の相手の番、このワザを受けたポケモンは逃げられない。"},
            {"name": "サンダーウェーブ", "energy": ["雷", "雷"], "energy_count": 2,
             "damage": 80, "description": "コインを1回投げオモテなら相手のバトルポケモンをマヒにする。"},
        ]),
    },
    {
        "name": "ジバコイル",
        "hp": 130, "type": "雷", "evolution_stage": "2 進化",
        "weakness_type": "闘", "weakness_value": "×2",
        "retreat_cost": 3,
        "attacks": json.dumps([
            {"name": "フラッシュキャノン", "energy": ["雷", "雷", "無"], "energy_count": 3,
             "damage": 130, "description": "自分の雷エネルギーを全てトラッシュする。"},
            {"name": "マグネットコイル", "energy": ["雷", "雷", "雷"], "energy_count": 3,
             "damage": 160, "description": ""},
        ]),
    },
    {
        "name": "ビリリダマ",
        "hp": 60, "type": "雷", "evolution_stage": "たね",
        "weakness_type": "闘", "weakness_value": "×2",
        "retreat_cost": 1,
        "attacks": json.dumps([
            {"name": "たいあたり", "energy": ["無"], "energy_count": 1,
             "damage": 10, "description": ""},
            {"name": "バチバチ", "energy": ["雷", "無"], "energy_count": 2,
             "damage": 40, "description": "コインを1回投げオモテなら相手のバトルポケモンをマヒにする。"},
        ]),
    },
    {
        "name": "マルマイン",
        "hp": 80, "type": "雷", "evolution_stage": "1 進化",
        "weakness_type": "闘", "weakness_value": "×2",
        "retreat_cost": 0,
        "attacks": json.dumps([
            {"name": "でんじほう", "energy": ["雷"], "energy_count": 1,
             "damage": 50, "description": "コインを1回投げウラなら自分のバトルポケモンをマヒにする。"},
            {"name": "ばくはつ", "energy": ["雷", "雷", "無"], "energy_count": 3,
             "damage": 200, "description": "このポケモンはきぜつする。"},
        ]),
    },
]

TRAINERS = [
    {
        "name": "博士の研究",
        "hp": None, "type": "サポート", "evolution_stage": None,
        "trainer_type": "サポート",
        "effect_description": "自分の手札を全てトラッシュする。その後、山札を7枚引く。",
        "attacks": json.dumps([]),
    },
    {
        "name": "マリィ",
        "hp": None, "type": "サポート", "evolution_stage": None,
        "trainer_type": "サポート",
        "effect_description": "自分の手札を山札に戻し、山札を切る。その後、山札を5枚引く。相手の手札を山札に戻し、山札を切る。その後、相手は山札を3枚引く。",
        "attacks": json.dumps([]),
    },
    {
        "name": "ボスの指令",
        "hp": None, "type": "サポート", "evolution_stage": None,
        "trainer_type": "サポート",
        "effect_description": "相手のベンチポケモンを1体選ぶ。相手はそのポケモンをバトル場に出す。",
        "attacks": json.dumps([]),
    },
    {
        "name": "クイックボール",
        "hp": None, "type": "グッズ", "evolution_stage": None,
        "trainer_type": "グッズ",
        "effect_description": "手札を1枚トラッシュする。自分の山札からたねポケモンを1枚選び、手札に加える。そして山札を切る。",
        "attacks": json.dumps([]),
    },
    {
        "name": "しんかのおこう",
        "hp": None, "type": "グッズ", "evolution_stage": None,
        "trainer_type": "グッズ",
        "effect_description": "自分の山札から進化ポケモンを1枚選び、手札に加える。そして山札を切る。",
        "attacks": json.dumps([]),
    },
    {
        "name": "ポケモンいれかえ",
        "hp": None, "type": "グッズ", "evolution_stage": None,
        "trainer_type": "グッズ",
        "effect_description": "自分のバトルポケモンをベンチポケモンと入れ替える。",
        "attacks": json.dumps([]),
    },
    {
        "name": "まんたんのくすり",
        "hp": None, "type": "グッズ", "evolution_stage": None,
        "trainer_type": "グッズ",
        "effect_description": "自分のポケモン1体のHPを120回復する。",
        "attacks": json.dumps([]),
    },
    {
        "name": "ふしぎなアメ",
        "hp": None, "type": "グッズ", "evolution_stage": None,
        "trainer_type": "グッズ",
        "effect_description": "自分のバトル場かベンチの「たね」のポケモンの上に、そのポケモンの「2進化」ポケモンを直接のせて進化させる。",
        "attacks": json.dumps([]),
    },
]


def insert_cards(conn, cards_data: list) -> dict:
    """カードを挿入してname→idのマッピングを返す（既存カードはスキップ）"""
    name_to_id = {}
    cursor = conn.cursor()
    for card in cards_data:
        # 既に同名カードが存在する場合はスキップ
        existing = conn.execute(
            "SELECT id FROM cards WHERE name = ?", (card["name"],)
        ).fetchone()
        if existing:
            name_to_id[card["name"]] = existing["id"]
            print(f"  既存: {card['name']} (id={existing['id']})")
            continue

        trainer_type = card.get("trainer_type")
        effect_description = card.get("effect_description")
        # card_type を適切に設定
        card_type = "trainer" if trainer_type else "pokemon"
        cursor.execute("""
            INSERT INTO cards
                (name, card_type, hp, type, evolution_stage,
                 weakness_type, weakness_value, retreat_cost, attacks,
                 trainer_type, effect_description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            card["name"],
            card_type,
            card.get("hp"),
            card.get("type"),
            card.get("evolution_stage"),
            card.get("weakness_type"),
            card.get("weakness_value"),
            card.get("retreat_cost"),
            card.get("attacks", "[]"),
            trainer_type,
            effect_description,
        ))
        name_to_id[card["name"]] = cursor.lastrowid
        print(f"  登録: {card['name']} (id={cursor.lastrowid})")
    conn.commit()
    return name_to_id


def create_deck(conn, name: str, description: str,
                cards_list: list[tuple], energies: dict) -> int:
    """
    デッキを作成して登録する。
    cards_list: [(card_id, count), ...]
    energies:   {"草": 20} など
    バリデーション: 合計60枚チェック
    """
    total = sum(c for _, c in cards_list) + sum(energies.values())
    assert total == 60, f"合計が60枚ではありません: {total}枚"
    assert all(c <= 4 for _, c in cards_list), "同名4枚制限違反"

    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO decks (name, description, energies) VALUES (?, ?, ?)",
        (name, description, json.dumps(energies, ensure_ascii=False))
    )
    deck_id = cursor.lastrowid

    for card_id, count in cards_list:
        cursor.execute(
            "INSERT INTO deck_cards (deck_id, card_id, count) VALUES (?, ?, ?)",
            (deck_id, card_id, count)
        )

    conn.commit()
    print(f"\n  デッキ登録完了: 「{name}」(id={deck_id}) 合計{total}枚")
    return deck_id


def main():
    conn = get_conn()

    # ===== 1. カード挿入 =====
    print("=== 草タイプポケモン登録 ===")
    grass_ids = insert_cards(conn, NEW_POKEMON_GRASS)

    print("\n=== 雷タイプポケモン登録 ===")
    elec_ids = insert_cards(conn, NEW_POKEMON_ELECTRIC)

    print("\n=== トレーナーカード登録 ===")
    trainer_ids = insert_cards(conn, TRAINERS)

    # 既存カードのIDを名前で検索
    existing = {row["name"]: row["id"]
                for row in conn.execute("SELECT id, name FROM cards WHERE name IN ('イトマル', 'シェイミ')")}
    if "イトマル" not in existing or "シェイミ" not in existing:
        print("WARNING: イトマル or シェイミ が見つかりません。草デッキのたねポケモンで代用します。")

    # --- 古い壊れたスターターデッキを削除 ---
    old_decks = conn.execute(
        "SELECT id FROM decks WHERE name IN ('草スターターデッキ', '雷スターターデッキ')"
    ).fetchall()
    for od in old_decks:
        conn.execute("DELETE FROM deck_cards WHERE deck_id = ?", (od["id"],))
        conn.execute("DELETE FROM decks WHERE id = ?", (od["id"],))
        print(f"  旧デッキ削除: id={od['id']}")
    conn.commit()

    # ===== 2. 草スターターデッキ =====
    print("\n=== 草スターターデッキ 作成 ===")
    # ポケモン 22枚
    # フシギダネ x4, フシギソウ x3, フシギバナ x2
    # ナエトル x4, ハヤシガメ x3, ドダイトス x2
    # イトマル x2, シェイミ x2 (既存)
    # トレーナー 16枚: 博士の研究 x4, マリィ x3, ボスの指令 x2, クイックボール x4
    #                   しんかのおこう x1, ポケモンいれかえ x1, ふしぎなアメ x1
    # 草エネルギー 22枚
    grass_deck_cards = [
        (grass_ids["フシギダネ"],    4),
        (grass_ids["フシギソウ"],   3),
        (grass_ids["フシギバナ"],   2),
        (grass_ids["ナエトル"],     4),
        (grass_ids["ハヤシガメ"],   3),
        (grass_ids["ドダイトス"],   2),
        (existing.get("イトマル", grass_ids["フシギダネ"]), 2),
        (existing.get("シェイミ", grass_ids["ナエトル"]), 2),
        (trainer_ids["博士の研究"],  4),
        (trainer_ids["マリィ"],      3),
        (trainer_ids["ボスの指令"],  2),
        (trainer_ids["クイックボール"], 4),
        (trainer_ids["しんかのおこう"], 1),
        (trainer_ids["ポケモンいれかえ"], 1),
        (trainer_ids["ふしぎなアメ"],  1),
    ]
    create_deck(
        conn,
        name="草スターターデッキ",
        description="フシギバナ・ナエトルを中心とした草タイプのスターターデッキ。進化ラインを育て毒状態や回復で戦う",
        cards_list=grass_deck_cards,
        energies={"草": 22},
    )

    # ===== 3. 雷スターターデッキ =====
    print("\n=== 雷スターターデッキ 作成 ===")
    # ポケモン 21枚
    # ピカチュウ x4, ライチュウ x3
    # コイル x4, レアコイル x3, ジバコイル x2
    # ビリリダマ x3, マルマイン x2
    # トレーナー 17枚: 博士の研究 x4, マリィ x3, ボスの指令 x2, クイックボール x4
    #                   まんたんのくすり x2, ポケモンいれかえ x2
    # 雷エネルギー 22枚
    elec_deck_cards = [
        (elec_ids["ピカチュウ"],   4),
        (elec_ids["ライチュウ"],   3),
        (elec_ids["コイル"],       4),
        (elec_ids["レアコイル"],   3),
        (elec_ids["ジバコイル"],   2),
        (elec_ids["ビリリダマ"],   3),
        (elec_ids["マルマイン"],   2),
        (trainer_ids["博士の研究"],  4),
        (trainer_ids["マリィ"],      3),
        (trainer_ids["ボスの指令"],  2),
        (trainer_ids["クイックボール"], 4),
        (trainer_ids["まんたんのくすり"], 2),
        (trainer_ids["ポケモンいれかえ"], 2),
    ]
    create_deck(
        conn,
        name="雷スターターデッキ",
        description="ライチュウ・ジバコイルを中核とした雷タイプのスターターデッキ。マヒ状態を活かし相手の動きを封じる",
        cards_list=elec_deck_cards,
        energies={"雷": 22},
    )

    # ===== 4. 結果表示 =====
    print("\n=== 登録完了サマリ ===")
    decks = conn.execute("SELECT id, name, description, energies FROM decks ORDER BY id").fetchall()
    for deck in decks:
        total_cards = conn.execute(
            "SELECT SUM(count) FROM deck_cards WHERE deck_id = ?", (deck["id"],)
        ).fetchone()[0] or 0
        energies = json.loads(deck["energies"])
        energy_total = sum(energies.values())
        print(f"\nデッキ[{deck['id']}]: {deck['name']}")
        print(f"  説明: {deck['description']}")
        print(f"  カード(Pokemon/Trainer): {total_cards}枚 + エネルギー: {energy_total}枚 = 合計: {total_cards + energy_total}枚")
        print(f"  エネルギー内訳: {energies}")
        rows = conn.execute("""
            SELECT c.name, c.type, c.evolution_stage, dc.count
            FROM deck_cards dc JOIN cards c ON c.id = dc.card_id
            WHERE dc.deck_id = ? ORDER BY c.type, c.evolution_stage, c.name
        """, (deck["id"],)).fetchall()
        for r in rows:
            print(f"    {r['name']:20} {r['type'] or 'ー':8} {r['evolution_stage'] or 'ー':8} x{r['count']}")

    conn.close()


if __name__ == "__main__":
    main()
