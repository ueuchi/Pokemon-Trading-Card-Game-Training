from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Protocol, Set
import random

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from cpu.cpu_ai import CpuAI, CpuDifficulty
from engine.actions.attach_energy import attach_energy
from engine.actions.attack import _check_energy_cost, declare_attack
from engine.actions.evolve import evolve_active, evolve_bench
from engine.actions.faint import send_to_active_from_bench
from engine.actions.place_pokemon import place_to_active, place_to_bench
from engine.actions.retreat import retreat
from engine.actions.trainer import use_goods, use_stadium, use_supporter
from engine.models.game_state import GameState
from engine.setup.game_setup import place_initial_pokemon, setup_game, start_game
from engine.turn.turn_manager import begin_turn, end_turn
from models.card import Attack, PokemonCard


ACTION_SIZE = 20
OBS_SIZE = 128


class BattleInterface(Protocol):
    """Interface for connecting battle logic and RL environment.

    Required methods:
      get_state() -> np.ndarray
        Returns float32 vector of shape (128,) from the controlled player's perspective.

      get_valid_actions() -> set[int]
        Returns valid action IDs in [0, 19] for the current controlled turn.

      apply_action(action_id: int) -> ActionOutcome
        Applies one action and advances game flow as needed.

      is_over() -> bool
        Returns whether the game has finished.
    """

    def get_state(self) -> np.ndarray:
        ...

    def get_valid_actions(self) -> Set[int]:
        ...

    def apply_action(self, action_id: int) -> "ActionOutcome":
        ...

    def is_over(self) -> bool:
        ...


@dataclass
class ActionOutcome:
    success: bool
    invalid: bool
    message: str
    side_taken: int = 0
    opponent_hp_delta_norm: float = 0.0
    self_fainted: bool = False
    win: bool = False
    lose: bool = False


class PokemonBattleEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(
        self,
        adapter_factory: Callable[[], BattleInterface],
        invalid_action_penalty: float = -0.1,
    ):
        super().__init__()
        self.adapter_factory = adapter_factory
        self.adapter: Optional[BattleInterface] = None
        self.invalid_action_penalty = invalid_action_penalty

        self.observation_space = spaces.Box(
            low=-1.0,
            high=1.0,
            shape=(OBS_SIZE,),
            dtype=np.float32,
        )
        self.action_space = spaces.Discrete(ACTION_SIZE)

    def reset(self, *, seed: Optional[int] = None, options: Optional[dict] = None):
        super().reset(seed=seed)
        self.adapter = self.adapter_factory()
        obs = self.adapter.get_state()
        return obs.astype(np.float32), {}

    def step(self, action: int):
        if self.adapter is None:
            raise RuntimeError("Environment not initialized. Call reset() first.")

        valid_actions = self.adapter.get_valid_actions()
        if action not in valid_actions:
            reward = self.invalid_action_penalty
            terminated = self.adapter.is_over()
            obs = self.adapter.get_state()
            info = {
                "invalid_action": True,
                "valid_actions": sorted(valid_actions),
            }
            return obs, reward, terminated, False, info

        outcome = self.adapter.apply_action(action)
        if outcome.invalid or (not outcome.success):
            reward = self.invalid_action_penalty
        else:
            reward = self._calc_reward(outcome)
        terminated = self.adapter.is_over()
        obs = self.adapter.get_state()

        info = {
            "invalid_action": outcome.invalid,
            "message": outcome.message,
        }
        return obs, reward, terminated, False, info

    def _calc_reward(self, outcome: ActionOutcome) -> float:
        reward = 0.0
        reward += float(outcome.side_taken) * 2.0
        reward += float(outcome.opponent_hp_delta_norm) * 0.5
        if outcome.self_fainted:
            reward -= 1.0
        if outcome.win:
            reward += 10.0
        if outcome.lose:
            reward -= 10.0
        return reward


