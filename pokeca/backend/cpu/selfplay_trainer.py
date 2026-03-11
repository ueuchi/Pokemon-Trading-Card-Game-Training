from __future__ import annotations

from pathlib import Path
from typing import Callable

from stable_baselines3.common.vec_env import SubprocVecEnv

from cpu.battle_env import EngineBattleAdapter, PokemonBattleEnv
from cpu.ppo_agent import PPOAgent


def _make_env(
    seed: int,
    opponent_mode: str,
    opponent_model_path: str | None,
):
    def _init() -> PokemonBattleEnv:
        return PokemonBattleEnv(
            adapter_factory=lambda: EngineBattleAdapter(
                controlled_player_id="player1",
                opponent_mode=opponent_mode,
                opponent_model_path=opponent_model_path,
                random_seed=seed,
            )
        )

    return _init


def _build_vec_env(
    n_envs: int,
    opponent_mode: str,
    opponent_model_path: str | None,
) -> SubprocVecEnv:
    env_fns = [_make_env(i, opponent_mode, opponent_model_path) for i in range(n_envs)]
    return SubprocVecEnv(env_fns)


def train_with_selfplay(
    output_dir: str = "backend/cpu/models",
    n_envs: int = 8,
    phase1_timesteps: int = 500_000,
    phase2_timesteps: int = 1_000_000,
) -> Path:
    """Two-phase training.

    Phase1: train against heuristic CPU
    Phase2: self-play against snapshot models
    """

    model_dir = Path(output_dir)
    model_dir.mkdir(parents=True, exist_ok=True)

    # Phase1
    phase1_env = _build_vec_env(n_envs=n_envs, opponent_mode="heuristic", opponent_model_path=None)
    agent = PPOAgent(env=phase1_env)
    agent.train(total_timesteps=phase1_timesteps)
    phase1_model_path = model_dir / "ppo_phase1"
    agent.save(str(phase1_model_path))
    phase1_env.close()

    # Phase2 self-play: repeatedly train against previous snapshot
    remaining = phase2_timesteps
    chunk = 200_000
    snapshot_path = str(phase1_model_path)

    # Recreate a fresh agent with phase1 weights to avoid stale vec env reference
    current_env = _build_vec_env(n_envs=n_envs, opponent_mode="model", opponent_model_path=snapshot_path)
    selfplay_agent = PPOAgent(env=current_env, model_path=snapshot_path)

    round_idx = 1
    while remaining > 0:
        train_steps = min(chunk, remaining)
        selfplay_agent.train(total_timesteps=train_steps)

        snapshot = model_dir / f"ppo_selfplay_round_{round_idx}"
        selfplay_agent.save(str(snapshot))
        snapshot_path = str(snapshot)

        remaining -= train_steps
        round_idx += 1

        if remaining > 0:
            current_env.close()
            current_env = _build_vec_env(
                n_envs=n_envs,
                opponent_mode="model",
                opponent_model_path=snapshot_path,
            )
            selfplay_agent.model.set_env(current_env)

    final_path = model_dir / "ppo_final"
    selfplay_agent.save(str(final_path))
    current_env.close()
    return final_path


if __name__ == "__main__":
    path = train_with_selfplay()
    print(f"training finished: {path}")
