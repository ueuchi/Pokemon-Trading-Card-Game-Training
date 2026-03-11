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


class AtomicEffectType(str, Enum):
    """原子効果の種別（1ワザ内の最小効果単位）"""

    # ダメージ系
    BENCH_DAMAGE    = "bench_damage"       # ベンチのポケモンにダメージ
    SELF_DAMAGE     = "self_damage"        # 自分のバトルポケモンにダメージ
    EXTRA_DAMAGE    = "extra_damage"       # 条件付き追加ダメージ
    DAMAGE_REDUCE   = "damage_reduce"      # 次に受けるダメージを軽減

    # 状態異常系
    POISON          = "poison"             # どく
    BURN            = "burn"               # やけど
    PARALYSIS       = "paralysis"          # マヒ
    SLEEP           = "sleep"              # ねむり
    CONFUSION       = "confusion"          # こんらん
    CANT_RETREAT    = "cant_retreat"       # 逃げられない

    # 回復系
    HEAL_SELF       = "heal_self"          # 自分のバトルポケモンを回復
    HEAL_BENCH      = "heal_bench"         # ベンチポケモンを回復

    # 山札・手札操作系
    DRAW            = "draw"               # 山札からN枚引く
    DISCARD_HAND    = "discard_hand"       # 手札からN枚捨てる
    SEARCH_POKEMON  = "search_pokemon"     # 山札からポケモンをサーチして手札に
    SEARCH_ENERGY   = "search_energy"      # 山札からエネルギーをサーチ

    # エネルギー操作系
    ATTACH_ENERGY   = "attach_energy"      # エネルギーをポケモンに付ける
    DISCARD_ENERGY  = "discard_energy"     # 付いているエネルギーを捨てる

    # コントロール系
    CANT_ATTACK     = "cant_attack"        # 次の自分の番ワザが使えない

    # 条件分岐
    COIN_FLIP       = "coin_flip"          # コイン → オモテ/ウラで別効果を発動

    # 個別実装が必要な固有効果
    CUSTOM          = "custom"             # カード固有の特殊処理
