"""
データベースモデル定義
pydanticがある場合はBaseModel、なければdataclassにフォールバック
"""
from typing import Optional, List

try:
    from pydantic import BaseModel
    from datetime import datetime

    class Attack(BaseModel):
        name: str
        energy: List[str]
        energy_count: int
        damage: int
        description: str

    class Weakness(BaseModel):
        type: str
        value: str

    class Resistance(BaseModel):
        type: str
        value: str

    class PokemonCard(BaseModel):
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
            from_attributes = True

    class CardCreateRequest(BaseModel):
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
        name: Optional[str] = None
        image_url: Optional[str] = None
        hp: Optional[int] = None
        type: Optional[str] = None
        evolution_stage: Optional[str] = None
        attacks: Optional[List[Attack]] = None
        weakness: Optional[Weakness] = None
        resistance: Optional[Resistance] = None
        retreat_cost: Optional[int] = None

except ImportError:
    from dataclasses import dataclass, field

    @dataclass
    class Attack:
        name: str = ""
        energy: List = field(default_factory=list)
        energy_count: int = 0
        damage: int = 0
        description: str = ""

    @dataclass
    class Weakness:
        type: str = ""
        value: str = ""

    @dataclass
    class Resistance:
        type: str = ""
        value: str = ""

    @dataclass
    class PokemonCard:
        id: Optional[int] = None
        name: str = ""
        image_url: Optional[str] = None
        list_index: Optional[int] = None
        hp: Optional[int] = None
        type: Optional[str] = None
        evolution_stage: Optional[str] = None
        attacks: List = field(default_factory=list)
        weakness: Optional[object] = None
        resistance: Optional[object] = None
        retreat_cost: Optional[int] = None
        created_at: Optional[str] = None

    class CardCreateRequest:
        pass

    class CardUpdateRequest:
        pass
