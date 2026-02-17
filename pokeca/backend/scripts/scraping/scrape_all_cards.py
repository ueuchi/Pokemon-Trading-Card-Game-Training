import json
import time
from scrape_pokemon_cards import PokemonCardScraper
from scrape_card_detail import CardDetailScraper

def scrape_all_cards(keyword=None, product_id=None, limit=None):
    """
    カード一覧を取得し、各カードの詳細を取得
    
    Args:
        keyword: 検索キーワード
        product_id: 商品ID
        limit: 取得する最大カード数（Noneの場合は全て）
    """
    # カード一覧を取得
    list_scraper = PokemonCardScraper()
    cards = list_scraper.scrape_card_list(keyword=keyword, product_id=product_id)
    list_scraper.close()
    
    print(f"\nFound {len(cards)} cards")
    
    # 詳細を取得
    detail_scraper = CardDetailScraper()
    detailed_cards = []
    
    for i, card in enumerate(cards[:limit] if limit else cards):
        print(f"\n[{i+1}/{len(cards)}] Processing: {card['name']}")
        
        # 詳細取得
        detail = detail_scraper.scrape_card_detail(card['url'])
        
        if detail:
            detailed_cards.append(detail)
        
        # サーバー負荷軽減のため待機（重要！）
        time.sleep(2)
    
    detail_scraper.close()
    
    # 結果を保存
    output_file = "backend/data/scraped/raw/all_cards.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(detailed_cards, f, ensure_ascii=False, indent=2)
    
    print(f"\n\n✅ Scraping completed!")
    print(f"Total cards scraped: {len(detailed_cards)}")
    print(f"Saved to: {output_file}")

if __name__ == "__main__":
    # 例1: ピカチュウを全て取得
    scrape_all_cards(keyword="ピカチュウ")
    
    # 例2: 特定の弾のカード全て取得（最初の10枚のみ）
    # scrape_all_cards(product_id="869", limit=10)
    
    # 例3: 全カード取得（時間がかかるので注意）
    # scrape_all_cards()