class EngineBattleAdapter(BattleInterface):
    """Adapter that binds existing game engine to the RL interface."""

    def __init__(
        self,
        controlled_player_id: str = "player1",
        opponent_mode: str = "heuristic",
        opponent_model_path: Optional[str] = None,
        random_seed: Optional[int] = None,
        existing_game_state: Optional[GameState] = None,
    ):
        self.controlled_player_id = controlled_player_id
        self.opponent_id = "player2" if controlled_player_id == "player1" else "player1"
        self.opponent_mode = opponent_mode
        self.opponent_model_path = opponent_model_path
        self.random = random.Random(random_seed)

        self.game_state: GameState = existing_game_state if existing_game_state else self._build_new_game()
        self.heuristic_cpu = CpuAI(CpuDifficulty.NORMAL, player_id=self.opponent_id)
        self._opponent_model = None
        self._ensure_controlled_turn()

    def get_state(self) -> np.ndarray:
        return encode_game_state(self.game_state, self.controlled_player_id)

    def get_valid_actions(self) -> Set[int]:
        return list_valid_actions(self.game_state, self.controlled_player_id)

    def is_over(self) -> bool:
        return self.game_state.is_game_over

    def apply_action(self, action_id: int) -> ActionOutcome:
        if self.game_state.is_game_over:
            return ActionOutcome(False, True, "game is over")

        self._ensure_controlled_turn()
        if self.game_state.is_game_over:
            return ActionOutcome(False, True, "game is over")

        valid = self.get_valid_actions()
        if action_id not in valid:
            return ActionOutcome(False, True, f"invalid action: {action_id}")

        before_opp_hp = self._active_hp(self.opponent_id)
        before_my_has_active = self.game_state.get_player(self.controlled_player_id).has_active
        before_side = self.game_state.get_player(self.controlled_player_id).prize_remaining

        result = self._execute_action_for_player(self.controlled_player_id, action_id)
        if not result.get("success", False):
            return ActionOutcome(False, True, result.get("message", "failed"))

        self._ensure_controlled_turn()

        after_opp_hp = self._active_hp(self.opponent_id)
        after_side = self.game_state.get_player(self.controlled_player_id).prize_remaining
        after_my_has_active = self.game_state.get_player(self.controlled_player_id).has_active

        side_taken = max(0, before_side - after_side)
        hp_delta = max(0, before_opp_hp - after_opp_hp)
        hp_norm = float(hp_delta) / 350.0

        win = self.game_state.is_game_over and self.game_state.winner_id == self.controlled_player_id
        lose = self.game_state.is_game_over and self.game_state.winner_id == self.opponent_id
        self_fainted = before_my_has_active and (not after_my_has_active) and (not self.game_state.is_game_over)

        return ActionOutcome(
            success=True,
            invalid=False,
            message=result.get("message", "ok"),
            side_taken=side_taken,
            opponent_hp_delta_norm=max(0.0, min(1.0, hp_norm)),
            self_fainted=self_fainted,
            win=win,
            lose=lose,
        )

    def _build_new_game(self) -> GameState:
        p1 = _build_demo_deck(1000, "lightning")
        p2 = _build_demo_deck(2000, "fire")
        game_state = setup_game(p1, p2)

        self._auto_place_initial(game_state, "player1")
        self._auto_place_initial(game_state, "player2")
        start_game(game_state)
        return game_state

    def _auto_place_initial(self, game_state: GameState, player_id: str) -> None:
        player = game_state.get_player(player_id)
        basics = [c for c in player.hand if getattr(c, "evolution_stage", None) == "たね"]
        if not basics:
            raise RuntimeError("No basic pokemon in hand after mulligan")

        active = max(basics, key=lambda c: c.hp or 0)
        bench = [c for c in basics if c.uid != active.uid][:5]
        place_initial_pokemon(game_state, player_id, active, bench)

    def _ensure_controlled_turn(self) -> None:
        while (not self.game_state.is_game_over) and (self.game_state.current_player_id != self.controlled_player_id):
            self._ensure_active_if_missing(self.game_state.current_player_id)
            if self.game_state.is_game_over:
                return

            if self.opponent_mode == "heuristic":
                self.heuristic_cpu.take_turn(self.game_state)
            elif self.opponent_mode == "model":
                self._play_model_turn(self.game_state.current_player_id)
            else:
                self.heuristic_cpu.take_turn(self.game_state)

            self._ensure_active_if_missing(self.controlled_player_id)
            self._ensure_active_if_missing(self.opponent_id)

    def _play_model_turn(self, player_id: str) -> None:
        model = self._get_opponent_model()
        if model is None:
            self.heuristic_cpu.take_turn(self.game_state)
            return

        if self.game_state.turn_phase.name == "DRAW":
            begin_turn(self.game_state)

        loop_guard = 0
        while (not self.game_state.is_game_over) and self.game_state.current_player_id == player_id and loop_guard < 20:
            loop_guard += 1
            valid = list_valid_actions(self.game_state, player_id)
            if not valid:
                end_turn(self.game_state)
                break

            obs = encode_game_state(self.game_state, player_id)
            action, _ = model.predict(obs, deterministic=True)
            act = int(action)
            if act not in valid:
                act = self.random.choice(sorted(valid))

            result = self._execute_action_for_player(player_id, act)
            if not result.get("success", False):
                fallback = [a for a in sorted(valid) if a != act]
                if not fallback:
                    end_turn(self.game_state)
                    break
                self._execute_action_for_player(player_id, fallback[0])

    def _get_opponent_model(self):
        if self._opponent_model is not None:
            return self._opponent_model
        if not self.opponent_model_path:
            return None
        try:
            from stable_baselines3 import PPO

            self._opponent_model = PPO.load(self.opponent_model_path)
            return self._opponent_model
        except Exception:
            return None

    def _active_hp(self, player_id: str) -> int:
        player = self.game_state.get_player(player_id)
        if not player.has_active:
            return 0
        return max(0, int(player.active_pokemon.current_hp))

    def _ensure_active_if_missing(self, player_id: str) -> None:
        player = self.game_state.get_player(player_id)
        if player.has_active:
            return
        if not player.has_bench_pokemon:
            return
        best_idx = max(range(len(player.bench)), key=lambda i: player.bench[i].current_hp)
        send_to_active_from_bench(self.game_state, player_id, best_idx)

    def _execute_action_for_player(self, player_id: str, action_id: int) -> Dict[str, Any]:
        return execute_action_for_player(self.game_state, player_id, action_id)

    def _play_hand_slot(self, player_id: str, slot: int) -> Dict[str, Any]:
        player = self.game_state.get_player(player_id)
        if slot < 0 or slot >= len(player.hand):
            return {"success": False, "message": "hand slot out of range"}

        card = player.hand[slot]

        evo_stage = getattr(card, "evolution_stage", None)
        card_type = getattr(card, "card_type", "pokemon")

        if evo_stage == "たね":
            if player.has_active:
                return place_to_bench(self.game_state, player_id, card.uid)
            return place_to_active(self.game_state, player_id, card.uid)

        if evo_stage in ("1進化", "2進化"):
            result = evolve_active(self.game_state, player_id, card.uid)
            if result.get("success"):
                return result
            for i in range(len(player.bench)):
                result = evolve_bench(self.game_state, player_id, i, card.uid)
                if result.get("success"):
                    return result
            return result

        if card_type == "energy" or evo_stage == "エネルギー":
            if player.has_active:
                return attach_energy(self.game_state, player_id, card.uid, "active")
            if player.has_bench_pokemon:
                return attach_energy(self.game_state, player_id, card.uid, "bench", 0)
            return {"success": False, "message": "no pokemon to attach energy"}

        if card_type == "trainer":
            trainer_type = getattr(card, "trainer_type", None)
            if trainer_type == "supporter":
                return use_supporter(self.game_state, player_id, card.uid)
            if trainer_type == "goods":
                return use_goods(self.game_state, player_id, card.uid)
            if trainer_type == "stadium":
                return use_stadium(self.game_state, player_id, card.uid)
            return use_goods(self.game_state, player_id, card.uid)

        return {"success": False, "message": "unsupported hand card"}

    def _do_retreat(self, player_id: str, force_bench_index: Optional[int] = None) -> Dict[str, Any]:
        player = self.game_state.get_player(player_id)
        if not player.has_active:
            return {"success": False, "message": "no active pokemon"}
        if not player.has_bench_pokemon:
            return {"success": False, "message": "no bench pokemon"}

        bench_index = force_bench_index
        if bench_index is None:
            bench_index = max(range(len(player.bench)), key=lambda i: player.bench[i].current_hp)

        active = player.active_pokemon
        retreat_cost = active.card.retreat_cost or 0
        if len(active.attached_energy) < retreat_cost:
            return {"success": False, "message": "not enough energy for retreat"}

        energy_indices = list(range(retreat_cost))
        return retreat(self.game_state, player_id, bench_index, energy_indices)

    def _other(self, player_id: str) -> str:
        return "player2" if player_id == "player1" else "player1"


