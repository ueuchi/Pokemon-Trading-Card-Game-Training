"""CPU実行ランタイム

目的:
- 現行バトルでCPUを確実に自動実行する
- 将来のCPU実装（PPO等）を戦略差し替えで拡張しやすくする
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Protocol

from cpu.cpu_ai import CpuAI, CpuDifficulty
from engine.actions.attack import _check_energy_cost
from engine.actions.faint import send_to_active_from_bench
from engine.turn.turn_manager import end_turn


class CpuPolicy(Protocol):
    """CPU戦略の最小インターフェース。"""

    def play_turn(self, game_state) -> list[dict]:
        ...


class RuleBasedCpuPolicy:
    """既存のルールベースCPUを使う戦略。"""

    def __init__(self, player_id: str = "player2", difficulty: CpuDifficulty = CpuDifficulty.NORMAL) -> None:
        self.player_id = player_id
        self.ai = CpuAI(difficulty, player_id=player_id)

    def play_turn(self, game_state) -> list[dict]:
        return self.ai.take_turn(game_state)


@dataclass
class RulePlusWeights:
    # サイド不利時の攻勢補正。
    side_behind: float = 1.0
    # 攻撃可能時の攻勢補正。
    can_attack: float = 1.0
    # 相手HPが低い時の詰め補正。
    opponent_low_hp: float = 1.0
    # 自分HPが低い時の守勢補正（減点）。
    self_low_hp_penalty: float = 1.0


class EnhancedRuleBasedCpuPolicy:
    """強化ルールベース戦略。

    方針:
    - まず HARD 思考でより攻撃的に行動
    - 不整合や停滞時は NORMAL 思考へフォールバック
    """

    def __init__(
        self,
        player_id: str = "player2",
        weights: RulePlusWeights | None = None,
        hard_threshold: float = 2.0,
    ) -> None:
        self.player_id = player_id
        self.hard_ai = CpuAI(CpuDifficulty.HARD, player_id=player_id)
        self.normal_ai = CpuAI(CpuDifficulty.NORMAL, player_id=player_id)
        self.weights = weights or RulePlusWeights()
        self.hard_threshold = hard_threshold

    def play_turn(self, game_state) -> list[dict]:
        actions: list[dict] = []
        before_turn = game_state.current_turn
        before_player = game_state.current_player_id

        # 盤面の攻勢/守勢を見て、先に使う戦略を選ぶ。
        primary_ai, secondary_ai, primary_name, score = self._select_policy_order(game_state)
        actions.append(
            {
                "action": "CPU_RULE_PLUS_SELECT",
                "success": True,
                "message": (
                    f"rule_plus: primary={primary_name}"
                    f" score={score:.2f} threshold={self.hard_threshold:.2f}"
                ),
            }
        )

        primary_actions = primary_ai.take_turn(game_state)
        actions.extend(primary_actions)

        # 同一ターンでCPU手番が進んでいなければ、NORMALで再試行する。
        still_cpu_turn = (
            (not game_state.is_game_over)
            and game_state.current_player_id == self.player_id
            and game_state.current_turn == before_turn
            and before_player == self.player_id
        )
        if still_cpu_turn:
            actions.append({
                "action": "CPU_RULE_PLUS_RECOVERY",
                "success": True,
                "message": "primary戦略で停滞したためsecondary戦略で再試行",
            })
            actions.extend(secondary_ai.take_turn(game_state))

        # それでも停滞した場合は強制的にターンを終えて進行停止を防ぐ。
        stuck_after_retry = (
            (not game_state.is_game_over)
            and game_state.current_player_id == self.player_id
            and game_state.current_turn == before_turn
            and before_player == self.player_id
        )
        if stuck_after_retry:
            end_result = end_turn(game_state)
            actions.append({"action": "CPU_FORCE_END_TURN", **end_result})

        return actions

    def _select_policy_order(self, game_state):
        player = game_state.get_player(self.player_id)
        opponent = game_state.get_opponent_of(self.player_id)

        # 攻勢判断スコア。高いほどHARDを優先。
        score = 0.0

        # 追いかけている時は攻撃的に。
        if player.prize_remaining > opponent.prize_remaining:
            score += self.weights.side_behind

        if player.has_active and opponent.has_active:
            my_active = player.active_pokemon
            opp_active = opponent.active_pokemon

            # 攻撃可能ならHARD優先。
            can_attack = any(
                _check_energy_cost(my_active.attached_energy, atk.energy).get("ok")
                for atk in my_active.card.attacks
            )
            if can_attack:
                score += self.weights.can_attack

            # 相手HPが低いなら詰めを狙う。
            if opp_active.current_hp <= 40:
                score += self.weights.opponent_low_hp

            # 自分HPが低くベンチがあるなら安全重視。
            if my_active.current_hp <= 30 and player.has_bench_pokemon:
                score -= self.weights.self_low_hp_penalty

        if score >= self.hard_threshold:
            return self.hard_ai, self.normal_ai, "hard", score
        return self.normal_ai, self.hard_ai, "normal", score


class PpoCpuPolicy:
    """学習済みPPOモデルで行動する戦略。"""

    def __init__(self, model_path: str, player_id: str = "player2") -> None:
        self.player_id = player_id
        self.model_path = model_path
        self._player = None

    def _get_player(self):
        # stable-baselines3依存を遅延ロードし、通常運用を軽く保つ。
        if self._player is None:
            from cpu.game_integration import CPUPlayer

            self._player = CPUPlayer(model_path=self.model_path, player_id=self.player_id)
        return self._player

    def play_turn(self, game_state) -> list[dict]:
        player = self._get_player()
        return player.play_turn(game_state)


class CpuRuntime:
    """CPUの実行窓口。

    fixed_mode を指定するとそのモードを固定で使用する（env var より優先）。
    指定しない場合は env var (CPU_AI_MODE) を参照する。
    """

    def __init__(
        self,
        player_id: str = "player2",
        fixed_mode: str | None = None,
        fixed_model_path: str | None = None,
    ) -> None:
        self.player_id = player_id
        self._fixed_mode = fixed_mode
        self._fixed_model_path = fixed_model_path
        self._policy: CpuPolicy = RuleBasedCpuPolicy(player_id=player_id)
        self._policy_key: tuple[str, str, str, str] = ("heuristic", "", "", "")

    @staticmethod
    def _load_rule_plus_config() -> tuple[RulePlusWeights, float]:
        """rule_plus の重み設定を環境変数から読み込む。"""
        default_weights = RulePlusWeights()
        threshold = 2.0

        # 例: CPU_RULE_PLUS_WEIGHTS='{"side_behind":1.2,"can_attack":1.5}'
        weights_raw = os.getenv("CPU_RULE_PLUS_WEIGHTS", "").strip()
        if weights_raw:
            try:
                data = json.loads(weights_raw)
                default_weights = RulePlusWeights(
                    side_behind=float(data.get("side_behind", default_weights.side_behind)),
                    can_attack=float(data.get("can_attack", default_weights.can_attack)),
                    opponent_low_hp=float(data.get("opponent_low_hp", default_weights.opponent_low_hp)),
                    self_low_hp_penalty=float(data.get("self_low_hp_penalty", default_weights.self_low_hp_penalty)),
                )
            except Exception:
                # 設定不正時はデフォルト継続。
                pass

        threshold_raw = os.getenv("CPU_RULE_PLUS_HARD_THRESHOLD", "").strip()
        if threshold_raw:
            try:
                threshold = float(threshold_raw)
            except ValueError:
                pass

        return default_weights, threshold

    def _resolve_policy(self) -> CpuPolicy:
        mode = (self._fixed_mode or os.getenv("CPU_AI_MODE", "heuristic")).lower().strip()
        model_path = (self._fixed_model_path or os.getenv("CPU_AI_MODEL_PATH", "")).strip()
        weights_raw = os.getenv("CPU_RULE_PLUS_WEIGHTS", "").strip()
        threshold_raw = os.getenv("CPU_RULE_PLUS_HARD_THRESHOLD", "").strip()
        key = (mode, model_path, weights_raw, threshold_raw)

        if key == self._policy_key:
            return self._policy

        if mode == "easy":
            self._policy = RuleBasedCpuPolicy(player_id=self.player_id, difficulty=CpuDifficulty.EASY)
        elif mode == "hard":
            self._policy = EnhancedRuleBasedCpuPolicy(player_id=self.player_id)
        elif mode in ("rule_plus", "heuristic_plus"):
            weights, threshold = self._load_rule_plus_config()
            self._policy = EnhancedRuleBasedCpuPolicy(
                player_id=self.player_id,
                weights=weights,
                hard_threshold=threshold,
            )
        elif mode in ("ppo", "ml") and model_path:
            self._policy = PpoCpuPolicy(model_path=model_path, player_id=self.player_id)
        else:
            self._policy = RuleBasedCpuPolicy(player_id=self.player_id)

        self._policy_key = key
        return self._policy

    def play_turn(self, game_state) -> list[dict]:
        policy = self._resolve_policy()

        try:
            actions = policy.play_turn(game_state)
        except Exception as e:
            # CPU停止を避けるため、失敗時は必ずルールベースへフォールバック。
            fallback = RuleBasedCpuPolicy(player_id=self.player_id)
            actions = [{
                "action": "CPU_MODEL_FALLBACK",
                "success": False,
                "message": f"CPU戦略エラーのため通常CPUへ切替: {e}",
            }]
            actions.extend(fallback.play_turn(game_state))
            self._policy = fallback
            self._policy_key = ("heuristic", "", "", "")

        self._replace_active_if_needed(game_state, actions)
        return actions

    def _replace_active_if_needed(self, game_state, actions: list[dict]) -> None:
        player = game_state.get_player(self.player_id)
        if player.has_active or not player.has_bench_pokemon or game_state.is_game_over:
            return

        # バトル場が空なら、最もHPが高いベンチを自動で前に出す。
        best_index = max(range(len(player.bench)), key=lambda i: player.bench[i].current_hp)
        replace = send_to_active_from_bench(game_state, self.player_id, best_index)
        actions.append({"action": "CPU_REPLACE_ACTIVE", **replace})
