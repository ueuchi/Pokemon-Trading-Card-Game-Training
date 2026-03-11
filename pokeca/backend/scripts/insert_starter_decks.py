"""デッキのみ登録（カードは登録済み前提）"""
import json, sqlite3, os

DB = os.path.join(os.path.dirname(__file__), "..", "data", "pokemon_cards.db")

def go():
    con = sqlite3.connect(DB)
    con.execute("PRAGMA foreign_keys = ON")
    cur = con.cursor()

    # ---------- 草スターターデッキ ----------
    # Pokemon 22枚 + Trainer 16枚 + 草エネルギー 22枚 = 60枚
    cur.execute(
        "INSERT INTO decks (name, description, energies) VALUES (?,?,?)",
        ("草スターターデッキ",
         "フシギバナ/ナエトルを中心とした草タイプのスターターデッキ。進化と毒・回復で戦う",
         json.dumps({"草": 22}, ensure_ascii=False))
    )
    d1 = cur.lastrowid

    grass_cards = [
        (27, 4),  # フシギダネ
        (28, 3),  # フシギソウ
        (29, 2),  # フシギバナ
        (30, 4),  # ナエトル
        (31, 3),  # ハヤシガメ
        (32, 2),  # ドダイトス
        ( 1, 2),  # イトマル (既存)
        ( 3, 2),  # シェイミ (既存)
        (40, 4),  # 博士の研究
        (41, 3),  # マリィ
        (42, 2),  # ボスの指令
        (43, 4),  # クイックボール
        (44, 1),  # しんかのおこう
        (45, 1),  # ポケモンいれかえ
        (47, 1),  # ふしぎなアメ
    ]
    for cid, cnt in grass_cards:
        cur.execute(
            "INSERT INTO deck_cards (deck_id, card_id, count) VALUES (?,?,?)",
            (d1, cid, cnt)
        )

    # ---------- 雷スターターデッキ ----------
    # Pokemon 21枚 + Trainer 17枚 + 雷エネルギー 22枚 = 60枚
    cur.execute(
        "INSERT INTO decks (name, description, energies) VALUES (?,?,?)",
        ("雷スターターデッキ",
         "ライチュウ/ジバコイルを中核とした雷タイプのスターターデッキ。マヒ状態で相手の行動を封じる",
         json.dumps({"雷": 22}, ensure_ascii=False))
    )
    d2 = cur.lastrowid

    elec_cards = [
        (33, 4),  # ピカチュウ
        (34, 3),  # ライチュウ
        (35, 4),  # コイル
        (36, 3),  # レアコイル
        (37, 2),  # ジバコイル
        (38, 3),  # ビリリダマ
        (39, 2),  # マルマイン
        (40, 4),  # 博士の研究
        (41, 3),  # マリィ
        (42, 2),  # ボスの指令
        (43, 4),  # クイックボール
        (46, 2),  # まんたんのくすり
        (45, 2),  # ポケモンいれかえ
    ]
    for cid, cnt in elec_cards:
        cur.execute(
            "INSERT INTO deck_cards (deck_id, card_id, count) VALUES (?,?,?)",
            (d2, cid, cnt)
        )

    con.commit()

    # ---------- 結果確認 ----------
    for deck_id in [d1, d2]:
        row = con.execute("SELECT id, name, energies FROM decks WHERE id=?", (deck_id,)).fetchone()
        energies = json.loads(row[2])
        energy_total = sum(energies.values())
        card_total = con.execute(
            "SELECT SUM(count) FROM deck_cards WHERE deck_id=?", (deck_id,)
        ).fetchone()[0]
        print(f"\nデッキ[{row[0]}]: {row[1]}")
        print(f"  カード: {card_total}枚 + エネルギー: {energy_total}枚 = 合計: {card_total + energy_total}枚")
        print(f"  エネルギー: {energies}")
        for r in con.execute("""
            SELECT c.name, c.type, c.evolution_stage, dc.count
            FROM deck_cards dc JOIN cards c ON c.id=dc.card_id
            WHERE dc.deck_id=? ORDER BY c.type, c.evolution_stage
        """, (deck_id,)):
            print(f"    {r[0]:20} [{r[1] or '-':8}] {r[2] or '-':10} x{r[3]}")

    con.close()
    print("\n完了")

go()
