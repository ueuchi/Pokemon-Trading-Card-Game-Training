"""
タスク3-10: 攻撃処理
攻撃宣言・エネルギーコスト確認・ダメージ計算（弱点・抵抗力・ダメージカウンター型）を実装する
"""
import random
from dataclasses import dataclass
from engine.models.game_state import GameState
from engine.models.game_enums import TurnPhase, DamageType, SpecialCondition
from engine.models.player_state import PlayerState, ActivePokemon, BenchPokemon
from engine.actions.faint import check_and_process_faint


@dataclass
class EffectContext:
    """効果処理に必要な参照をまとめる構造体"""
    game_state: GameState
    attacker_player: PlayerState
    defender_player: PlayerState
    attacker: ActivePokemon
    defender: ActivePokemon


def declare_attack(
    game_state: GameState,
    player_id: str,
    attack_index: int,
) -> dict:
    """
    攻撃宣言を行いダメージを適用する。
    攻撃後はそのターンを終了し、相手のターンへ移行する。

    Args:
        game_state: ゲーム状態
        player_id: 攻撃プレイヤーID
        attack_index: 使用するワザのインデックス（0始まり）

    Returns:
        {"success": bool, "message": str, "damage": int, "fainted": bool}
    """
    player = game_state.get_player(player_id)
    opponent = game_state.get_opponent_of(player_id)

    if game_state.current_player_id != player_id:
        return {"success": False, "message": "自分のターンではありません", "damage": 0, "fainted": False}
    if game_state.turn_phase != TurnPhase.MAIN:
        return {"success": False, "message": "メインフェーズ以外では攻撃できません", "damage": 0, "fainted": False}
    if game_state.attacked_this_turn:
        return {"success": False, "message": "このターンはすでに攻撃済みです", "damage": 0, "fainted": False}

    # 先行プレイヤーの最初のターンは攻撃不可
    if game_state.is_first_turn:
        return {"success": False, "message": "先行プレイヤーの最初のターンは攻撃できません", "damage": 0, "fainted": False}

    # バトル場のポケモン確認
    if not player.has_active:
        return {"success": False, "message": "バトル場にポケモンがいません", "damage": 0, "fainted": False}
    if not opponent.has_active:
        return {"success": False, "message": "相手のバトル場にポケモンがいません", "damage": 0, "fainted": False}

    attacker = player.active_pokemon
    defender = opponent.active_pokemon

    # ワザ存在チェック
    if attack_index < 0 or attack_index >= len(attacker.card.attacks):
        return {"success": False, "message": f"ワザインデックス{attack_index}が無効です", "damage": 0, "fainted": False}

    attack = attacker.card.attacks[attack_index]

    # エネルギーコストチェック
    cost_check = _check_energy_cost(attacker.attached_energy, attack.energy)
    if not cost_check["ok"]:
        return {
            "success": False,
            "message": f"エネルギーが足りません。必要: {attack.energy}, 現在: {attacker.attached_energy}",
            "damage": 0,
            "fainted": False,
        }

    # ダメージ計算
    damage = _calculate_damage(attack, attacker, defender)

    # ダメージ適用
    damage_counters = damage // 10
    defender.damage_counters += damage_counters

    game_state.attacked_this_turn = True
    game_state.turn_phase = TurnPhase.ATTACK

    # effect_steps の処理（ダメージ後に発動）
    if attack.effect_steps:
        ctx = EffectContext(
            game_state=game_state,
            attacker_player=player,
            defender_player=opponent,
            attacker=attacker,
            defender=defender,
        )
        apply_effect_steps(attack.effect_steps, ctx)

    game_state.add_log(
        "ATTACK",
        f"{player_id}: {attacker.card.name}の「{attack.name}」→ {defender.card.name}に{damage}ダメージ"
    )

    # きぜつ判定
    faint_result = check_and_process_faint(game_state, player_id)

    return {
        "success": True,
        "message": f"{attacker.card.name}の「{attack.name}」が{defender.card.name}に{damage}ダメージ！",
        "damage": damage,
        "fainted": faint_result.get("fainted", False),
        "faint_detail": faint_result,
    }


def _check_energy_cost(attached: list[str], required: list[str]) -> dict:
    """
    付与されているエネルギーが必要コストを満たすか確認する。
    「無色」エネルギーはどのタイプでも代用可能。

    Args:
        attached: 付与されているエネルギータイプのリスト
        required: ワザに必要なエネルギータイプのリスト

    Returns:
        {"ok": bool}
    """
    available = attached.copy()

    # まず色指定のエネルギーを消費
    colored_required = [e for e in required if e != "無色"]
    colorless_required = required.count("無色")

    for energy_type in colored_required:
        if energy_type in available:
            available.remove(energy_type)
        else:
            return {"ok": False}

    # 残りで無色コストを満たせるか
    if len(available) < colorless_required:
        return {"ok": False}

    return {"ok": True}


