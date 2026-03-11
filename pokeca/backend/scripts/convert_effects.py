"""
DBのcardsテーブルにあるワザの description テキストを解析し、
effect_steps JSON を生成してDBを更新するスクリプト。

処理フロー:
  1. DBからポケモンカードの attacks JSON を全件読み込み
  2. 各ワザの description に対してパターンマッチングを実行
  3. AtomicEffectType に基づく effect_steps を生成
  4. DB の attacks カラムを更新

使い方:
  python convert_effects.py             # DBを実際に更新
  python convert_effects.py --dry-run   # 変換結果を表示するだけ（DB更新なし）
  python convert_effects.py --show-unmatched  # 変換できなかった効果テキスト一覧を表示

AtomicEffectType (engine/models/game_enums.py) との対応:
  bench_damage / self_damage / extra_damage / damage_reduce
  poison / burn / paralysis / sleep / confusion / cant_retreat
  heal_self / heal_bench
  draw / discard_hand / search_pokemon / search_energy
  attach_energy / discard_energy
  cant_attack
  coin_flip
  custom
"""
import sys
import os
import json
import re
import sqlite3

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)   # backend/scripts/ → backend/
DB_PATH = os.path.join(BACKEND_DIR, "data", "pokemon_cards.db")


# ============================================================
# パターンルール定義
# 優先順位順（上から評価し、最初にマッチしたルールを採用）
# ============================================================

def _num(text: str, default: int = 0) -> int:
    """テキストから最初の数値を抽出する"""
    m = re.search(r"\d+", text)
    return int(m.group()) if m else default


def parse_description(description: str) -> list[dict]:
    """
    ワザの効果テキストを解析して effect_steps リストを返す。

    Args:
        description: 公式テキスト（日本語）

    Returns:
        [{"type": str, "params": dict}, ...]
    """
    if not description or not description.strip():
        return []

    steps = []
    remaining = description.strip()

    # --- コインフリップを先に処理（複合効果の外枠になることが多い） ---
    # 例: 「コインを1枚投げオモテなら〜マヒ。ウラなら自分に20ダメージ。」
    coin_pattern = re.compile(
        r"コインを\d+[枚回]投げ[、。\s]*"
        r"(?:"
        r"(?:オモテなら[、]?(.+?)(?:[。]|ウラなら|$))"   # オモテなら〜
        r"(?:ウラなら[、]?(.+?)(?:[。]|$))?"              # ウラなら〜（省略可）
        r"|"
        r"(?:ウラなら[、]?(.+?)(?:[。]|$))"              # ウラなら〜のみ
        r")",
        re.DOTALL,
    )
    coin_match = coin_pattern.search(remaining)
    if coin_match:
        heads_text = (coin_match.group(1) or "").strip()
        # group(2)=オモテあり時のウラ、group(3)=ウラのみパターン
        tails_text = (coin_match.group(2) or coin_match.group(3) or "").strip()

        on_heads = _single_effect(heads_text) if heads_text else None
        on_tails = _single_effect(tails_text) if tails_text else None

        steps.append({
            "type": "coin_flip",
            "params": {
                "on_heads": on_heads,
                "on_tails": on_tails,
            },
        })
        # コインフリップ部分を除去して残りを処理
        remaining = remaining[:coin_match.start()] + remaining[coin_match.end():]
        remaining = remaining.strip()

    # --- 残りのテキストを文ごとに分割してパース ---
    sentences = re.split(r"[。\n]+", remaining)
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        effect = _single_effect(sentence)
        if effect:
            steps.append(effect)

    return steps


