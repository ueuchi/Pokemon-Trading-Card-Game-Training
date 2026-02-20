"""
プレイヤー状態モデル
対戦中の各プレイヤーの状態を管理する
"""
from dataclasses import dataclass, field
from typing import List, Optional
from models.card import PokemonCard
from engine.models.game_enums import SpecialCondition


@dataclass
class ActivePokemon:
    """
    バトル場に出ているポケモンの状態
    カード情報に加え、ゲーム中の状態（HPダメージ、エネルギー、特殊状態）を持つ
    """
    card: PokemonCard
    damage_counters: int = 0          # 受けているダメージカウンター数（10ダメージ = 1カウンター）
    attached_energy: List[str] = field(default_factory=list)  # 付与されているエネルギータイプのリスト
    special_condition: SpecialCondition = SpecialCondition.NONE
    turns_in_play: int = 0            # 場に出てから経過したターン数（進化制限判定用）

    @property
    def current_hp(self) -> int:
        """現在のHP（最大HP - 受けたダメージ）"""
        base_hp = self.card.hp or 0
        return base_hp - (self.damage_counters * 10)

    @property
    def is_fainted(self) -> bool:
        """きぜつしているか"""
        return self.current_hp <= 0

    @property
    def energy_count(self) -> int:
        """付与されているエネルギーの総数"""
        return len(self.attached_energy)


@dataclass
class BenchPokemon:
    """
    ベンチに出ているポケモンの状態
    """
    card: PokemonCard
    damage_counters: int = 0
    attached_energy: List[str] = field(default_factory=list)
    special_condition: SpecialCondition = SpecialCondition.NONE
    turns_in_play: int = 0

    @property
    def current_hp(self) -> int:
        base_hp = self.card.hp or 0
        return base_hp - (self.damage_counters * 10)

    @property
    def is_fainted(self) -> bool:
        return self.current_hp <= 0

    @property
    def energy_count(self) -> int:
        return len(self.attached_energy)


@dataclass
class PlayerState:
    """
    プレイヤーの対戦状態全体を管理するクラス

    Attributes:
        player_id: プレイヤー識別子（"player1" or "player2"）
        deck: 山札（残りのカードリスト）
        hand: 手札
        active_pokemon: バトル場のポケモン（Noneの場合はバトル場が空）
        bench: ベンチのポケモンリスト（最大5枚）
        prize_cards: サイドカード（残り枚数）
        discard_pile: トラッシュ
        energy_attached_this_turn: このターンにエネルギーを付与したか
        supporter_used_this_turn: このターンにサポートを使用したか
        retreated_this_turn: このターンに逃げたか
        mulligans: このプレイヤーがマリガンした回数
    """
    player_id: str
    deck: List[PokemonCard] = field(default_factory=list)
    hand: List[PokemonCard] = field(default_factory=list)
    active_pokemon: Optional[ActivePokemon] = None
    bench: List[BenchPokemon] = field(default_factory=list)
    prize_cards: List[PokemonCard] = field(default_factory=list)
    discard_pile: List[PokemonCard] = field(default_factory=list)
    energy_attached_this_turn: bool = False
    supporter_used_this_turn: bool = False
    retreated_this_turn: bool = False
    mulligans: int = 0

    @property
    def has_active(self) -> bool:
        """バトル場にポケモンがいるか"""
        return self.active_pokemon is not None

    @property
    def bench_count(self) -> int:
        """ベンチのポケモン数"""
        return len(self.bench)

    @property
    def bench_is_full(self) -> bool:
        """ベンチが満員（5枚）か"""
        return self.bench_count >= 5

    @property
    def prize_remaining(self) -> int:
        """残りサイドカード枚数"""
        return len(self.prize_cards)

    @property
    def deck_count(self) -> int:
        """山札の残り枚数"""
        return len(self.deck)

    @property
    def has_basic_in_hand(self) -> bool:
        """手札にたねポケモンがあるか（マリガン判定用）"""
        return any(c.evolution_stage == "たね" for c in self.hand)

    @property
    def has_bench_pokemon(self) -> bool:
        """ベンチにポケモンがいるか"""
        return len(self.bench) > 0

    def reset_turn_flags(self):
        """ターン開始時にターン制限フラグをリセット"""
        self.energy_attached_this_turn = False
        self.supporter_used_this_turn = False
        self.retreated_this_turn = False

    def increment_turns_in_play(self):
        """場に出ている全ポケモンのturns_in_playをインクリメント（ターン終了時）"""
        if self.active_pokemon:
            self.active_pokemon.turns_in_play += 1
        for bench_mon in self.bench:
            bench_mon.turns_in_play += 1
