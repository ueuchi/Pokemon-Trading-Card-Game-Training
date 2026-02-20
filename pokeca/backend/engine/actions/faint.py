"""
タスク3-11: きぜつ処理
ポケモンのHP0判定・トラッシュ・サイド取得・バトル場交代を実装する
"""
from engine.models.game_state import GameState
from engine.models.game_enums import GamePhase


def check_and_process_faint(game_state: GameState, attacker_id: str) -> dict:
    """
    攻撃後、相手のバトル場ポケモンがきぜつしているか確認し、処理する。

    Args:
        attacker_id: 攻撃したプレイヤーのID

    Returns:
        {"fainted": bool, "message": str, "prize_taken": int, "game_over": bool}
    """
    opponent = game_state.get_opponent_of(attacker_id)
    attacker = game_state.get_player(attacker_id)

    if not opponent.has_active:
        return {"fainted": False, "message": "", "prize_taken": 0, "game_over": False}

    defender = opponent.active_pokemon

    if not defender.is_fainted:
        return {"fainted": False, "message": "", "prize_taken": 0, "game_over": False}

    # きぜつ処理
    fainted_name = defender.card.name

    # きぜつしたポケモンとエネルギーをトラッシュへ
    opponent.discard_pile.append(defender.card)
    opponent.active_pokemon = None

    game_state.add_log("FAINT", f"{fainted_name}がきぜつした")

    # サイドカードの取得（Phase 3では通常ポケモン = 1枚固定）
    prize_count = _get_prize_count(defender.card)
    prizes_taken = []
    for _ in range(prize_count):
        if attacker.prize_cards:
            prize = attacker.prize_cards.pop(0)
            attacker.hand.append(prize)
            prizes_taken.append(prize.name)

    game_state.add_log(
        "TAKE_PRIZE",
        f"{attacker_id}がサイドを{prize_count}枚取得（残り{attacker.prize_remaining}枚）"
    )

    # 勝利条件チェック（サイド全取得）
    if attacker.prize_remaining == 0:
        game_state.game_phase = GamePhase.GAME_OVER
        game_state.winner_id = attacker_id
        game_state.add_log("GAME_OVER", f"{attacker_id}がサイドを全取得して勝利！")
        return {
            "fainted": True,
            "message": f"{fainted_name}がきぜつ。{attacker_id}がサイドを全取得して勝利！",
            "prize_taken": prize_count,
            "game_over": True,
        }

    # 相手のバトル場が空になった場合（ベンチもなければ勝利）
    if not opponent.has_bench_pokemon:
        game_state.game_phase = GamePhase.GAME_OVER
        game_state.winner_id = attacker_id
        game_state.add_log("GAME_OVER", f"相手のバトル場とベンチが空になり{attacker_id}が勝利！")
        return {
            "fainted": True,
            "message": f"{fainted_name}がきぜつ。相手のポケモンがいなくなり{attacker_id}の勝利！",
            "prize_taken": prize_count,
            "game_over": True,
        }

    return {
        "fainted": True,
        "message": f"{fainted_name}がきぜつ。{attacker_id}がサイドを{prize_count}枚取得",
        "prize_taken": prize_count,
        "game_over": False,
        "need_replacement": True,  # 倒されたプレイヤーはポケモンを選ぶ必要がある
    }


def send_to_active_from_bench(
    game_state: GameState,
    player_id: str,
    bench_index: int,
) -> dict:
    """
    バトル場が空の場合に、ベンチからポケモンをバトル場に出す。
    きぜつ後の強制交代に使用する。

    Args:
        player_id: 操作プレイヤーID
        bench_index: バトル場に出すベンチポケモンのインデックス

    Returns:
        {"success": bool, "message": str}
    """
    from engine.models.player_state import ActivePokemon

    player = game_state.get_player(player_id)

    if player.has_active:
        return {"success": False, "message": "バトル場にすでにポケモンがいます"}

    if bench_index < 0 or bench_index >= len(player.bench):
        return {"success": False, "message": f"ベンチインデックス{bench_index}が無効です"}

    bench_mon = player.bench.pop(bench_index)
    player.active_pokemon = ActivePokemon(
        card=bench_mon.card,
        damage_counters=bench_mon.damage_counters,
        attached_energy=bench_mon.attached_energy.copy(),
        special_condition=bench_mon.special_condition,
        turns_in_play=bench_mon.turns_in_play,
    )

    game_state.add_log(
        "SEND_TO_ACTIVE",
        f"{player_id}: {player.active_pokemon.card.name}をバトル場に出した"
    )
    return {
        "success": True,
        "message": f"{player.active_pokemon.card.name}をバトル場に出した"
    }


def _get_prize_count(card) -> int:
    """
    きぜつしたポケモンのサイド取得枚数を返す。
    Phase 3では全て1枚固定（exやVなどの複数枚取得はPhase 9以降で実装）
    """
    return 1
