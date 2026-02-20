"""
タスク3-12: 勝利条件チェック
3つの勝利条件をチェックする
"""
from engine.models.game_state import GameState


def check_victory(game_state: GameState) -> dict:
    """
    勝利条件をチェックして結果を返す。

    勝利条件:
    1. 自分のサイドカードを全て取得した
    2. 相手のバトル場が空かつベンチも空
    3. ターン開始時に相手の山札が0枚（begin_turn側でチェック）

    Returns:
        {"game_over": bool, "winner_id": str | None, "reason": str}
    """
    p1 = game_state.player1
    p2 = game_state.player2

    # 条件1: サイドカード全取得
    if p1.prize_remaining == 0:
        return {
            "game_over": True,
            "winner_id": "player1",
            "reason": "player1がサイドカードを全て取得"
        }
    if p2.prize_remaining == 0:
        return {
            "game_over": True,
            "winner_id": "player2",
            "reason": "player2がサイドカードを全て取得"
        }

    # 条件2: 相手のバトル場が空（きぜつ後にベンチも空）
    if not p1.has_active and not p1.has_bench_pokemon:
        return {
            "game_over": True,
            "winner_id": "player2",
            "reason": "player1のバトル場とベンチが空になった"
        }
    if not p2.has_active and not p2.has_bench_pokemon:
        return {
            "game_over": True,
            "winner_id": "player1",
            "reason": "player2のバトル場とベンチが空になった"
        }

    # 条件3: 山札切れはbegin_turn()側でチェックするためここでは判定しない
    return {
        "game_over": False,
        "winner_id": None,
        "reason": ""
    }