def encode_game_state(game_state: GameState, perspective_player_id: str) -> np.ndarray:
    """Encode board state into a fixed 128 float32 vector."""

    me = game_state.get_player(perspective_player_id)
    opp = game_state.get_opponent_of(perspective_player_id)

    vec = np.zeros(OBS_SIZE, dtype=np.float32)

    vec[0] = min(1.0, game_state.current_turn / 100.0)
    vec[1] = 1.0 if game_state.current_player_id == perspective_player_id else 0.0
    vec[2] = 1.0 if game_state.first_player_id == perspective_player_id else 0.0
    vec[3] = min(1.0, me.prize_remaining / 6.0)
    vec[4] = min(1.0, opp.prize_remaining / 6.0)
    vec[5] = min(1.0, len(me.hand) / 20.0)
    vec[6] = min(1.0, len(opp.hand) / 20.0)
    vec[7] = min(1.0, me.deck_count / 60.0)
    vec[8] = min(1.0, opp.deck_count / 60.0)

    _encode_side(me, vec, start=16)
    _encode_side(opp, vec, start=56)

    # Hand composition summary for up to 10 cards.
    for i in range(min(10, len(me.hand))):
        card = me.hand[i]
        base = 96 + i * 3
        evo = getattr(card, "evolution_stage", "")
        ctype = getattr(card, "card_type", "pokemon")
        vec[base] = 1.0 if evo == "たね" else 0.0
        vec[base + 1] = 1.0 if ctype == "energy" or evo == "エネルギー" else 0.0
        vec[base + 2] = 1.0 if ctype == "trainer" else 0.0

    return vec.astype(np.float32)