def _single_effect(text: str) -> dict | None:
    """
    1文の効果テキストから単一の EffectStep を生成する。
    マッチしない場合は None を返す。
    """
    t = text.strip()
    if not t:
        return None

    # ============ 状態異常 ============
    if re.search(r"どくにする|毒にする|どく状態にする", t):
        return {"type": "poison", "params": {}}

    if re.search(r"やけど状態にする|やけどにする", t):
        return {"type": "burn", "params": {}}

    if re.search(r"マヒにする|まひにする|マヒ状態にする|まひ状態にする", t):
        return {"type": "paralysis", "params": {}}

    if re.search(r"ねむり状態にする|ねむりにする|眠り状態にする", t):
        return {"type": "sleep", "params": {}}

    if re.search(r"こんらん状態にする|こんらんにする|混乱状態にする", t):
        return {"type": "confusion", "params": {}}

    # ============ 移動制限 ============
    if re.search(r"にげられない|逃げられない", t):
        return {"type": "cant_retreat", "params": {}}

    # ============ ベンチへのダメージ ============
    # 「相手のベンチポケモン全員に〇ダメージ」
    m = re.search(r"ベンチポケモン全員に(\d+)ダメージ", t)
    if m:
        return {"type": "bench_damage", "params": {"damage": int(m.group(1)), "target": "all"}}

    # 「相手のベンチポケモン1体に〇ダメージ」
    m = re.search(r"ベンチ.{0,4}ポケモン.{0,4}に(\d+)ダメージ", t)
    if m:
        return {"type": "bench_damage", "params": {"damage": int(m.group(1)), "target": "single"}}

    # ============ 自分へのダメージ ============
    # 「自分のバトルポケモンにも〇ダメージ」
    m = re.search(r"自分.{0,12}に[もを]?(\d+)ダメージ", t)
    if m:
        return {"type": "self_damage", "params": {"damage": int(m.group(1))}}

    # ============ ダメージ軽減 ============
    # 「このポケモンが受けるワザのダメージを〇減らす」「ダメージを-〇する」
    m = re.search(r"ダメージ[をが].{0,4}[-－](\d+)|(\d+)減らす", t)
    if m:
        val = int(m.group(1) or m.group(2))
        return {"type": "damage_reduce", "params": {"value": val}}

    # ============ 回復 ============
    # 「自分のバトルポケモンのHPを〇回復する」
    m = re.search(r"自分.{0,12}HP[をが]?(\d+)回復", t)
    if m:
        return {"type": "heal_self", "params": {"hp": int(m.group(1))}}

    # 「〇のHPを〇回復する」（ベンチ全員 or タイプ指定）
    m = re.search(r"ベンチ[^\d]{0,8}(\d+)回復|ベンチ全員[^\d]{0,8}(\d+)回復してもよい", t)
    if m:
        hp = int(m.group(1) or m.group(2))
        # タイプ指定があるか確認
        type_match = re.search(r"自分の(草|炎|水|雷|超|闘|悪|鋼|無色)ポケモン", t)
        params: dict = {"hp": hp}
        if type_match:
            params["filter_type"] = type_match.group(1)
        return {"type": "heal_bench", "params": params}

    # 「自分のポケモン全員のHPを〇回復する」
    m = re.search(r"ポケモン全員[^\d]{0,8}(\d+)回復", t)
    if m:
        hp = int(m.group(1))
        # タイプ指定（草ポケモン全員、など）
        type_match = re.search(r"自分の(草|炎|水|雷|超|闘|悪|鋼|無色)ポケモン", t)
        params = {"hp": hp}
        if type_match:
            params["filter_type"] = type_match.group(1)
        return {"type": "heal_bench", "params": params}

    # ============ 山札・手札操作 ============
    # 「カードを〇枚引く」
    m = re.search(r"カードを(\d+)枚引く|山札から(\d+)枚引く|\d+枚ドローする", t)
    if m:
        count = int(m.group(1) or m.group(2) or 1)
        return {"type": "draw", "params": {"count": count}}

    # 「手札からカードを〇枚[選んで]トラッシュする」
    m = re.search(r"手札.{0,6}(\d+)枚.{0,6}(?:トラッシュ|捨て)", t)
    if m:
        optional = "のぞむなら" in t or "してもよい" in t
        return {"type": "discard_hand", "params": {"count": int(m.group(1)), "optional": optional}}

    # 「山札にある〇ポケモンを手札に加える」
    m = re.search(r"山札.{0,4}ポケモン.{0,6}手札に加え", t)
    if m:
        return {"type": "search_pokemon", "params": {"to": "hand"}}

    # 「山札からエネルギーを1枚選び〜につける」
    m = re.search(r"山札.{0,4}エネルギー.{0,16}?(ベンチ|バトル場|手札)", t)
    if m:
        to = "bench" if "ベンチ" in m.group(1) else "hand"
        # エネルギータイプ指定があるか
        etype = re.search(r"(草|炎|水|雷|超|闘|悪|鋼|無色)エネルギー", t)
        params = {"to": to}
        if etype:
            params["energy_type"] = etype.group(1)
        return {"type": "search_energy", "params": params}

    # ============ エネルギー操作 ============
    # 「このポケモンについているエネルギーを全てトラッシュする」
    if re.search(r"エネルギーを全てトラッシュ|エネルギーをすべてトラッシュ", t):
        return {"type": "discard_energy", "params": {"count": 99, "from": "self"}}

    # 「このポケモンについているエネルギーを〇枚トラッシュする」
    m = re.search(r"つ[いけ]ている.{0,4}エネルギー.{0,4}(\d+)枚.{0,4}トラッシュ", t)
    if m:
        return {"type": "discard_energy", "params": {"count": int(m.group(1)), "from": "self"}}

    # 「相手のポケモンについているエネルギー〇枚をトラッシュ」
    m = re.search(r"相手.{0,8}エネルギー.{0,4}(\d+)枚.{0,4}トラッシュ", t)
    if m:
        return {"type": "discard_energy", "params": {"count": int(m.group(1)), "from": "opponent"}}

    # ============ 特殊処理（custom）============
    # 「このポケモンはきぜつする」（自爆）
    if re.search(r"このポケモンはきぜつする", t):
        return {"type": "custom", "params": {"id": "self_ko"}}

    # ============ 行動制限 ============
    # 「次の自分の番、このポケモンはワザが使えない」
    if re.search(r"次の自分の番.{0,10}ワザ[がを]使えない|次の番.{0,10}ワザ[がを]使えない", t):
        return {"type": "cant_attack", "params": {}}

    # ============ マッチしない場合 ============
    return None


