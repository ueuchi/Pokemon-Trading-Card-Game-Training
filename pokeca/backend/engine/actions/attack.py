"""
タスク3-10: 攻撃処理
攻撃宣言・エネルギーコスト確認・ダメージ計算（弱点・抵抗力・ダメージカウンター型）を実装する
"""
from engine.models.game_state import GameState
from engine.models.game_enums import TurnPhase, DamageType
from engine.actions.faint import check_and_process_faint


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
    if defender.card.weakness and defender.card.weakness.type == attacker_type:
        final_damage *= 2

    # 抵抗力チェック（-30）
    if defender.card.resistance and defender.card.resistance.type == attacker_type:
        final_damage -= 30
        if final_damage < 0:
            final_damage = 0

    return final_damage