def _calculate_damage(attack, attacker, defender) -> int:
    """
    ダメージを計算する。
    - attack.descriptionに"ダメカン"や"ダメージカウンター"が含まれる場合はカウンター型とみなす
    - それ以外は通常ダメージ（弱点×2、抵抗力-30）

    Returns:
        最終ダメージ（10の倍数）
    """
    base_damage = attack.damage

    # ダメージカウンター型の判定（descriptionで簡易判定）
    description = attack.description or ""
    is_counter_type = ("ダメカン" in description or "ダメージカウンター" in description)

    if is_counter_type:
        # ダメージカウンター型: 弱点・抵抗力の計算なし
        return base_damage

    # 通常ダメージ: 弱点・抵抗力を計算
    attacker_type = attacker.card.type or ""
    final_damage = base_damage

    # 弱点チェック（×2）
    if defender.card.weakness and defender.card.weakness == attacker_type:
        final_damage *= 2

    # 抵抗力チェック（-30）
    if defender.card.resistance and defender.card.resistance.type == attacker_type:
        final_damage -= 30
        if final_damage < 0:
            final_damage = 0

    return final_damage


# ============================================================
# 効果処理エンジン
# ============================================================

def apply_effect_steps(steps: list, ctx: EffectContext) -> None:
    """
    EffectStep のリストを順番に処理する。

    Args:
        steps: EffectStep のリスト（AttackモデルのeffectStepsフィールド）
        ctx: 効果処理に必要な参照一式
    """
    for step in steps:
        # EffectStep dataclass or dict 両対応
        if isinstance(step, dict):
            effect_type = step.get("type", "")
            params = step.get("params", {})
        else:
            effect_type = step.type
            params = step.params

        apply_atomic_effect(effect_type, params, ctx)


