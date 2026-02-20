"""
ゲームエンジン共通Enum定義
"""
from enum import Enum


class EvolutionStage(str, Enum):
    """進化段階"""
    BASIC = "たね"
    STAGE1 = "1 進化"
    STAGE2 = "2 進化"


class GamePhase(str, Enum):
    """ゲームフェーズ"""
    SETUP = "setup"          # 対戦前準備
    PLAYER1_TURN = "player1_turn"
    PLAYER2_TURN = "player2_turn"
    GAME_OVER = "game_over"


class TurnPhase(str, Enum):
    """ターン内フェーズ"""
    DRAW = "draw"            # ドローフェーズ
    MAIN = "main"            # メインフェーズ（ポケモン配置・エネルギー・トレーナー等）
    ATTACK = "attack"        # 攻撃宣言済み
    END = "end"              # ターン終了


class SpecialCondition(str, Enum):
    """特殊状態（Phase 9以降で実装）"""
    NONE = "none"
    POISONED = "poisoned"        # どく
    BURNED = "burned"            # やけど
    CONFUSED = "confused"        # こんらん
    PARALYZED = "paralyzed"      # まひ
    ASLEEP = "asleep"            # ねむり
    CANT_RETREAT = "cant_retreat"  # 逃げられない


class Zone(str, Enum):
    """ポケモンのゾーン"""
    DECK = "deck"
    HAND = "hand"
    ACTIVE = "active"      # バトル場
    BENCH = "bench"        # ベンチ
    DISCARD = "discard"    # トラッシュ
    PRIZE = "prize"        # サイド


class DamageType(str, Enum):
    """攻撃のダメージ種別"""
    NORMAL = "normal"          # 通常ダメージ（弱点・抵抗力計算あり）
    COUNTER = "counter"        # ダメージカウンター型（計算なし）
