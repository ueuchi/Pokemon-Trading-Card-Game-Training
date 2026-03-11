"""
タスク3-5: ポケモンを場に出す処理
バトル場・ベンチへのポケモン配置ルールを実装する
"""
from models.card import PokemonCard
from engine.models.game_state import GameState
from engine.models.player_state import ActivePokemon, BenchPokemon
from engine.models.game_enums import TurnPhase


def place_to_active(game_state: GameState, player_id: str, card_id: int) -> dict:
    """
    手札のたねポケモンをバトル場に出す。
    バトル場が空の場合のみ配置可能（ポケモンがきぜつ後の交代はfaint.pyで処理）。

    Returns:
        {"success": bool, "message": str}
    """
    player = game_state.get_player(player_id)

    # フェーズチェック
    if game_state.turn_phase not in (TurnPhase.MAIN,):
        return {"success": False, "message": "メインフェーズ以外ではポケモンを出せません"}

    # 現在のプレイヤーのターンか
    if game_state.current_player_id != player_id:
        return {"success": False, "message": "自分のターンではありません"}

    # バトル場が空か
    if player.has_active:
        return {"success": False, "message": "バトル場にすでにポケモンがいます"}

    # 手札から対象カードを探す
    card = _find_card_in_hand(player, card_id)
    if card is None:
        return {"success": False, "message": f"手札にカードID={card_id}が見つかりません"}

    # たねポケモンのみ配置可能
    if card.evolution_stage != "たね":
        return {"success": False, "message": f"バトル場にはたねポケモンのみ出せます: {card.name}"}

    # 手札から取り出してバトル場へ（uidで特定の1枚を除去）
    player.hand = [c for c in player.hand if c.uid != card.uid]
    player.active_pokemon = ActivePokemon(card=card, turns_in_play=0)

    game_state.add_log("PLACE_ACTIVE", f"{player_id}: {card.name}をバトル場に出した")
    return {"success": True, "message": f"{card.name}をバトル場に出した"}


def place_to_bench(game_state: GameState, player_id: str, card_id: int) -> dict:
    """
    手札のたねポケモンをベンチに出す。
    ベンチは最大5枚まで。

    Returns:
        {"success": bool, "message": str}
    """
    player = game_state.get_player(player_id)

    # フェーズチェック
    if game_state.turn_phase not in (TurnPhase.MAIN,):
        return {"success": False, "message": "メインフェーズ以外ではポケモンを出せません"}

    if game_state.current_player_id != player_id:
        return {"success": False, "message": "自分のターンではありません"}

    # ベンチ満員チェック
    if player.bench_is_full:
        return {"success": False, "message": "ベンチが満員です（最大5枚）"}

    # 手札から対象カードを探す
    card = _find_card_in_hand(player, card_id)
    if card is None:
        return {"success": False, "message": f"手札にカードID={card_id}が見つかりません"}

    # たねポケモンのみ配置可能
    if card.evolution_stage != "たね":
        return {"success": False, "message": f"ベンチにはたねポケモンのみ出せます: {card.name}"}

    # 手札から取り出してベンチへ（uidで特定の1枚を除去）
    player.hand = [c for c in player.hand if c.uid != card.uid]
    player.bench.append(BenchPokemon(card=card, turns_in_play=0))

    game_state.add_log("PLACE_BENCH", f"{player_id}: {card.name}をベンチに出した")
    return {"success": True, "message": f"{card.name}をベンチに出した"}


def _find_card_in_hand(player, card_id: int):
    """手札からuidに一致するカードを返す（なければNone）"""
    for card in player.hand:
        if card.uid == card_id:
            return card
    return None
