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

class CardDetailScraper:
    def __init__(self):
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
    
    def scrape_card_detail(self, card_url):
        """
        個別カードページから詳細情報を取得
        
        Args:
            card_url: カード詳細ページのURL
        """
        print(f"Scraping: {card_url}")
        self.driver.get(card_url)
        time.sleep(2)
        
        card_data = {}
        
        try:
            # カード名
            card_name = self.driver.find_element(By.CSS_SELECTOR, "h1.card_name").text
            card_data["name"] = card_name
            
            # HP（ポケモンカードの場合）
            try:
                hp = self.driver.find_element(By.CSS_SELECTOR, "span.hp").text
                card_data["hp"] = int(hp.replace("HP", ""))
            except:
                card_data["hp"] = None
            
            # タイプ
            try:
                card_type = self.driver.find_element(By.CSS_SELECTOR, "span.type").text
                card_data["type"] = card_type
            except:
                card_data["type"] = None
            
            # 進化段階
            try:
                evolution = self.driver.find_element(By.CSS_SELECTOR, "span.evolution").text
                card_data["evolution_stage"] = evolution
            except:
                card_data["evolution_stage"] = None
            
            # 弱点
            try:
                weakness = self.driver.find_element(By.CSS_SELECTOR, "div.weakness span").text
                card_data["weakness"] = weakness
            except:
                card_data["weakness"] = None
            
            # 抵抗力
            try:
                resistance = self.driver.find_element(By.CSS_SELECTOR, "div.resistance span").text
                card_data["resistance"] = resistance
            except:
                card_data["resistance"] = None
            
            # 逃げるコスト
            try:
                retreat = self.driver.find_element(By.CSS_SELECTOR, "div.retreat span").text
                card_data["retreat_cost"] = len(retreat)  # エネルギーマークの数
            except:
                card_data["retreat_cost"] = None
            
            # 攻撃（わざ）
            attacks = []
            try:
                attack_elements = self.driver.find_elements(By.CSS_SELECTOR, "div.attack_block")
                for attack_elem in attack_elements:
                    attack = {}
                    
                    # 攻撃名
                    attack_name = attack_elem.find_element(By.CSS_SELECTOR, "h3.attack_name").text
                    attack["name"] = attack_name
                    
                    # エネルギーコスト
                    try:
                        cost_elements = attack_elem.find_elements(By.CSS_SELECTOR, "span.energy")
                        cost = [elem.get_attribute("class").split()[-1] for elem in cost_elements]
                        attack["cost"] = cost
                    except:
                        attack["cost"] = []
                    
                    # ダメージ
                    try:
                        damage = attack_elem.find_element(By.CSS_SELECTOR, "span.damage").text
                        attack["damage"] = damage.replace("+", "").replace("×", "")
                    except:
                        attack["damage"] = None
                    
                    # 効果
                    try:
                        effect = attack_elem.find_element(By.CSS_SELECTOR, "p.effect").text
                        attack["effect"] = effect
                    except:
                        attack["effect"] = None
                    
                    attacks.append(attack)
            except:
                pass
            
            card_data["attacks"] = attacks
            
            # レアリティ
            try:
                rarity = self.driver.find_element(By.CSS_SELECTOR, "span.rarity").text
                card_data["rarity"] = rarity
            except:
                card_data["rarity"] = None
            
            # 商品名（収録弾）
            try:
                product = self.driver.find_element(By.CSS_SELECTOR, "span.product_name").text
                card_data["product"] = product
            except:
                card_data["product"] = None
            
            # カード画像URL
            try:
                img_url = self.driver.find_element(By.CSS_SELECTOR, "div.card_image img").get_attribute("src")
                card_data["image_url"] = img_url
            except:
                card_data["image_url"] = None
            
            print(f"Successfully scraped: {card_name}")
            
        except Exception as e:
            print(f"Error scraping card detail: {e}")
            return None
        
        return card_data
    
    def save_to_json(self, data, filename):
        """JSONファイルに保存"""
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Saved to: {filename}")
    
    def close(self):
        self.driver.quit()

# 使用例
if __name__ == "__main__":
    scraper = CardDetailScraper()
    
    # 個別カードのURL（例）
    card_url = "https://www.pokemon-card.com/card-search/details.php/card/12345"
    card_detail = scraper.scrape_card_detail(card_url)
    
    if card_detail:
        # カードIDを生成（URLから抽出）
        card_id = card_url.split("/")[-1]
        scraper.save_to_json(
            card_detail, 
            f"backend/data/scraped/raw/cards/{card_detail['name']}_{card_id}.json"
        )
    
    scraper.close()