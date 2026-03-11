"""
デッキバリデーション
"""
from typing import List, Tuple
from models.card import PokemonCard


def validate_deck(deck: List[PokemonCard]) -> Tuple[bool, List[str]]:
    errors = []
    if len(deck) != 60:
        errors.append(f"デッキは60枚必要です（現在{len(deck)}枚）")
    name_count: dict[str, int] = {}
    ace_spec_count = 0
    for card in deck:
        name_count[card.name] = name_count.get(card.name, 0) + 1
        if card.card_type == "trainer" and card.is_ace_spec:
            ace_spec_count += 1
    for name, count in name_count.items():
        card = next((c for c in deck if c.name == name), None)
        # 基本エネルギーは何枚でもOK（card_type="energy" かつ名前が"基本"で始まる、または energy_type="basic"）
        if card and card.card_type == "energy":
            continue
        if count > 4:
            errors.append(f"「{name}」は4枚までです（現在{count}枚）")
    if ace_spec_count > 1:
        ace_cards = [c.name for c in deck if c.card_type == "trainer" and c.is_ace_spec]
        errors.append(f"ACE SPECはデッキに1枚までです（現在{ace_spec_count}枚: {ace_cards}）")
    return len(errors) == 0, errors
