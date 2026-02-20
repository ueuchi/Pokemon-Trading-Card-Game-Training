"""
タスク3-6: 進化処理
たねポケモン→1進化→2進化の進化ルールを実装する
"""
from engine.models.game_state import GameState
from engine.models.player_state import ActivePokemon, BenchPokemon
from engine.models.game_enums import TurnPhase, SpecialCondition

# 進化段階の順序マッピング
EVOLUTION_ORDER = {
    "たね": 0,
    "1 進化": 1,
    "2 進化": 2,
}

NEXT_STAGE = {
    "たね": "1 進化",
    "1 進化": "2 進化",
}


def evolve_active(game_state: GameState, player_id: str, card_id: int) -> dict:
    """
    バトル場のポケモンを進化させる。

    Args:
        game_state: ゲーム状態
        player_id: 操作プレイヤーID
        card_id: 手札の進化カードのID

    Returns:
        {"success": bool, "message": str}
    """
    player = game_state.get_player(player_id)

    if game_state.current_player_id != player_id:
        return {"success": False, "message": "自分のターンではありません"}
    if game_state.turn_phase != TurnPhase.MAIN:
        return {"success": False, "message": "メインフェーズ以外では進化できません"}
    if not player.has_active:
        return {"success": False, "message": "バトル場にポケモンがいません"}

    active = player.active_pokemon
    evo_check = _check_evolution_conditions(game_state, active)
    if not evo_check["can_evolve"]:
        return {"success": False, "message": evo_check["reason"]}

    # 手札から進化カードを探す
    evo_card = _find_card_in_hand(player, card_id)
    if evo_card is None:
        return {"success": False, "message": f"手札にカードID={card_id}が見つかりません"}

    # 進化先の段階チェック
    current_stage = active.card.evolution_stage
    expected_next = NEXT_STAGE.get(current_stage)
    if evo_card.evolution_stage != expected_next:
        return {
            "success": False,
            "message": f"{active.card.name}({current_stage})の次の進化は{expected_next}です。{evo_card.name}は{evo_card.evolution_stage}です"
        }

    # 進化元カードをトラッシュへ
    old_card = active.card
    player.discard_pile.append(old_card)

    # エネルギーを引き継ぎ、特殊状態はリセット
    old_energy = active.attached_energy.copy()
    old_damage = active.damage_counters

    # 手札から進化カードを取り出してバトル場へ
    player.hand = [c for c in player.hand if c.id != card_id]
    player.active_pokemon = ActivePokemon(
        card=evo_card,
        damage_counters=old_damage,
        attached_energy=old_energy,
        special_condition=SpecialCondition.NONE,  # 特殊状態リセット
        turns_in_play=0,  # 進化したターンは再度進化不可
    )

    game_state.add_log(
        "EVOLVE_ACTIVE",
        f"{player_id}: {old_card.name} → {evo_card.name}（バトル場）"
    )
    return {"success": True, "message": f"{old_card.name}が{evo_card.name}に進化した"}


def evolve_bench(game_state: GameState, player_id: str, bench_index: int, card_id: int) -> dict:
    """
    ベンチのポケモンを進化させる。

    Args:
        bench_index: ベンチの何番目のポケモンか（0始まり）
        card_id: 手札の進化カードのID
    """
    player = game_state.get_player(player_id)

    if game_state.current_player_id != player_id:
        return {"success": False, "message": "自分のターンではありません"}
    if game_state.turn_phase != TurnPhase.MAIN:
        return {"success": False, "message": "メインフェーズ以外では進化できません"}

    if bench_index < 0 or bench_index >= len(player.bench):
        return {"success": False, "message": f"ベンチインデックス{bench_index}が無効です"}

    bench_mon = player.bench[bench_index]
    evo_check = _check_evolution_conditions(game_state, bench_mon)
    if not evo_check["can_evolve"]:
        return {"success": False, "message": evo_check["reason"]}

    evo_card = _find_card_in_hand(player, card_id)
    if evo_card is None:
        return {"success": False, "message": f"手札にカードID={card_id}が見つかりません"}

    current_stage = bench_mon.card.evolution_stage
    expected_next = NEXT_STAGE.get(current_stage)
    if evo_card.evolution_stage != expected_next:
        return {
            "success": False,
            "message": f"{bench_mon.card.name}({current_stage})の次の進化は{expected_next}です"
        }

    old_card = bench_mon.card
    player.discard_pile.append(old_card)
    old_energy = bench_mon.attached_energy.copy()
    old_damage = bench_mon.damage_counters

    player.hand = [c for c in player.hand if c.id != card_id]
    player.bench[bench_index] = BenchPokemon(
        card=evo_card,
        damage_counters=old_damage,
        attached_energy=old_energy,
        special_condition=SpecialCondition.NONE,
        turns_in_play=0,
    )

    game_state.add_log(
        "EVOLVE_BENCH",
        f"{player_id}: {old_card.name} → {evo_card.name}（ベンチ{bench_index}）"
    )
    return {"success": True, "message": f"{old_card.name}が{evo_card.name}に進化した"}


def _check_evolution_conditions(game_state: GameState, pokemon) -> dict:
    """
    進化可能かどうかをチェックする共通処理。

    進化不可条件:
    - 最初のターン（先行・後攻共に）
    - 場に出した同一ターン内（turns_in_play == 0）
    """
    # ゲーム最初のターン（current_turn == 1）
    if game_state.current_turn == 1:
        return {"can_evolve": False, "reason": "最初のターンは進化できません"}

    # 場に出たターンは進化不可
    if pokemon.turns_in_play == 0:
        return {"can_evolve": False, "reason": f"{pokemon.card.name}は場に出たターンには進化できません"}

    # 2進化以上には進化できない
    if pokemon.card.evolution_stage == "2 進化":
        return {"can_evolve": False, "reason": f"{pokemon.card.name}はすでに最終進化です"}

    return {"can_evolve": True, "reason": ""}


def _find_card_in_hand(player, card_id: int):
    for card in player.hand:
        if card.id == card_id:
            return card
    return None
