import json
from backend.repositories.card_repository import CardRepository

def import_from_json():
    """
    スクレイピングしたJSONファイルをDBに保存
    """
    # JSONファイルを読み込み
    with open('backend/data/scraped/raw/pikachu_detailed.json', 'r') as f:
        cards = json.load(f)
    
    # CardRepositoryを使ってDBに保存
    repo = CardRepository()
    
    for card in cards:
        # DB用フォーマットに変換
        db_card = {
            'name': card['name'],
            'card_type': card['category'],  # 'ポケモン' → 'pokemon'
            'hp': card.get('hp'),
            'type': card.get('type'),
            # ... その他のフィールド
        }
        
        # DBに保存
        repo.create_card(db_card)
        print(f"✅ {card['name']} を保存しました")

if __name__ == "__main__":
    import_from_json()