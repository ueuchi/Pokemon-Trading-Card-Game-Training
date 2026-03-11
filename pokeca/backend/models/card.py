"""
カードモデル定義（更新版 - dataclass使用）
Pydantic非依存のdataclassで定義する
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from pydantic import BaseModel


@dataclass
class EffectStep:
    """
    1つの原子効果を表すデータ構造。
    複数の EffectStep を組み合わせて1ワザの効果全体を表現する。

    params の主なキー（effect_type ごと）:
      bench_damage:   { "damage": int, "target": "single"|"all" }
      self_damage:    { "damage": int }
      damage_reduce:  { "value": int }
      heal_self:      { "hp": int }
      heal_bench:     { "hp": int, "filter_type": str|None }
      draw:           { "count": int }
      discard_hand:   { "count": int, "optional": bool }
      search_energy:  { "energy_type": str|None, "to": "bench"|"hand" }
      attach_energy:  { "from": "hand"|"deck" }
      discard_energy: { "count": int, "from": "self"|"opponent" }
      coin_flip:      { "on_heads": EffectStep|None, "on_tails": EffectStep|None }
      custom:         { "id": str }
    """
    type: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Attack:
    name: str
    energy: List[str] = field(default_factory=list)
    energy_count: int = 0
    damage: int = 0
    description: str = ""
    effect_steps: List[EffectStep] = field(default_factory=list)


@dataclass
class Ability:
    name: str
    description: str = ""


@dataclass
class Resistance:
    type: str
    value: int = -30


@dataclass
class PokemonCard:
    id: int
    name: str
    card_type: str = "pokemon"

    # デッキ内のユニークインスタンスID（同名カードを区別するため）
    uid: int = 0

    # ポケモン固有
    pokemon_type: str = "normal"          # "normal" | "trainer_pokemon"
    card_rule: Optional[str] = None       # None | "ex" | "mega_ex"
    evolution_stage: Optional[str] = None # "たね" | "1進化" | "2進化"
    evolves_from: Optional[str] = None
    hp: Optional[int] = None
    type: Optional[str] = None
    attacks: List[Attack] = field(default_factory=list)
    ability: Optional[Ability] = None
    weakness: Optional[str] = None        # 弱点タイプ文字列（例: "炎"）
    resistance: Optional[Resistance] = None
    retreat_cost: int = 0

    # エネルギー固有
    energy_type: Optional[str] = None    # "basic" | "special"

    # トレーナー固有
    trainer_type: Optional[str] = None   # "supporter" | "goods" | "stadium"
    is_ace_spec: bool = False
    effect_description: Optional[str] = None

    # 共通
    image_url: Optional[str] = None


# ==================== Pydanticリクエストモデル ====================

class CardCreateRequest(BaseModel):
    """カード作成リクエスト"""
    name: str
    card_type: str = "pokemon"
    image_url: Optional[str] = None
    hp: Optional[int] = None
    type: Optional[str] = None
    evolution_stage: Optional[str] = None
    evolves_from: Optional[str] = None
    retreat_cost: int = 0
    pokemon_type: str = "normal"
    card_rule: Optional[str] = None
    energy_type: Optional[str] = None
    trainer_type: Optional[str] = None
    is_ace_spec: bool = False
    effect_description: Optional[str] = None

    class Config:
        extra = "allow"


class CardUpdateRequest(BaseModel):
    """カード更新リクエスト（全フィールド任意）"""
    name: Optional[str] = None
    card_type: Optional[str] = None
    image_url: Optional[str] = None
    hp: Optional[int] = None
    type: Optional[str] = None
    evolution_stage: Optional[str] = None
    evolves_from: Optional[str] = None
    retreat_cost: Optional[int] = None
    pokemon_type: Optional[str] = None
    card_rule: Optional[str] = None
    energy_type: Optional[str] = None
    trainer_type: Optional[str] = None
    is_ace_spec: Optional[bool] = None
    effect_description: Optional[str] = None

    class Config:
        extra = "allow"