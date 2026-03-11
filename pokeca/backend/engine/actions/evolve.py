"""
進化処理
たねポケモン→1進化→2進化の進化ルールを実装する。

進化ルール:
- normal ポケモンは normal ポケモンにのみ進化できる
- trainer_pokemon は trainer_pokemon にのみ進化できる
- 最初のターンは進化不可
- 場に出したターンは進化不可（turns_in_play == 0）
"""
from engine.models.game_state import GameState
from engine.models.player_state import ActivePokemon, BenchPokemon
from engine.models.game_enums import TurnPhase, SpecialCondition

EVOLUTION_ORDER = {
    "たね": 0,
    "1進化": 1,
    "2進化": 2,
}

NEXT_STAGE = {
    "たね": "1進化",
    "1進化": "2進化",
}


def evolve_active(game_state: GameState, player_id: str, card_id: int) -> dict:
    """バトル場のポケモンを進化させる"""
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

    evo_card = _find_card_in_hand(player, card_id)
    if evo_card is None:
        return {"success": False, "message": f"手札にカードID={card_id}が見つかりません"}

    # 進化段階チェック
    current_stage = active.card.evolution_stage
    expected_next = NEXT_STAGE.get(current_stage)
    if evo_card.evolution_stage != expected_next:
        return {
            "success": False,
            "message": f"{active.card.name}({current_stage})の次の進化は{expected_next}です"
        }

    # pokemon_type 一致チェック
    type_check = _check_pokemon_type_match(active.card, evo_card)
    if not type_check["ok"]:
        return {"success": False, "message": type_check["reason"]}

    # 進化元をトラッシュ
    old_card = active.card
    player.discard_pile.append(old_card)

    # エネルギー・ダメージ引き継ぎ・特殊状態リセット
    player.hand = [c for c in player.hand if c.uid != evo_card.uid]
    player.active_pokemon = ActivePokemon(
        card=evo_card,
        damage_counters=active.damage_counters,
        attached_energy=active.attached_energy.copy(),
        special_condition=SpecialCondition.NONE,
        turns_in_play=0,
    )

    game_state.add_log("EVOLVE_ACTIVE", f"{player_id}: {old_card.name} → {evo_card.name}（バトル場）")
    return {"success": True, "message": f"{old_card.name}が{evo_card.name}に進化した"}


def evolve_bench(game_state: GameState, player_id: str, bench_index: int, card_id: int) -> dict:
    """ベンチのポケモンを進化させる"""
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

    # pokemon_type 一致チェック
    type_check = _check_pokemon_type_match(bench_mon.card, evo_card)
    if not type_check["ok"]:
        return {"success": False, "message": type_check["reason"]}

    old_card = bench_mon.card
    player.discard_pile.append(old_card)
    player.hand = [c for c in player.hand if c.uid != evo_card.uid]
    player.bench[bench_index] = BenchPokemon(
        card=evo_card,
        damage_counters=bench_mon.damage_counters,
        attached_energy=bench_mon.attached_energy.copy(),
        special_condition=SpecialCondition.NONE,
        turns_in_play=0,
    )

    game_state.add_log("EVOLVE_BENCH", f"{player_id}: {old_card.name} → {evo_card.name}（ベンチ{bench_index}）")
    return {"success": True, "message": f"{old_card.name}が{evo_card.name}に進化した"}


def _check_evolution_conditions(game_state: GameState, pokemon) -> dict:
    """進化可能かどうかをチェック"""
    if game_state.current_turn == 1:
        return {"can_evolve": False, "reason": "最初のターンは進化できません"}
    if pokemon.turns_in_play == 0:
        return {"can_evolve": False, "reason": f"{pokemon.card.name}は場に出たターンには進化できません"}
    if pokemon.card.evolution_stage == "2進化":
        return {"can_evolve": False, "reason": f"{pokemon.card.name}はすでに最終進化です"}
    return {"can_evolve": True, "reason": ""}


def _check_pokemon_type_match(base_card, evo_card) -> dict:
    """
    進化元と進化先のpokemon_typeが一致するか確認する。
    normal → normal のみ可
    trainer_pokemon → trainer_pokemon のみ可
    """
    base_type = getattr(base_card, "pokemon_type", "normal") or "normal"
    evo_type = getattr(evo_card, "pokemon_type", "normal") or "normal"

    if base_type != evo_type:
        type_label = {"normal": "通常ポケモン", "trainer_pokemon": "トレーナーポケモン"}
        return {
            "ok": False,
            "reason": (
                f"{base_card.name}（{type_label.get(base_type, base_type)}）は"
                f"{type_label.get(evo_type, evo_type)}には進化できません"
            )
        }
    return {"ok": True, "reason": ""}


def _find_card_in_hand(player, card_id: int):
    for card in player.hand:
        if card.uid == card_id:
            return card
    return None