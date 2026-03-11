from __future__ import annotations

from typing import Optional

import torch as th
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import VecEnv


class PPOAgent:
    def __init__(
        self,
        env: VecEnv,
        model_path: Optional[str] = None,
    ):
        if model_path:
            self.model = PPO.load(model_path, env=env)
        else:
            policy_kwargs = {
                "net_arch": [256, 256],
                "activation_fn": th.nn.ReLU,
            }
            self.model = PPO(
                policy="MlpPolicy",
                env=env,
                learning_rate=3e-4,
                n_steps=2048,
                batch_size=64,
                n_epochs=10,
                policy_kwargs=policy_kwargs,
                verbose=1,
            )

    def train(self, total_timesteps: int) -> None:
        self.model.learn(total_timesteps=total_timesteps)

    def predict(self, obs, deterministic: bool = True) -> int:
        action, _ = self.model.predict(obs, deterministic=deterministic)
        return int(action)

    def save(self, path: str) -> None:
        self.model.save(path)
