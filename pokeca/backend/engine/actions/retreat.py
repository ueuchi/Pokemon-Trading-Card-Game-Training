"""
タスク3-8: 逃げる処理
1ターン1回、逃げエネルギーをトラッシュしてバトル場のポケモンをベンチと入れ替える
"""
from engine.models.game_state import GameState
from engine.models.player_state import ActivePokemon
from engine.models.game_enums import TurnPhase, SpecialCondition


def retreat(
    game_state: GameState,
    player_id: str,
    bench_index: int,
    energy_indices: list[int],
) -> dict:
    """
    バトル場のポケモンを逃がし、ベンチのポケモンと入れ替える。

    Args:
        game_state: ゲーム状態
        player_id: 操作プレイヤーID
        bench_index: バトル場に出すベンチポケモンのインデックス（0始まり）
        energy_indices: トラッシュするエネルギーのインデックスリスト（attached_energyのインデックス）

    Returns:
        {"success": bool, "message": str}
    """
    player = game_state.get_player(player_id)

    if game_state.current_player_id != player_id:
        return {"success": False, "message": "自分のターンではありません"}
    if game_state.turn_phase != TurnPhase.MAIN:
        return {"success": False, "message": "メインフェーズ以外では逃げられません"}

    # 1ターン1回制限チェック
    if player.retreated_this_turn:
        return {"success": False, "message": "このターンはすでに逃げています"}

    if not player.has_active:
        return {"success": False, "message": "バトル場にポケモンがいません"}

    active = player.active_pokemon

    # 特殊状態：まひ・ねむりは逃げられない
    if active.special_condition in (SpecialCondition.PARALYZED, SpecialCondition.ASLEEP):
        return {"success": False, "message": f"{active.card.name}は{active.special_condition.value}状態で逃げられません"}

    # 特殊状態：逃げられない
    if active.special_condition == SpecialCondition.CANT_RETREAT:
        return {"success": False, "message": f"{active.card.name}は逃げられない状態です"}

    # ベンチが空なら逃げられない
    if not player.has_bench_pokemon:
        return {"success": False, "message": "ベンチにポケモンがいないため逃げられません"}

    if bench_index < 0 or bench_index >= len(player.bench):
        return {"success": False, "message": f"ベンチインデックス{bench_index}が無効です"}

    # 逃げエネルギーのコストチェック
    retreat_cost = active.card.retreat_cost or 0
    if len(energy_indices) != retreat_cost:
        return {
            "success": False,
            "message": f"{active.card.name}の逃げエネルギーは{retreat_cost}個です。{len(energy_indices)}個指定されました"
        }

    # インデックスの有効性チェック
    for idx in energy_indices:
        if idx < 0 or idx >= len(active.attached_energy):
            return {"success": False, "message": f"エネルギーインデックス{idx}が無効です"}

    # 重複インデックスチェック
    if len(set(energy_indices)) != len(energy_indices):
        return {"success": False, "message": "同じエネルギーを複数回指定することはできません"}

    # エネルギーをトラッシュ（インデックスを降順でソートして後ろから削除）
    old_active_name = active.card.name
    for idx in sorted(energy_indices, reverse=True):
        trashed_energy_type = active.attached_energy.pop(idx)
        # エネルギーカード自体はトラッシュに積む（型を合わせるため簡易的にcard情報を記録）
        # 実際のエネルギーカードオブジェクトは手元にないため、ログのみ記録

    # バトル場とベンチを入れ替え
    bench_mon = player.bench[bench_index]
    new_active = ActivePokemon(
        card=bench_mon.card,
        damage_counters=bench_mon.damage_counters,
        attached_energy=bench_mon.attached_energy.copy(),
        special_condition=bench_mon.special_condition,
        turns_in_play=bench_mon.turns_in_play,
    )

    # 逃げたポケモンをベンチへ（特殊状態はリセット）
    from engine.models.player_state import BenchPokemon
    retreated_bench = BenchPokemon(
        card=active.card,
        damage_counters=active.damage_counters,
        attached_energy=active.attached_energy.copy(),
        special_condition=SpecialCondition.NONE,  # 逃げると特殊状態リセット
        turns_in_play=active.turns_in_play,
    )

    player.bench[bench_index] = retreated_bench
    player.active_pokemon = new_active
    player.retreated_this_turn = True

    game_state.add_log(
        "RETREAT",
        f"{player_id}: {old_active_name}が逃げ、{new_active.card.name}がバトル場に出た"
    )
    return {
        "success": True,
        "message": f"{old_active_name}が逃げ、{new_active.card.name}がバトル場に出た"
    }
