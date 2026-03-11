from __future__ import annotations

from typing import Optional
import random

from stable_baselines3 import PPO

from cpu.battle_env import (
    encode_game_state,
    execute_action_for_player,
    list_valid_actions,
)
from engine.models.game_state import GameState


class CPUPlayer:
    """Inference wrapper for trained PPO model."""

    def __init__(
        self,
        model_path: str,
        player_id: str = "player2",
        deterministic: bool = True,
    ):
        self.player_id = player_id
        self.model = PPO.load(model_path)
        self.deterministic = deterministic
        self.random = random.Random()

    def decide_action(self, game_state: GameState) -> int:
        """Return one action ID [0..19] for the current game state."""
        valid_actions = list_valid_actions(game_state, self.player_id)
        if not valid_actions:
            return 19

        obs = encode_game_state(game_state, self.player_id)
        action, _ = self.model.predict(obs, deterministic=self.deterministic)
        action_id = int(action)

        if action_id not in valid_actions:
            action_id = self._fallback_action(valid_actions)
        return action_id

    def play_turn(self, game_state: GameState, max_steps: int = 20) -> list[dict]:
        """Run CPU actions until the turn ends or game is over."""
        actions: list[dict] = []
        steps = 0

        while (
            not game_state.is_game_over
            and game_state.current_player_id == self.player_id
            and steps < max_steps
        ):
            steps += 1
            action_id = self.decide_action(game_state)
            result = execute_action_for_player(game_state, self.player_id, action_id)
            actions.append({"action_id": action_id, **result})

            if not result.get("success", False):
                valid_actions = list_valid_actions(game_state, self.player_id)
                fallback = [a for a in sorted(valid_actions) if a != action_id]
                if not fallback:
                    break
                action_id = fallback[0]
                result = execute_action_for_player(game_state, self.player_id, action_id)
                actions.append({"action_id": action_id, "fallback": True, **result})

        return actions

    def _fallback_action(self, valid_actions: set[int]) -> int:
        # Keep fallback deterministic priority while preserving robustness.
        for a in (0, 1, 12, 19):
            if a in valid_actions:
                return a
        return self.random.choice(sorted(valid_actions))
