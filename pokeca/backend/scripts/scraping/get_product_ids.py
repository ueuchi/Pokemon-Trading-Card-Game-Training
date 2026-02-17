"""
商品ID一覧を取得するスクリプト
backend/scripts/scraping/get_product_ids.py
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import json
import time

class ProductIdScraper:
    def __init__(self, headless=True):
        print("🔧 Seleniumを初期化中...")
        
        chrome_options = Options()
        if headless:
            chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        print("✅ 初期化完了！")
    
    def get_product_list(self):
        """
        商品（弾）の一覧とIDを取得
        
        Returns:
            商品IDと商品名の辞書リスト
        """
        url = "https://www.pokemon-card.com/card-search/"
        print(f"\n🔍 商品一覧を取得中: {url}")
        
        self.driver.get(url)
        time.sleep(3)
        
        products = []
        
        try:
            # サイドバーの商品セレクトボックスを探す
            # （実際のHTML構造に応じて調整が必要）
            
            # 方法1: セレクトボックスから取得
            try:
                select_element = self.driver.find_element(By.CSS_SELECTOR, "select[name='pg']")
                options = select_element.find_elements(By.TAG_NAME, "option")
                
                for option in options:
                    product_id = option.get_attribute("value")
                    product_name = option.text
                    
                    if product_id and product_name:
                        products.append({
                            "id": product_id,
                            "name": product_name
                        })
                        print(f"  📦 {product_name} (ID: {product_id})")
            except:
                print("  ⚠️ セレクトボックスが見つかりませんでした")
            
            # 方法2: リンクから取得
            try:
                product_links = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='pg=']")
                
                for link in product_links:
                    href = link.get_attribute("href")
                    product_name = link.text
                    
                    if "pg=" in href and product_name:
                        # URLからIDを抽出
                        product_id = href.split("pg=")[1].split("&")[0]
                        
                        # 重複チェック
                        if not any(p['id'] == product_id for p in products):
                            products.append({
                                "id": product_id,
                                "name": product_name
                            })
                            print(f"  📦 {product_name} (ID: {product_id})")
            except Exception as e:
                print(f"  ⚠️ リンクから取得失敗: {e}")
            
        except Exception as e:
            print(f"❌ エラー: {e}")
        
        print(f"\n✅ {len(products)}個の商品を発見")
        return products
    
    def save_to_json(self, products, filename="backend/data/scraped/product_ids.json"):
        """商品一覧をJSONで保存"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(products, f, ensure_ascii=False, indent=2)
        print(f"💾 保存完了: {filename}")
    
    def close(self):
        self.driver.quit()


def main():
    scraper = ProductIdScraper(headless=True)
    
    try:
        # 商品一覧を取得
        products = scraper.get_product_list()
        
        # JSONで保存
        scraper.save_to_json(products)
        
        print("\n" + "="*60)
        print("✅ 商品ID一覧を取得しました！")
        print("="*60)
        
    finally:
        scraper.close()


if __name__ == "__main__":
    main()