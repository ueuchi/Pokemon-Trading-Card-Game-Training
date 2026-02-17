"""
カードリポジトリ - データアクセス層
"""
import json
import sqlite3
from typing import List, Optional
from models.card import PokemonCard, Attack, Weakness, Resistance


class CardRepository:
    """カードデータのCRUD操作を管理"""
    
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.cursor = conn.cursor()
    
    def _row_to_card(self, row: sqlite3.Row) -> PokemonCard:
        """
        データベースの行をPokemonCardオブジェクトに変換
        """
        # ワザ情報をパース
        attacks_data = json.loads(row["attacks"]) if row["attacks"] else []
        attacks = [Attack(**attack) for attack in attacks_data]
        
        # 弱点情報をパース
        weakness = None
        if row["weakness_type"] and row["weakness_value"]:
            weakness = Weakness(
                type=row["weakness_type"],
                value=row["weakness_value"]
            )
        
        # 抵抗力情報をパース
        resistance = None
        if row["resistance_type"] and row["resistance_value"]:
            resistance = Resistance(
                type=row["resistance_type"],
                value=row["resistance_value"]
            )
        
        return PokemonCard(
            id=row["id"],
            name=row["name"],
            image_url=row["image_url"],
            list_index=row["list_index"],
            hp=row["hp"],
            type=row["type"],
            evolution_stage=row["evolution_stage"],
            attacks=attacks,
            weakness=weakness,
            resistance=resistance,
            retreat_cost=row["retreat_cost"],
            created_at=row["created_at"]
        )
    
    def get_all_cards(self) -> List[PokemonCard]:
        """
        全カードを取得
        """
        self.cursor.execute('SELECT * FROM cards ORDER BY list_index')
        rows = self.cursor.fetchall()
        return [self._row_to_card(row) for row in rows]
    
    def get_card_by_id(self, card_id: int) -> Optional[PokemonCard]:
        """
        IDでカードを取得
        """
        self.cursor.execute('SELECT * FROM cards WHERE id = ?', (card_id,))
        row = self.cursor.fetchone()
        return self._row_to_card(row) if row else None
    
    def get_cards_by_type(self, card_type: str) -> List[PokemonCard]:
        """
        タイプでカードを検索
        """
        self.cursor.execute('SELECT * FROM cards WHERE type = ? ORDER BY list_index', (card_type,))
        rows = self.cursor.fetchall()
        return [self._row_to_card(row) for row in rows]
    
    def get_cards_by_name(self, name: str) -> List[PokemonCard]:
        """
        名前でカードを検索（部分一致）
        """
        self.cursor.execute(
            'SELECT * FROM cards WHERE name LIKE ? ORDER BY list_index',
            (f'%{name}%',)
        )
        rows = self.cursor.fetchall()
        return [self._row_to_card(row) for row in rows]
    
    def create_card(self, card_data: dict) -> int:
        """
        カードを新規作成
        """
        self.cursor.execute('''
            INSERT INTO cards (
                name, image_url, list_index, hp, type, evolution_stage,
                weakness_type, weakness_value, 
                resistance_type, resistance_value,
                retreat_cost, attacks
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            card_data['name'],
            card_data['image_url'],
            card_data.get('list_index', 0),
            card_data['hp'],
            card_data['type'],
            card_data['evolution_stage'],
            card_data.get('weakness', {}).get('type'),
            card_data.get('weakness', {}).get('value'),
            card_data.get('resistance', {}).get('type'),
            card_data.get('resistance', {}).get('value'),
            card_data['retreat_cost'],
            json.dumps(card_data['attacks'], ensure_ascii=False)
        ))
        self.conn.commit()
        return self.cursor.lastrowid
    
    def update_card(self, card_id: int, card_data: dict) -> bool:
        """
        カードを更新
        """
        # 更新フィールドを動的に構築
        update_fields = []
        values = []
        
        if 'name' in card_data:
            update_fields.append('name = ?')
            values.append(card_data['name'])
        if 'hp' in card_data:
            update_fields.append('hp = ?')
            values.append(card_data['hp'])
        if 'type' in card_data:
            update_fields.append('type = ?')
            values.append(card_data['type'])
        # 他のフィールドも同様に...
        
        if not update_fields:
            return False
        
        values.append(card_id)
        query = f"UPDATE cards SET {', '.join(update_fields)} WHERE id = ?"
        
        self.cursor.execute(query, values)
        self.conn.commit()
        return self.cursor.rowcount > 0
    
    def delete_card(self, card_id: int) -> bool:
        """
        カードを削除
        """
        self.cursor.execute('DELETE FROM cards WHERE id = ?', (card_id,))
        self.conn.commit()
        return self.cursor.rowcount > 0
    
    def get_card_count(self) -> int:
        """
        カードの総数を取得
        """
        self.cursor.execute('SELECT COUNT(*) FROM cards')
        return self.cursor.fetchone()[0]