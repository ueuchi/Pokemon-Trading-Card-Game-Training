"""
データベースモデル定義
"""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class Attack(BaseModel):
    """ワザ情報"""
    name: str
    energy: List[str]
    energy_count: int
    damage: int
    description: str


class Weakness(BaseModel):
    """弱点情報"""
    type: str
    value: str


class Resistance(BaseModel):
    """抵抗力情報"""
    type: str
    value: str


class PokemonCard(BaseModel):
    """ポケモンカード情報"""
    id: Optional[int] = None
    name: str
    image_url: Optional[str] = None
    list_index: Optional[int] = None
    hp: Optional[int] = None
    type: Optional[str] = None
    evolution_stage: Optional[str] = None
    attacks: List[Attack] = []
    weakness: Optional[Weakness] = None
    resistance: Optional[Resistance] = None
    retreat_cost: Optional[int] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True  # Pydantic v2の設定


class CardCreateRequest(BaseModel):
    """カード作成リクエスト"""
    name: str
    image_url: str
    hp: int
    type: str
    evolution_stage: str
    attacks: List[Attack]
    weakness: Optional[Weakness] = None
    resistance: Optional[Resistance] = None
    retreat_cost: int


class CardUpdateRequest(BaseModel):
    """カード更新リクエスト"""
    name: Optional[str] = None
    image_url: Optional[str] = None
    hp: Optional[int] = None
    type: Optional[str] = None
    evolution_stage: Optional[str] = None
    attacks: Optional[List[Attack]] = None
    weakness: Optional[Weakness] = None
    resistance: Optional[Resistance] = None
    retreat_cost: Optional[int] = None