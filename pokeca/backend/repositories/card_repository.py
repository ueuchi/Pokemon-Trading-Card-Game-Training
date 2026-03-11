"""
カードリポジトリ（更新版）
新しいデータモデルに対応
"""
import json
from typing import List, Optional

from models.card import PokemonCard, Attack, EffectStep, Ability, Resistance


class CardRepository:
    def __init__(self, conn):
        self.conn = conn

    def row_to_card(self, row: dict) -> PokemonCard:
        """DBの行データをPokemonCardオブジェクトに変換"""
        # attacks JSON パース
        attacks = []
        if row.get("attacks"):
            try:
                attacks_data = json.loads(row["attacks"])
                for a in attacks_data:
                    # effect_steps パース
                    raw_steps = a.get("effect_steps", [])
                    effect_steps = [
                        EffectStep(
                            type=s.get("type", "custom"),
                            params=s.get("params", {}),
                        )
                        for s in raw_steps
                    ]
                    attacks.append(Attack(
                        name=a.get("name", ""),
                        energy=a.get("energy", []),
                        energy_count=a.get("energy_count", 0),
                        damage=a.get("damage", 0),
                        description=a.get("description", ""),
                        effect_steps=effect_steps,
                    ))
            except (json.JSONDecodeError, TypeError):
                pass

        # ability JSON パース
        ability = None
        if row.get("ability"):
            try:
                ab = json.loads(row["ability"])
                ability = Ability(
                    name=ab.get("name", ""),
                    description=ab.get("description", ""),
                )
            except (json.JSONDecodeError, TypeError):
                pass

        # weakness パース（typeのみ文字列で保持）
        weakness: Optional[str] = row.get("weakness_type") or None

        # resistance パース
        resistance = None
        if row.get("resistance_type"):
            resistance = Resistance(
                type=row["resistance_type"],
                value=row.get("resistance_value", -30),
            )

        return PokemonCard(
            id=row["id"],
            name=row["name"],
            card_type=row.get("card_type", "pokemon"),
            pokemon_type=row.get("pokemon_type", "normal"),
            card_rule=row.get("card_rule"),
            evolution_stage=row.get("evolution_stage"),
            evolves_from=row.get("evolves_from"),
            hp=row.get("hp"),
            type=row.get("type"),
            attacks=attacks,
            ability=ability,
            weakness=weakness,
            resistance=resistance,
            retreat_cost=row.get("retreat_cost", 0),
            energy_type=row.get("energy_type"),
            trainer_type=row.get("trainer_type"),
            is_ace_spec=bool(row.get("is_ace_spec", 0)),
            effect_description=row.get("effect_description"),
            image_url=row.get("image_url"),
        )

    def get_all_cards(self) -> List[PokemonCard]:
        cursor = self.conn.execute("SELECT * FROM cards ORDER BY id")
        return [self.row_to_card(dict(row)) for row in cursor.fetchall()]

    def get_card_by_id(self, card_id: int) -> Optional[PokemonCard]:
        cursor = self.conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,))
        row = cursor.fetchone()
        return self.row_to_card(dict(row)) if row else None

    def get_cards_by_type(self, card_type: str) -> List[PokemonCard]:
        cursor = self.conn.execute(
            "SELECT * FROM cards WHERE card_type = ? ORDER BY id", (card_type,)
        )
        return [self.row_to_card(dict(row)) for row in cursor.fetchall()]

    def get_cards_by_name(self, name: str) -> List[PokemonCard]:
        cursor = self.conn.execute(
            "SELECT * FROM cards WHERE name LIKE ? ORDER BY id", (f"%{name}%",)
        )
        return [self.row_to_card(dict(row)) for row in cursor.fetchall()]

    def get_card_count(self) -> int:
        cursor = self.conn.execute("SELECT COUNT(*) as cnt FROM cards")
        return cursor.fetchone()["cnt"]

    def create_card(self, data: dict) -> int:
        attacks = data.get("attacks", [])
        if attacks and not isinstance(attacks, str):
            attacks = json.dumps([
                {
                    "name": a.name if hasattr(a, "name") else a.get("name", ""),
                    "energy": a.energy if hasattr(a, "energy") else a.get("energy", []),
                    "energy_count": a.energy_count if hasattr(a, "energy_count") else a.get("energy_count", 0),
                    "damage": a.damage if hasattr(a, "damage") else a.get("damage", 0),
                    "description": a.description if hasattr(a, "description") else a.get("description", ""),
                }
                for a in attacks
            ], ensure_ascii=False)
        elif not attacks:
            attacks = "[]"

        ability = data.get("ability")
        if ability and not isinstance(ability, str):
            if hasattr(ability, "name"):
                ability = json.dumps({"name": ability.name, "description": ability.description}, ensure_ascii=False)
            elif isinstance(ability, dict):
                ability = json.dumps(ability, ensure_ascii=False)

        weakness = data.get("weakness")
        weakness_type = weakness.type if hasattr(weakness, "type") else (weakness.get("type") if isinstance(weakness, dict) else None)
        weakness_value = weakness.value if hasattr(weakness, "value") else (weakness.get("value", 2) if isinstance(weakness, dict) else None)

        resistance = data.get("resistance")
        resistance_type = resistance.type if hasattr(resistance, "type") else (resistance.get("type") if isinstance(resistance, dict) else None)
        resistance_value = resistance.value if hasattr(resistance, "value") else (resistance.get("value", -30) if isinstance(resistance, dict) else None)

        cursor = self.conn.execute("""
            INSERT INTO cards (
                name, card_type, pokemon_type, card_rule,
                evolution_stage, evolves_from, hp, type,
                attacks, ability,
                weakness_type, weakness_value,
                resistance_type, resistance_value,
                retreat_cost, energy_type,
                trainer_type, is_ace_spec, effect_description,
                image_url
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get("name"),
            data.get("card_type", "pokemon"),
            data.get("pokemon_type", "normal"),
            data.get("card_rule"),
            data.get("evolution_stage"),
            data.get("evolves_from"),
            data.get("hp"),
            data.get("type"),
            attacks,
            ability,
            weakness_type,
            weakness_value,
            resistance_type,
            resistance_value,
            data.get("retreat_cost", 0),
            data.get("energy_type"),
            data.get("trainer_type"),
            1 if data.get("is_ace_spec") else 0,
            data.get("effect_description"),
            data.get("image_url"),
        ))
        self.conn.commit()
        return cursor.lastrowid

    def update_card(self, card_id: int, data: dict) -> bool:
        fields = []
        values = []

        simple_fields = [
            "name", "card_type", "pokemon_type", "card_rule",
            "evolution_stage", "evolves_from", "hp", "type",
            "retreat_cost", "energy_type", "trainer_type",
            "effect_description", "image_url",
        ]
        for f in simple_fields:
            if f in data:
                fields.append(f"{f} = ?")
                values.append(data[f])

        if "is_ace_spec" in data:
            fields.append("is_ace_spec = ?")
            values.append(1 if data["is_ace_spec"] else 0)

        if "attacks" in data:
            attacks = data["attacks"]
            if attacks and not isinstance(attacks, str):
                attacks = json.dumps([
                    {
                        "name": a.name if hasattr(a, "name") else a.get("name", ""),
                        "energy": a.energy if hasattr(a, "energy") else a.get("energy", []),
                        "energy_count": a.energy_count if hasattr(a, "energy_count") else a.get("energy_count", 0),
                        "damage": a.damage if hasattr(a, "damage") else a.get("damage", 0),
                        "description": a.description if hasattr(a, "description") else a.get("description", ""),
                    }
                    for a in attacks
                ], ensure_ascii=False)
            fields.append("attacks = ?")
            values.append(attacks or "[]")

        if "ability" in data:
            ability = data["ability"]
            if ability and not isinstance(ability, str):
                if hasattr(ability, "name"):
                    ability = json.dumps({"name": ability.name, "description": ability.description}, ensure_ascii=False)
                elif isinstance(ability, dict):
                    ability = json.dumps(ability, ensure_ascii=False)
            fields.append("ability = ?")
            values.append(ability)

        if "weakness" in data:
            weakness = data["weakness"]
            fields.append("weakness_type = ?")
            fields.append("weakness_value = ?")
            values.append(weakness.type if hasattr(weakness, "type") else (weakness.get("type") if weakness else None))
            values.append(weakness.value if hasattr(weakness, "value") else (weakness.get("value", 2) if weakness else None))

        if "resistance" in data:
            resistance = data["resistance"]
            fields.append("resistance_type = ?")
            fields.append("resistance_value = ?")
            values.append(resistance.type if hasattr(resistance, "type") else (resistance.get("type") if resistance else None))
            values.append(resistance.value if hasattr(resistance, "value") else (resistance.get("value", -30) if resistance else None))

        if not fields:
            return False

        values.append(card_id)
        self.conn.execute(
            f"UPDATE cards SET {', '.join(fields)} WHERE id = ?", values
        )
        self.conn.commit()
        return True

    def delete_card(self, card_id: int) -> bool:
        self.conn.execute("DELETE FROM cards WHERE id = ?", (card_id,))
        self.conn.commit()
        return True