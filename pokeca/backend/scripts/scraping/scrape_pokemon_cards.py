from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import json
import time
import os

class PokemonCardScraper:
    def __init__(self):
        # Headlessモード設定
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.base_url = "https://www.pokemon-card.com/card-search/index.php"
        
    def scrape_card_list(self, keyword="", regulation="XY", product_id=None):
        """
        カード一覧を取得
        
        Args:
            keyword: カード名キーワード
            regulation: レギュレーション（XY, BW, など）
            product_id: 商品ID（弾のID、例: 869 = VSTARユニバース）
        """
        params = f"?keyword={keyword}&regulation_sidebar_form={regulation}"
        if product_id:
            params += f"&pg={product_id}"
        
        url = self.base_url + params
        print(f"Accessing: {url}")
        
        self.driver.get(url)
        
        # ページが読み込まれるまで待機
        time.sleep(3)
        
        # カード要素を取得
        wait = WebDriverWait(self.driver, 10)
        card_elements = wait.until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.card_list ul li"))
        )
        
        cards = []
        for element in card_elements:
            try:
                # カード名
                card_name_elem = element.find_element(By.CSS_SELECTOR, "h2.card_name")
                card_name = card_name_elem.text
                
                # カードリンク
                card_link_elem = element.find_element(By.CSS_SELECTOR, "a")
                card_url = card_link_elem.get_attribute("href")
                
                # カード画像
                card_img_elem = element.find_element(By.CSS_SELECTOR, "img")
                card_img_url = card_img_elem.get_attribute("src")
                
                cards.append({
                    "name": card_name,
                    "url": card_url,
                    "image_url": card_img_url
                })
                
                print(f"Found: {card_name}")
                
            except Exception as e:
                print(f"Error parsing card element: {e}")
                continue
        
        return cards
    
    def save_to_json(self, data, filename):
        """JSONファイルに保存"""
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Saved to: {filename}")
    
    def close(self):
        """ブラウザを閉じる"""
        self.driver.quit()

# 使用例
if __name__ == "__main__":
    scraper = PokemonCardScraper()
    
    # ピカチュウを検索
    cards = scraper.scrape_card_list(keyword="ピカチュウ")
    scraper.save_to_json(cards, "backend/data/scraped/raw/pikachu_list.json")
    
    # 特定の弾のカード全て取得（例: VSTARユニバース）
    # cards = scraper.scrape_card_list(product_id="869")
    # scraper.save_to_json(cards, "backend/data/scraped/raw/vstar_universe.json")
    
    scraper.close()