def list_valid_actions(game_state: GameState, perspective_player_id: str) -> Set[int]:
    if game_state.is_game_over:
        return set()
    if game_state.current_player_id != perspective_player_id:
        return set()

    player = game_state.get_player(perspective_player_id)
    valid: Set[int] = {19}

    if game_state.turn_phase.name not in ("DRAW", "MAIN"):
        return valid

    # attacks
    if player.has_active and (not game_state.is_first_turn) and (not game_state.attacked_this_turn):
        attacks = player.active_pokemon.card.attacks
        for i in (0, 1):
            if i < len(attacks):
                if _check_energy_cost(player.active_pokemon.attached_energy, attacks[i].energy).get("ok"):
                    valid.add(i)

    # hand slots
    for i in range(min(10, len(player.hand))):
        valid.add(2 + i)

    # retreat
    if player.has_active and player.has_bench_pokemon and (not player.retreated_this_turn):
        active = player.active_pokemon
        if len(active.attached_energy) >= (active.card.retreat_cost or 0):
            valid.add(12)

    # switch / replace
    for i in range(6):
        if i < len(player.bench):
            valid.add(13 + i)

    return valid


def execute_action_for_player(game_state: GameState, player_id: str, action_id: int) -> Dict[str, Any]:
    """Execute one action ID (0..19) on existing engine state."""
    player = game_state.get_player(player_id)

    if game_state.turn_phase.name == "DRAW":
        draw_result = begin_turn(game_state)
        if not draw_result.get("success", False):
            return draw_result

    if action_id in (0, 1):
        result = declare_attack(game_state, player_id, action_id)
        if result.get("success"):
            ensure_active_if_missing(game_state, "player2" if player_id == "player1" else "player1")
            if not game_state.is_game_over:
                end_turn(game_state)
        return result

    if 2 <= action_id <= 11:
        return _play_hand_slot_for_action(game_state, player_id, action_id - 2)

    if action_id == 12:
        return _do_retreat_for_action(game_state, player_id)

    if 13 <= action_id <= 18:
        bench_index = action_id - 13
        if not player.has_active:
            return send_to_active_from_bench(game_state, player_id, bench_index)
        return _do_retreat_for_action(game_state, player_id, force_bench_index=bench_index)

    if action_id == 19:
        return end_turn(game_state)

    return {"success": False, "message": "unknown action"}


def ensure_active_if_missing(game_state: GameState, player_id: str) -> None:
    player = game_state.get_player(player_id)
    if player.has_active or not player.has_bench_pokemon:
        return
    best_idx = max(range(len(player.bench)), key=lambda i: player.bench[i].current_hp)
    send_to_active_from_bench(game_state, player_id, best_idx)


