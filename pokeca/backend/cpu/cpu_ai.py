"""
CPU思考エンジン（難易度3段階対応）

難易度:
  EASY   - ランダム行動。攻撃できても攻撃しないことがある
  NORMAL - 簡易ルールベース（攻撃できれば攻撃・毎ターンエネルギー付与）
  HARD   - 最大ダメージ優先・KO狙い・進化を活用・HP考慮した交代選択
"""
import random
from enum import Enum
from typing import Optional

from engine.models.game_state import GameState
from engine.actions.place_pokemon import place_to_bench
from engine.actions.evolve import evolve_active, evolve_bench, NEXT_STAGE
from engine.actions.attach_energy import attach_energy
from engine.actions.attack import declare_attack, _check_energy_cost
from engine.actions.faint import send_to_active_from_bench
from engine.turn.turn_manager import begin_turn, end_turn


class CpuDifficulty(str, Enum):
    EASY = "easy"
    NORMAL = "normal"
    HARD = "hard"


class CpuAI:
    """
    難易度に応じた思考ロジックを持つCPU AIクラス。
    player_idはインスタンス生成時またはtake_turn()呼び出し時に決定する。
    """

    def __init__(self, difficulty: CpuDifficulty = CpuDifficulty.NORMAL, player_id: str = "player2"):
        self.difficulty = difficulty
        self.player_id = player_id

    def take_turn(self, game_state: GameState) -> list:
        """CPUが1ターン分の行動をすべて実行する。"""
        if self.difficulty == CpuDifficulty.EASY:
            return self._take_turn_easy(game_state)
        elif self.difficulty == CpuDifficulty.NORMAL:
            return self._take_turn_normal(game_state)
        else:
            return self._take_turn_hard(game_state)

    def choose_active_after_faint(self, game_state: GameState) -> dict:
        """きぜつ後のバトル場交代。難易度に応じた選択をする。"""
        player = game_state.get_player(self.player_id)
        if not player.has_bench_pokemon:
            return {"success": False, "message": "ベンチにポケモンがいません"}
        if self.difficulty == CpuDifficulty.EASY:
            index = random.randrange(len(player.bench))
        elif self.difficulty == CpuDifficulty.NORMAL:
            index = max(range(len(player.bench)), key=lambda i: player.bench[i].current_hp)
        else:
            index = self._best_bench_index_hard(player)
        return send_to_active_from_bench(game_state, self.player_id, index)

    # ===== EASY =====
    def _take_turn_easy(self, game_state: GameState) -> list:
        actions = []
        draw_result = begin_turn(game_state)
        actions.append({"action": "DRAW", **draw_result})
        if not draw_result["success"] or game_state.is_game_over:
            return actions

        player = game_state.get_player(self.player_id)
        if not player.has_active:
            r = self._fill_active(game_state)
            if r:
                actions.append(r)
            if game_state.is_game_over:
                return actions

        if random.random() < 0.5:
            actions.extend(self._fill_bench(game_state))
        if random.random() < 0.5:
            r = self._attach_energy_normal(game_state)
            if r:
                actions.append(r)
        if not game_state.is_first_turn and random.random() < 0.6:
            r = self._attack_random(game_state)
            if r:
                actions.append(r)
                if game_state.is_game_over:
                    return actions

        end_result = end_turn(game_state)
        actions.append({"action": "END_TURN", **end_result})
        return actions

    # ===== NORMAL =====
    def _take_turn_normal(self, game_state: GameState) -> list:
        actions = []
        draw_result = begin_turn(game_state)
        actions.append({"action": "DRAW", **draw_result})
        if not draw_result["success"] or game_state.is_game_over:
            return actions

        player = game_state.get_player(self.player_id)
        if not player.has_active:
            r = self._fill_active(game_state)
            if r:
                actions.append(r)
            if game_state.is_game_over:
                return actions

        actions.extend(self._fill_bench(game_state))
        r = self._attach_energy_normal(game_state)
        if r:
            actions.append(r)

        if not game_state.is_first_turn:
            r = self._attack_best_damage(game_state)
            if r:
                actions.append(r)
                if game_state.is_game_over:
                    return actions

        end_result = end_turn(game_state)
        actions.append({"action": "END_TURN", **end_result})
        return actions

    # ===== HARD =====
    def _take_turn_hard(self, game_state: GameState) -> list:
        actions = []
        draw_result = begin_turn(game_state)
        actions.append({"action": "DRAW", **draw_result})
        if not draw_result["success"] or game_state.is_game_over:
            return actions

        player = game_state.get_player(self.player_id)
        if not player.has_active:
            r = self._fill_active(game_state)
            if r:
                actions.append(r)
            if game_state.is_game_over:
                return actions

        r = self._try_evolve_active(game_state)
        if r:
            actions.append(r)
        actions.extend(self._try_evolve_bench(game_state))
        actions.extend(self._fill_bench_smart(game_state))

        r = self._attach_energy_smart(game_state)
        if r:
            actions.append(r)

        if not game_state.is_first_turn:
            r = self._attack_smart(game_state)
            if r:
                actions.append(r)
                if game_state.is_game_over:
                    return actions

        end_result = end_turn(game_state)
        actions.append({"action": "END_TURN", **end_result})
        return actions

    # ===== 共通ヘルパー =====
    def _fill_active(self, game_state):
        player = game_state.get_player(self.player_id)
        if player.has_active or not player.has_bench_pokemon:
            return None
        index = max(range(len(player.bench)), key=lambda i: player.bench[i].current_hp)
        r = send_to_active_from_bench(game_state, self.player_id, index)
        return {"action": "FILL_ACTIVE", **r}

    def _fill_bench(self, game_state):
        results = []
        player = game_state.get_player(self.player_id)
        for card in list(player.hand):
            if player.bench_is_full:
                break
            if card.evolution_stage == "たね":
                r = place_to_bench(game_state, self.player_id, card.uid)
                if r["success"]:
                    results.append({"action": "PLACE_BENCH", **r})
        return results

    def _fill_bench_smart(self, game_state):
        results = []
        player = game_state.get_player(self.player_id)
        basics = sorted(
            [c for c in player.hand if c.evolution_stage == "たね"],
            key=lambda c: c.hp or 0, reverse=True
        )
        for card in basics:
            if player.bench_is_full:
                break
            r = place_to_bench(game_state, self.player_id, card.uid)
            if r["success"]:
                results.append({"action": "PLACE_BENCH", **r})
        return results

    def _attach_energy_normal(self, game_state):
        player = game_state.get_player(self.player_id)
        if player.energy_attached_this_turn or not player.has_active:
            return None
        energy_cards = [c for c in player.hand if c.evolution_stage == "エネルギー"]
        if not energy_cards:
            return None
        active = player.active_pokemon
        needed = {e for atk in active.card.attacks for e in atk.energy}
        chosen = next((c for c in energy_cards if c.type in needed), energy_cards[0])
        r = attach_energy(game_state, self.player_id, chosen.uid, "active")
        return {"action": "ATTACH_ENERGY", **r}

    def _attach_energy_smart(self, game_state):
        player = game_state.get_player(self.player_id)
        if player.energy_attached_this_turn or not player.has_active:
            return None
        energy_cards = [c for c in player.hand if c.evolution_stage == "エネルギー"]
        if not energy_cards:
            return None
        active = player.active_pokemon
        best_card, min_shortage = None, float("inf")
        for ec in energy_cards:
            for atk in active.card.attacks:
                shortage = _count_shortage(active.attached_energy + [ec.type], atk.energy)
                if shortage < min_shortage:
                    min_shortage = shortage
                    best_card = ec
        chosen = best_card or energy_cards[0]
        r = attach_energy(game_state, self.player_id, chosen.uid, "active")
        return {"action": "ATTACH_ENERGY", **r}

    def _attack_random(self, game_state):
        player = game_state.get_player(self.player_id)
        opponent = game_state.get_opponent_of(self.player_id)
        if not player.has_active or not opponent.has_active:
            return None
        active = player.active_pokemon
        usable = [i for i, atk in enumerate(active.card.attacks)
                  if _check_energy_cost(active.attached_energy, atk.energy)["ok"]]
        if not usable:
            return None
        r = declare_attack(game_state, self.player_id, random.choice(usable))
        return {"action": "ATTACK", **r}

    def _attack_best_damage(self, game_state):
        player = game_state.get_player(self.player_id)
        opponent = game_state.get_opponent_of(self.player_id)
        if not player.has_active or not opponent.has_active:
            return None
        active = player.active_pokemon
        best_i, best_dmg = None, -1
        for i, atk in enumerate(active.card.attacks):
            if _check_energy_cost(active.attached_energy, atk.energy)["ok"] and atk.damage > best_dmg:
                best_dmg, best_i = atk.damage, i
        if best_i is None:
            return None
        r = declare_attack(game_state, self.player_id, best_i)
        return {"action": "ATTACK", **r}

    def _attack_smart(self, game_state):
        player = game_state.get_player(self.player_id)
        opponent = game_state.get_opponent_of(self.player_id)
        if not player.has_active or not opponent.has_active:
            return None
        attacker = player.active_pokemon
        defender = opponent.active_pokemon
        attacker_type = attacker.card.type or ""
        best_i, best_score = None, -1
        for i, atk in enumerate(attacker.card.attacks):
            if not _check_energy_cost(attacker.attached_energy, atk.energy)["ok"]:
                continue
            dmg = atk.damage
            if defender.card.weakness and defender.card.weakness.type == attacker_type:
                dmg *= 2
            if defender.card.resistance and defender.card.resistance.type == attacker_type:
                dmg = max(0, dmg - 30)
            # KOできればボーナス
            score = dmg * 10 if dmg >= defender.current_hp else dmg
            if score > best_score:
                best_score, best_i = score, i
        if best_i is None:
            return None
        r = declare_attack(game_state, self.player_id, best_i)
        return {"action": "ATTACK", **r}

    def _try_evolve_active(self, game_state):
        player = game_state.get_player(self.player_id)
        if not player.has_active:
            return None
        active = player.active_pokemon
        if active.turns_in_play == 0 or game_state.current_turn == 1:
            return None
        next_stage = NEXT_STAGE.get(active.card.evolution_stage)
        if not next_stage:
            return None
        evo_card = next((c for c in player.hand if c.evolution_stage == next_stage), None)
        if not evo_card:
            return None
        r = evolve_active(game_state, self.player_id, evo_card.uid)
        return {"action": "EVOLVE_ACTIVE", **r} if r["success"] else None

    def _try_evolve_bench(self, game_state):
        results = []
        player = game_state.get_player(self.player_id)
        for i, bench_mon in enumerate(player.bench):
            if bench_mon.turns_in_play == 0 or game_state.current_turn == 1:
                continue
            next_stage = NEXT_STAGE.get(bench_mon.card.evolution_stage)
            if not next_stage:
                continue
            evo_card = next((c for c in player.hand if c.evolution_stage == next_stage), None)
            if not evo_card:
                continue
            r = evolve_bench(game_state, self.player_id, i, evo_card.uid)
            if r["success"]:
                results.append({"action": "EVOLVE_BENCH", **r})
        return results

    def _best_bench_index_hard(self, player):
        return max(
            range(len(player.bench)),
            key=lambda i: player.bench[i].energy_count * 100 + player.bench[i].current_hp
        )


# ===== 後方互換（フェーズ3デモ等から呼ばれる） =====
def cpu_take_turn(game_state: GameState) -> list:
    return CpuAI(CpuDifficulty.NORMAL, player_id="player2").take_turn(game_state)

def cpu_choose_active_after_faint(game_state: GameState) -> dict:
    return CpuAI(CpuDifficulty.NORMAL, player_id="player2").choose_active_after_faint(game_state)


# ===== ユーティリティ =====
def _count_shortage(available: list, required: list) -> int:
    avail = available.copy()
    shortage = 0
    for e in [x for x in required if x != "無色"]:
        if e in avail:
            avail.remove(e)
        else:
            shortage += 1
    return shortage + max(0, required.count("無色") - len(avail))
