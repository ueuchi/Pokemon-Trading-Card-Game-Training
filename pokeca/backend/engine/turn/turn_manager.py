"""
タスク3-3: ターン管理
ターン開始・終了・プレイヤー交代を管理する
"""
from engine.models.game_state import GameState
from engine.models.game_enums import TurnPhase, GamePhase
from engine.actions.draw import draw_card
from engine.victory import check_victory


def begin_turn(game_state: GameState) -> dict:
    """
    ターン開始処理。
    1. ターンフラグをリセット
    2. 山札から1枚ドロー（山札切れなら負け）
    3. turn_phaseをMAINに移行

    Returns:
        {"success": bool, "message": str, "drew_card": str | None}
    """
    player = game_state.current_player

    # ターンフラグリセット（switch_turnで既にリセット済みのケースもあるが念のため）
    player.reset_turn_flags()
    game_state.attacked_this_turn = False

    # 山札切れチェック（引く前に判定）
    if player.deck_count == 0:
        game_state.game_phase = GamePhase.GAME_OVER
        opponent = game_state.opponent
        game_state.winner_id = opponent.player_id
        game_state.add_log(
            "DECK_OUT",
            f"{player.player_id}の山札が0枚のためターン開始時にドローできず敗北"
        )
        return {
            "success": False,
            "message": f"{player.player_id}の山札が切れました。{opponent.player_id}の勝利です。",
            "drew_card": None,
        }

    # 1枚ドロー
    result = draw_card(game_state, player.player_id)

    # MAINフェーズへ
    game_state.turn_phase = TurnPhase.MAIN

    drew_name = result.get("card_name", "不明")
    game_state.add_log("TURN_START", f"ターン{game_state.current_turn} {player.player_id} ドロー: {drew_name}")

    return {
        "success": True,
        "message": f"ターン{game_state.current_turn}開始。{drew_name}を引いた。",
        "drew_card": drew_name,
    }


def end_turn(game_state: GameState) -> dict:
    """
    ターン終了処理。
    1. 勝利条件チェック
    2. 次プレイヤーへ交代

    Returns:
        {"success": bool, "message": str, "game_over": bool, "winner_id": str | None}
    """
    # 終了前に勝利条件チェック
    victory = check_victory(game_state)
    if victory["game_over"]:
        game_state.game_phase = GamePhase.GAME_OVER
        game_state.winner_id = victory["winner_id"]
        game_state.add_log("GAME_OVER", f"勝者: {victory['winner_id']} / 理由: {victory['reason']}")
        return {
            "success": True,
            "message": f"ゲーム終了。{victory['winner_id']}の勝利！（{victory['reason']}）",
            "game_over": True,
            "winner_id": victory["winner_id"],
        }

    current_id = game_state.current_player_id
    game_state.add_log("TURN_END", f"ターン{game_state.current_turn} 終了")

    # ターンを切り替え
    game_state.switch_turn()

    # game_phase更新
    if game_state.current_player_id == "player1":
        game_state.game_phase = GamePhase.PLAYER1_TURN
    else:
        game_state.game_phase = GamePhase.PLAYER2_TURN

    return {
        "success": True,
        "message": f"{current_id}のターン終了。{game_state.current_player_id}のターン開始。",
        "game_over": False,
        "winner_id": None,
    }
