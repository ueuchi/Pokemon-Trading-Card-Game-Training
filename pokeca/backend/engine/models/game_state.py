"""
ゲーム状態モデル
対戦全体の状態を管理する（メモリ上のみ、DBには保存しない）
"""
import uuid
from dataclasses import dataclass, field
from typing import Optional, List
from engine.models.player_state import PlayerState
from engine.models.game_enums import GamePhase, TurnPhase
from models.card import PokemonCard


@dataclass
class StadiumState:
    """場に出ているスタジアムカードの状態"""
    card: PokemonCard
    played_by: str  # "player1" or "player2"


@dataclass
class GameLog:
    """ゲームログの1エントリ"""
    turn: int
    player_id: str
    action: str
    detail: str = ""


@dataclass
class GameState:
    """
    ゲーム全体の状態を管理するクラス

    Attributes:
        game_id: ゲームの一意ID
        player1: プレイヤー1の状態
        player2: プレイヤー2の状態
        current_turn: 現在のターン数（1始まり）
        current_player_id: 現在のターンのプレイヤーID
        first_player_id: 先行プレイヤーのID
        game_phase: ゲーム全体のフェーズ
        turn_phase: ターン内のフェーズ
        winner_id: 勝者のプレイヤーID（ゲーム終了時にセット）
        stadium: 現在場に出ているスタジアムカード
        logs: ゲームログ
        attacked_this_turn: このターンに攻撃宣言したか
    """
    player1: PlayerState
    player2: PlayerState
    game_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    current_turn: int = 1
    current_player_id: str = "player1"
    first_player_id: str = "player1"
    game_phase: GamePhase = GamePhase.SETUP
    turn_phase: TurnPhase = TurnPhase.DRAW
    winner_id: Optional[str] = None
    stadium: Optional[StadiumState] = None
    logs: List[GameLog] = field(default_factory=list)
    attacked_this_turn: bool = False

    @property
    def current_player(self) -> PlayerState:
        """現在のターンのプレイヤー"""
        return self.player1 if self.current_player_id == "player1" else self.player2

    @property
    def opponent(self) -> PlayerState:
        """現在のターンの相手プレイヤー"""
        return self.player2 if self.current_player_id == "player1" else self.player1

    @property
    def is_game_over(self) -> bool:
        """ゲームが終了しているか"""
        return self.game_phase == GamePhase.GAME_OVER

    @property
    def is_first_turn(self) -> bool:
        """先行プレイヤーの最初のターンか（攻撃禁止判定用）"""
        return self.current_turn == 1 and self.current_player_id == self.first_player_id

    def get_player(self, player_id: str) -> PlayerState:
        """player_idでPlayerStateを取得"""
        if player_id == "player1":
            return self.player1
        elif player_id == "player2":
            return self.player2
        raise ValueError(f"不明なプレイヤーID: {player_id}")

    def get_opponent_of(self, player_id: str) -> PlayerState:
        """指定プレイヤーの相手を取得"""
        return self.player2 if player_id == "player1" else self.player1

    def add_log(self, action: str, detail: str = ""):
        """ゲームログを追加"""
        log = GameLog(
            turn=self.current_turn,
            player_id=self.current_player_id,
            action=action,
            detail=detail
        )
        self.logs.append(log)

    def switch_turn(self):
        """ターンを相手プレイヤーに移行"""
        # 現在のプレイヤーの場のポケモンのturns_in_playをインクリメント
        self.current_player.increment_turns_in_play()

        # プレイヤー切り替え
        self.current_player_id = (
            "player2" if self.current_player_id == "player1" else "player1"
        )
        self.current_turn += 1
        self.turn_phase = TurnPhase.DRAW
        self.attacked_this_turn = False

        # 次のプレイヤーのターンフラグをリセット
        self.current_player.reset_turn_flags()

    def to_dict(self) -> dict:
        """ゲーム状態をAPI応答用の辞書形式に変換"""
        def pokemon_to_dict(p):
            if p is None:
                return None
            return {
                "card_id": p.card.id,
                "name": p.card.name,
                "hp": p.card.hp,
                "current_hp": p.current_hp,
                "damage_counters": p.damage_counters,
                "attached_energy": p.attached_energy,
                "special_condition": p.special_condition.value,
                "turns_in_play": p.turns_in_play,
                "evolution_stage": p.card.evolution_stage,
                "type": p.card.type,
                "attacks": [
                    {
                        "name": a.name,
                        "energy": a.energy,
                        "energy_count": a.energy_count,
                        "damage": a.damage,
                        "description": a.description,
                    }
                    for a in p.card.attacks
                ],
                "retreat_cost": p.card.retreat_cost,
                "weakness": {"type": p.card.weakness.type, "value": p.card.weakness.value} if p.card.weakness else None,
                "resistance": {"type": p.card.resistance.type, "value": p.card.resistance.value} if p.card.resistance else None,
            }

        def player_to_dict(ps: PlayerState):
            return {
                "player_id": ps.player_id,
                "deck_count": ps.deck_count,
                "hand_count": len(ps.hand),
                "hand": [{"card_id": c.id, "name": c.name, "evolution_stage": c.evolution_stage, "type": c.type} for c in ps.hand],
                "active_pokemon": pokemon_to_dict(ps.active_pokemon),
                "bench": [pokemon_to_dict(b) for b in ps.bench],
                "prize_remaining": ps.prize_remaining,
                "discard_count": len(ps.discard_pile),
                "energy_attached_this_turn": ps.energy_attached_this_turn,
                "supporter_used_this_turn": ps.supporter_used_this_turn,
                "retreated_this_turn": ps.retreated_this_turn,
            }

        return {
            "game_id": self.game_id,
            "current_turn": self.current_turn,
            "current_player_id": self.current_player_id,
            "first_player_id": self.first_player_id,
            "game_phase": self.game_phase.value,
            "turn_phase": self.turn_phase.value,
            "winner_id": self.winner_id,
            "is_first_turn": self.is_first_turn,
            "attacked_this_turn": self.attacked_this_turn,
            "stadium": {
                "card_id": self.stadium.card.id,
                "name": self.stadium.card.name,
                "played_by": self.stadium.played_by,
            } if self.stadium else None,
            "player1": player_to_dict(self.player1),
            "player2": player_to_dict(self.player2),
            "logs": [
                {"turn": l.turn, "player_id": l.player_id, "action": l.action, "detail": l.detail}
                for l in self.logs[-20:]  # 直近20件のみ返す
            ],
        }
