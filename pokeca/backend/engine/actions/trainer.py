"""
タスク3-9: トレーナーカード処理
サポート（1ターン1枚）・グッズ（無制限）・スタジアム（1ターン1枚）の使用ルールを実装する
Phase 3ではルール制限のみ実装。実際の効果はPhase 11で拡張。
"""
from engine.models.game_state import GameState, StadiumState
from engine.models.game_enums import TurnPhase


# カードのevolution_stageやtypeでトレーナー種別を判別するための定数
# ※ 実際のカードデータの構造に合わせて適宜調整が必要
TRAINER_CATEGORY_SUPPORTER = "サポート"
TRAINER_CATEGORY_GOODS = "グッズ"
TRAINER_CATEGORY_STADIUM = "スタジアム"


def use_supporter(game_state: GameState, player_id: str, card_id: int) -> dict:
    """
    サポートカードを使用する（1ターン1枚制限）。
    Phase 3では使用制限チェックのみ行い、効果は適用しない。

    Returns:
        {"success": bool, "message": str}
    """
    player = game_state.get_player(player_id)

    if game_state.current_player_id != player_id:
        return {"success": False, "message": "自分のターンではありません"}
    if game_state.turn_phase != TurnPhase.MAIN:
        return {"success": False, "message": "メインフェーズ以外ではサポートを使用できません"}
    if player.supporter_used_this_turn:
        return {"success": False, "message": "このターンはすでにサポートを使用済みです"}

    card = _find_card_in_hand(player, card_id)
    if card is None:
        return {"success": False, "message": f"手札にカードID={card_id}が見つかりません"}

    # 手札から取り出してトラッシュへ
    player.hand = [c for c in player.hand if c.id != card_id]
    player.discard_pile.append(card)
    player.supporter_used_this_turn = True

    game_state.add_log("USE_SUPPORTER", f"{player_id}: {card.name}を使用（効果はPhase 11で実装）")
    return {"success": True, "message": f"{card.name}を使用した（効果はPhase 11で実装）"}


def use_goods(game_state: GameState, player_id: str, card_id: int) -> dict:
    """
    グッズカードを使用する（使用回数制限なし）。
    Phase 3では使用制限チェックのみ行い、効果は適用しない。

    Returns:
        {"success": bool, "message": str}
    """
    player = game_state.get_player(player_id)

    if game_state.current_player_id != player_id:
        return {"success": False, "message": "自分のターンではありません"}
    if game_state.turn_phase != TurnPhase.MAIN:
        return {"success": False, "message": "メインフェーズ以外ではグッズを使用できません"}

    card = _find_card_in_hand(player, card_id)
    if card is None:
        return {"success": False, "message": f"手札にカードID={card_id}が見つかりません"}

    player.hand = [c for c in player.hand if c.id != card_id]
    player.discard_pile.append(card)

    game_state.add_log("USE_GOODS", f"{player_id}: {card.name}を使用（効果はPhase 11で実装）")
    return {"success": True, "message": f"{card.name}を使用した（効果はPhase 11で実装）"}


def use_stadium(game_state: GameState, player_id: str, card_id: int) -> dict:
    """
    スタジアムカードを使用する（1ターン1枚、既存スタジアムはトラッシュ）。

    Returns:
        {"success": bool, "message": str}
    """
    player = game_state.get_player(player_id)

    if game_state.current_player_id != player_id:
        return {"success": False, "message": "自分のターンではありません"}
    if game_state.turn_phase != TurnPhase.MAIN:
        return {"success": False, "message": "メインフェーズ以外ではスタジアムを使用できません"}

    card = _find_card_in_hand(player, card_id)
    if card is None:
        return {"success": False, "message": f"手札にカードID={card_id}が見つかりません"}

    # 既存のスタジアムがあればトラッシュ
    old_stadium_name = None
    if game_state.stadium is not None:
        old_card = game_state.stadium.card
        old_stadium_name = old_card.name
        # スタジアムを置いたプレイヤーのトラッシュへ
        old_owner = game_state.get_player(game_state.stadium.played_by)
        old_owner.discard_pile.append(old_card)

    # 新しいスタジアムを場に出す
    player.hand = [c for c in player.hand if c.id != card_id]
    game_state.stadium = StadiumState(card=card, played_by=player_id)

    detail = f"{player_id}: {card.name}をスタジアムに設置"
    if old_stadium_name:
        detail += f"（{old_stadium_name}をトラッシュ）"

    game_state.add_log("USE_STADIUM", detail)
    return {"success": True, "message": detail}


def _find_card_in_hand(player, card_id: int):
    for card in player.hand:
        if card.id == card_id:
            return card
    return None