# ============================================================
# DB操作
# ============================================================

def load_cards_with_attacks(conn: sqlite3.Connection) -> list[dict]:
    """attacksが存在するポケモンカードを全件取得"""
    rows = conn.execute(
        "SELECT id, name, attacks FROM cards "
        "WHERE card_type = 'pokemon' AND attacks IS NOT NULL AND attacks != '[]' AND attacks != ''"
        "ORDER BY id"
    ).fetchall()
    return [dict(r) for r in rows]


def convert_card_attacks(card: dict) -> tuple[list[dict], list[str]]:
    """
    1枚のカードの attacks JSON を変換する。

    Returns:
        (更新後attacks, マッチしなかったテキストリスト)
    """
    attacks_raw = json.loads(card["attacks"])
    unmatched = []
    updated_attacks = []

    for attack in attacks_raw:
        desc = attack.get("description", "")
        steps = parse_description(desc)

        if desc and not steps:
            unmatched.append(f"  [{card['name']}] {attack.get('name','')}: {desc}")

        updated_attack = dict(attack)
        updated_attack["effect_steps"] = steps
        updated_attacks.append(updated_attack)

    return updated_attacks, unmatched


def main(dry_run: bool = False, show_unmatched: bool = False):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    cards = load_cards_with_attacks(conn)
    print(f"対象カード: {len(cards)}件")

    all_unmatched: list[str] = []
    updated_count = 0

    for card in cards:
        updated_attacks, unmatched = convert_card_attacks(card)
        all_unmatched.extend(unmatched)

        if dry_run:
            print(f"\n[{card['id']}] {card['name']}")
            for atk in updated_attacks:
                steps_str = json.dumps(atk["effect_steps"], ensure_ascii=False)
                print(f"  ワザ: {atk['name']} / steps: {steps_str}")
        else:
            conn.execute(
                "UPDATE cards SET attacks = ? WHERE id = ?",
                (json.dumps(updated_attacks, ensure_ascii=False), card["id"]),
            )
            updated_count += 1

    if not dry_run:
        conn.commit()
        print(f"\n完了: {updated_count}件更新")

    if show_unmatched or dry_run:
        if all_unmatched:
            print(f"\n--- マッチしなかった効果テキスト ({len(all_unmatched)}件) ---")
            for line in all_unmatched:
                print(line)
        else:
            print("\n全効果テキストがマッチしました ✅")

    conn.close()


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    show = "--show-unmatched" in sys.argv
    main(dry_run=dry, show_unmatched=show)
