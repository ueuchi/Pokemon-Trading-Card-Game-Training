"""
タスク3-4: ドロー処理
山札からカードを引く処理
"""
from engine.models.game_state import GameState


def draw_card(game_state: GameState, player_id: str) -> dict:
    """
    指定プレイヤーが山札から1枚引く。
    山札が0枚の場合はエラーを返す（山札切れ判定はbegin_turn側で行う）。

    Returns:
        {"success": bool, "message": str, "card_name": str | None}
    """
    player = game_state.get_player(player_id)

    if player.deck_count == 0:
        return {
            "success": False,
            "message": "山札が0枚です。カードを引けません。",
            "card_name": None,
        }

    card = player.deck.pop(0)
    player.hand.append(card)

    return {
        "success": True,
        "message": f"{card.name}を引いた",
        "card_name": card.name,
    }


def draw_cards(game_state: GameState, player_id: str, count: int) -> dict:
    """
    指定プレイヤーが山札からcount枚引く（サポートカード効果等で複数枚引く場合）。
    山札が足りない場合は引ける分だけ引く。

    Returns:
        {"success": bool, "message": str, "drew_count": int, "card_names": list[str]}
    """
    player = game_state.get_player(player_id)
    drew = []

    for _ in range(count):
        if player.deck_count == 0:
            break
        card = player.deck.pop(0)
        player.hand.append(card)
        drew.append(card.name)

    return {
        "success": True,
        "message": f"{len(drew)}枚引いた",
        "drew_count": len(drew),
        "card_names": drew,
    }