def _play_hand_slot_for_action(game_state: GameState, player_id: str, slot: int) -> Dict[str, Any]:
    player = game_state.get_player(player_id)
    if slot < 0 or slot >= len(player.hand):
        return {"success": False, "message": "hand slot out of range"}

    card = player.hand[slot]
    evo_stage = getattr(card, "evolution_stage", None)
    card_type = getattr(card, "card_type", "pokemon")

    if evo_stage == "たね":
        if player.has_active:
            return place_to_bench(game_state, player_id, card.uid)
        return place_to_active(game_state, player_id, card.uid)

    if evo_stage in ("1進化", "2進化"):
        result = evolve_active(game_state, player_id, card.uid)
        if result.get("success"):
            return result
        for i in range(len(player.bench)):
            result = evolve_bench(game_state, player_id, i, card.uid)
            if result.get("success"):
                return result
        return result

    if card_type == "energy" or evo_stage == "エネルギー":
        if player.has_active:
            return attach_energy(game_state, player_id, card.uid, "active")
        if player.has_bench_pokemon:
            return attach_energy(game_state, player_id, card.uid, "bench", 0)
        return {"success": False, "message": "no pokemon to attach energy"}

    if card_type == "trainer":
        trainer_type = getattr(card, "trainer_type", None)
        if trainer_type == "supporter":
            return use_supporter(game_state, player_id, card.uid)
        if trainer_type == "goods":
            return use_goods(game_state, player_id, card.uid)
        if trainer_type == "stadium":
            return use_stadium(game_state, player_id, card.uid)
        return use_goods(game_state, player_id, card.uid)

    return {"success": False, "message": "unsupported hand card"}


def _do_retreat_for_action(
    game_state: GameState,
    player_id: str,
    force_bench_index: Optional[int] = None,
) -> Dict[str, Any]:
    player = game_state.get_player(player_id)
    if not player.has_active:
        return {"success": False, "message": "no active pokemon"}
    if not player.has_bench_pokemon:
        return {"success": False, "message": "no bench pokemon"}

    bench_index = force_bench_index
    if bench_index is None:
        bench_index = max(range(len(player.bench)), key=lambda i: player.bench[i].current_hp)

    active = player.active_pokemon
    retreat_cost = active.card.retreat_cost or 0
    if len(active.attached_energy) < retreat_cost:
        return {"success": False, "message": "not enough energy for retreat"}

    energy_indices = list(range(retreat_cost))
    return retreat(game_state, player_id, bench_index, energy_indices)


def _encode_side(player, vec: np.ndarray, start: int) -> None:
    idx = start

    # active
    if player.has_active:
        active = player.active_pokemon
        max_hp = max(10, int(active.card.hp or 10))
        vec[idx] = max(0.0, min(1.0, active.current_hp / max_hp))
        vec[idx + 1] = max(0.0, min(1.0, active.energy_count / 8.0))
        vec[idx + 2] = max(0.0, min(1.0, (active.card.retreat_cost or 0) / 4.0))
        vec[idx + 3] = 1.0 if active.special_condition.value != "none" else 0.0
    idx += 4

    # bench x5
    for i in range(5):
        if i < len(player.bench):
            b = player.bench[i]
            max_hp = max(10, int(b.card.hp or 10))
            vec[idx] = max(0.0, min(1.0, b.current_hp / max_hp))
            vec[idx + 1] = max(0.0, min(1.0, b.energy_count / 8.0))
            vec[idx + 2] = max(0.0, min(1.0, (b.card.retreat_cost or 0) / 4.0))
            vec[idx + 3] = 1.0 if b.special_condition.value != "none" else 0.0
        idx += 4


def _build_demo_deck(base_id: int, energy_type: str) -> list[PokemonCard]:
    if energy_type == "fire":
        poke_type = "炎"
        atk1 = Attack(name="scratch", energy=["無色"], energy_count=1, damage=10, description="")
        atk2 = Attack(name="flame", energy=["炎", "炎"], energy_count=2, damage=40, description="")
    else:
        poke_type = "雷"
        atk1 = Attack(name="zap", energy=["雷"], energy_count=1, damage=20, description="")
        atk2 = Attack(name="spark", energy=["雷", "無色"], energy_count=2, damage=30, description="")

    deck: list[PokemonCard] = []

    for i in range(4):
        deck.append(
            PokemonCard(
                id=base_id + i,
                name=f"basic_{energy_type}_{i}",
                card_type="pokemon",
                evolution_stage="たね",
                hp=70,
                type=poke_type,
                attacks=[atk1, atk2],
                retreat_cost=1,
            )
        )

    for i in range(56):
        deck.append(
            PokemonCard(
                id=base_id + 100 + i,
                name=f"{poke_type} energy",
                card_type="energy",
                evolution_stage="エネルギー",
                type=poke_type,
                attacks=[],
                retreat_cost=0,
            )
        )

    return deck
