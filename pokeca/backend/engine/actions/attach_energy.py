"""
タスク3-7: エネルギー付与処理
1ターン1回、手札のエネルギーカードを場のポケモンに付与する
"""
from engine.models.game_state import GameState
from engine.models.game_enums import TurnPhase


def attach_energy(
    game_state: GameState,
    player_id: str,
    energy_card_id: int,
    target: str,
    bench_index: int = -1,
) -> dict:
    """
    手札のエネルギーカードを場のポケモンに付与する。

    Args:
        game_state: ゲーム状態
        player_id: 操作プレイヤーID
        energy_card_id: 手札のエネルギーカードID
        target: "active" or "bench"
        bench_index: targetが"bench"の場合のベンチインデックス（0始まり）

    Returns:
        {"success": bool, "message": str}
    """
    player = game_state.get_player(player_id)

    if game_state.current_player_id != player_id:
        return {"success": False, "message": "自分のターンではありません"}
    if game_state.turn_phase != TurnPhase.MAIN:
        return {"success": False, "message": "メインフェーズ以外ではエネルギーを付与できません"}

    # 1ターン1回制限チェック
    if player.energy_attached_this_turn:
        return {"success": False, "message": "このターンはすでにエネルギーを付与済みです"}

    # 手札からエネルギーカードを探す
    energy_card = None
    for card in player.hand:
        if card.uid == energy_card_id:
            energy_card = card
            break

    if energy_card is None:
        return {"success": False, "message": f"手札にカードID={energy_card_id}が見つかりません"}

    # エネルギータイプの取得（エネルギーカードのtypeをそのまま使用）
    energy_type = energy_card.type or "無色"

    # 付与先ポケモンを特定
    if target == "active":
        if not player.has_active:
            return {"success": False, "message": "バトル場にポケモンがいません"}
        pokemon = player.active_pokemon
        target_name = pokemon.card.name
    elif target == "bench":
        if bench_index < 0 or bench_index >= len(player.bench):
            return {"success": False, "message": f"ベンチインデックス{bench_index}が無効です"}
        pokemon = player.bench[bench_index]
        target_name = pokemon.card.name
    else:
        return {"success": False, "message": f"無効なtarget: {target}。'active' or 'bench'を指定してください"}

    # エネルギーを付与
    pokemon.attached_energy.append(energy_type)
    player.hand = [c for c in player.hand if c.uid != energy_card.uid]
    player.discard_pile.append(energy_card)
    player.energy_attached_this_turn = True

    game_state.add_log(
        "ATTACH_ENERGY",
        f"{player_id}: {energy_type}エネルギーを{target_name}に付与"
    )
    return {
        "success": True,
        "message": f"{energy_type}エネルギーを{target_name}に付与した"
    }