def apply_atomic_effect(effect_type: str, params: dict, ctx: EffectContext) -> None:
    """
    原子効果を1つ処理する。

    Args:
        effect_type: AtomicEffectType の値（文字列）
        params: 効果のパラメータ辞書
        ctx: EffectContext
    """
    match effect_type:

        # ---- 状態異常 ----
        case "poison":
            ctx.defender.special_condition = SpecialCondition.POISONED
            ctx.game_state.add_log("EFFECT", f"{ctx.defender.card.name}がどく状態になった")

        case "burn":
            ctx.defender.special_condition = SpecialCondition.BURNED
            ctx.game_state.add_log("EFFECT", f"{ctx.defender.card.name}がやけど状態になった")

        case "paralysis":
            ctx.defender.special_condition = SpecialCondition.PARALYZED
            ctx.game_state.add_log("EFFECT", f"{ctx.defender.card.name}がマヒ状態になった")

        case "sleep":
            ctx.defender.special_condition = SpecialCondition.ASLEEP
            ctx.game_state.add_log("EFFECT", f"{ctx.defender.card.name}がねむり状態になった")

        case "confusion":
            ctx.defender.special_condition = SpecialCondition.CONFUSED
            ctx.game_state.add_log("EFFECT", f"{ctx.defender.card.name}がこんらん状態になった")

        # ---- 移動制限 ----
        case "cant_retreat":
            ctx.defender.special_condition = SpecialCondition.CANT_RETREAT
            ctx.game_state.add_log("EFFECT", f"{ctx.defender.card.name}は逃げられない")

        # ---- ベンチダメージ ----
        case "bench_damage":
            dmg = params.get("damage", 20)
            target = params.get("target", "single")
            bench = ctx.defender_player.bench
            if not bench:
                return
            counters = dmg // 10
            if target == "all":
                for bp in bench:
                    bp.damage_counters += counters
                ctx.game_state.add_log(
                    "EFFECT", f"相手のベンチポケモン全員に{dmg}ダメージ"
                )
            else:
                # CPU/プレイヤー共通：ランダムに1体を選択
                target_pokemon = random.choice(bench)
                target_pokemon.damage_counters += counters
                ctx.game_state.add_log(
                    "EFFECT", f"相手の{target_pokemon.card.name}（ベンチ）に{dmg}ダメージ"
                )

        # ---- 自分へのダメージ ----
        case "self_damage":
            dmg = params.get("damage", 20)
            ctx.attacker.damage_counters += dmg // 10
            ctx.game_state.add_log("EFFECT", f"{ctx.attacker.card.name}に{dmg}の自傷ダメージ")

        # ---- ダメージ軽減（次に受けるダメージ）----
        case "damage_reduce":
            value = params.get("value", 30)
            ctx.attacker.damage_reduction_next = getattr(ctx.attacker, "damage_reduction_next", 0) + value
            ctx.game_state.add_log("EFFECT", f"{ctx.attacker.card.name}の次のダメージを{value}軽減")

        # ---- 回復 ----
        case "heal_self":
            hp = params.get("hp", 30)
            healed = min(ctx.attacker.damage_counters, hp // 10)
            ctx.attacker.damage_counters -= healed
            ctx.game_state.add_log("EFFECT", f"{ctx.attacker.card.name}のHPが{healed * 10}回復")

        case "heal_bench":
            hp = params.get("hp", 30)
            filter_type = params.get("filter_type")
            bench = ctx.attacker_player.bench
            for bp in bench:
                if filter_type and bp.card.type != filter_type:
                    continue
                healed = min(bp.damage_counters, hp // 10)
                bp.damage_counters -= healed
            ctx.game_state.add_log("EFFECT", f"ベンチポケモンのHPが{hp}回復")

        # ---- 山札・手札操作 ----
        case "draw":
            count = params.get("count", 1)
            drawn = 0
            for _ in range(count):
                if ctx.attacker_player.deck:
                    card = ctx.attacker_player.deck.pop(0)
                    ctx.attacker_player.hand.append(card)
                    drawn += 1
            ctx.game_state.add_log("EFFECT", f"カードを{drawn}枚引いた")

        case "discard_hand":
            count = params.get("count", 1)
            optional = params.get("optional", False)
            # CPUは常に実行、プレイヤーはoptionalでも実行（UI側で選択）
            discarded = 0
            for _ in range(min(count, len(ctx.attacker_player.hand))):
                card = ctx.attacker_player.hand.pop()
                ctx.attacker_player.discard_pile.append(card)
                discarded += 1
            ctx.game_state.add_log("EFFECT", f"手札を{discarded}枚トラッシュした")

        case "search_pokemon":
            # 山札から最初のポケモンカードを手札に
            deck = ctx.attacker_player.deck
            for i, card in enumerate(deck):
                if card.card_type == "pokemon":
                    ctx.attacker_player.hand.append(deck.pop(i))
                    ctx.game_state.add_log("EFFECT", f"山札から{card.name}を手札に加えた")
                    break

        case "search_energy":
            energy_type = params.get("energy_type")
            to = params.get("to", "hand")
            deck = ctx.attacker_player.deck
            for i, card in enumerate(deck):
                if card.card_type != "energy":
                    continue
                if energy_type and card.type != energy_type:
                    continue
                if to == "bench":
                    # ベンチの最初のポケモンに付ける
                    if ctx.attacker_player.bench:
                        ctx.attacker_player.bench[0].attached_energy.append(
                            card.type or "無色"
                        )
                        ctx.game_state.add_log(
                            "EFFECT",
                            f"山札から{card.name}をベンチの"
                            f"{ctx.attacker_player.bench[0].card.name}に付けた",
                        )
                else:
                    ctx.attacker_player.hand.append(card)
                    ctx.game_state.add_log("EFFECT", f"山札から{card.name}を手札に加えた")
                deck.pop(i)
                break

        # ---- エネルギー操作 ----
        case "discard_energy":
            count = params.get("count", 1)
            source = params.get("from", "self")
            target_pokemon = ctx.attacker if source == "self" else ctx.defender
            removed = 0
            for _ in range(min(count, len(target_pokemon.attached_energy))):
                removed_energy = target_pokemon.attached_energy.pop()
                ctx.attacker_player.discard_pile.append(removed_energy)
                removed += 1
            ctx.game_state.add_log("EFFECT", f"エネルギーを{removed}枚トラッシュした")

        # ---- コントロール ----
        case "cant_attack":
            ctx.attacker.cant_attack_next_turn = True
            ctx.game_state.add_log("EFFECT", f"{ctx.attacker.card.name}は次の番ワザが使えない")

        # ---- コインフリップ（条件分岐）----
        case "coin_flip":
            result = random.random() < 0.5  # True = オモテ
            coin_label = "オモテ" if result else "ウラ"
            ctx.game_state.add_log("EFFECT", f"コイン: {coin_label}")
            next_step = params.get("on_heads") if result else params.get("on_tails")
            if next_step:
                apply_atomic_effect(next_step["type"], next_step.get("params", {}), ctx)

        # ---- 固有効果 ----
        case "custom":
            custom_id = params.get("id", "")
            ctx.game_state.add_log("EFFECT", f"固有効果 [{custom_id}] は未実装")

        case _:
            ctx.game_state.add_log("EFFECT", f"未対応の効果タイプ: {effect_type}")
