import json
import os

def convert_scraped_to_db_format(scraped_data):
    """
    スクレイピングしたデータをDB用フォーマットに変換
    
    Args:
        scraped_data: スクレイピングした生データ（dict）
    
    Returns:
        DB挿入用データ（dict）
    """
    # カードタイプを判定
    if scraped_data.get('hp') is not None:
        card_type = 'pokemon'
    elif 'エネルギー' in scraped_data.get('name', ''):
        card_type = 'energy'
    else:
        card_type = 'trainer'
    
    db_data = {
        'name': scraped_data.get('name'),
        'card_type': card_type,
        'rarity': scraped_data.get('rarity'),
        'product': scraped_data.get('product'),
        'image_url': scraped_data.get('image_url')
    }
    
    # ポケモンカードの場合
    if card_type == 'pokemon':
        db_data.update({
            'hp': scraped_data.get('hp'),
            'type': scraped_data.get('type'),
            'evolution_stage': scraped_data.get('evolution_stage'),
            'weakness_type': scraped_data.get('weakness'),
            'resistance_type': scraped_data.get('resistance'),
            'retreat_cost': scraped_data.get('retreat_cost'),
            'attacks': scraped_data.get('attacks', [])
        })
    
    # トレーナーカードの場合
    elif card_type == 'trainer':
        # トレーナーカテゴリを判定（サポート、グッズなど）
        trainer_category = 'item'  # デフォルト
        if 'サポート' in scraped_data.get('name', ''):
            trainer_category = 'supporter'
        elif 'スタジアム' in scraped_data.get('name', ''):
            trainer_category = 'stadium'
        
        db_data.update({
            'trainer_category': trainer_category
        })
    
    return db_data

def process_all_scraped_data(input_file, output_dir):
    """
    全てのスクレイピングデータを変換して保存
    
    Args:
        input_file: スクレイピング結果のJSONファイル
        output_dir: 変換後データの保存先
    """
    # 入力ファイルを読み込み
    with open(input_file, 'r', encoding='utf-8') as f:
        scraped_cards = json.load(f)
    
    # カードタイプ別に分類
    pokemon_cards = []
    trainer_cards = []
    energy_cards = []
    
    for card in scraped_cards:
        db_format = convert_scraped_to_db_format(card)
        
        if db_format['card_type'] == 'pokemon':
            pokemon_cards.append(db_format)
        elif db_format['card_type'] == 'trainer':
            trainer_cards.append(db_format)
        elif db_format['card_type'] == 'energy':
            energy_cards.append(db_format)
    
    # 保存
    os.makedirs(output_dir, exist_ok=True)
    
    if pokemon_cards:
        with open(f"{output_dir}/pokemon.json", 'w', encoding='utf-8') as f:
            json.dump(pokemon_cards, f, ensure_ascii=False, indent=2)
        print(f"Saved {len(pokemon_cards)} pokemon cards")
    
    if trainer_cards:
        with open(f"{output_dir}/trainer.json", 'w', encoding='utf-8') as f:
            json.dump(trainer_cards, f, ensure_ascii=False, indent=2)
        print(f"Saved {len(trainer_cards)} trainer cards")
    
    if energy_cards:
        with open(f"{output_dir}/energy.json", 'w', encoding='utf-8') as f:
            json.dump(energy_cards, f, ensure_ascii=False, indent=2)
        print(f"Saved {len(energy_cards)} energy cards")

if __name__ == "__main__":
    input_file = "backend/data/scraped/raw/all_cards.json"
    output_dir = "backend/data/scraped/processed"
    
    process_all_scraped_data(input_file, output_dir)