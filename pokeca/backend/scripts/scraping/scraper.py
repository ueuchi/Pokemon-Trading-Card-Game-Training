"""
ポケモンカード公式サイト スクレイピングツール
完全動作版 - コピペですぐに使えます
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
import os
import requests
from pathlib import Path

class PokemonCardScraper:
    def __init__(self, headless=True):
        """
        スクレイパーを初期化
        
        Args:
            headless: ヘッドレスモードで実行するか（True=ブラウザ画面を表示しない）
        """
        print("🔧 Seleniumを初期化中...")
        
        # Chromeオプション設定
        chrome_options = Options()
        if headless:
            chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        # ChromeDriverを自動インストール＆設定
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.driver.implicitly_wait(10)
        
        print("✅ 初期化完了！")
    
    def scrape_card_list(self, keyword="", product_id=None, max_cards=None):
        """
        カード一覧を取得
        
        Args:
            keyword: 検索キーワード（例: "ピカチュウ"）
            product_id: 商品ID（弾のID、例: 869 = VSTARユニバース）
            max_cards: 最大取得カード数（Noneの場合は全て取得）
        
        Returns:
            カード情報のリスト
        """
        # URL生成
        base_url = "https://www.pokemon-card.com/card-search/index.php"
        params = []
        
        if keyword:
            params.append(f"keyword={keyword}")
        if product_id:
            params.append(f"pg={product_id}")
        
        # regulation_sidebar_formはデフォルトで全てを検索
        params.append("regulation_sidebar_form=all")
        
        url = base_url + "?" + "&".join(params)
        
        print(f"\n🔍 カード検索中: {url}")
        self.driver.get(url)
        
        # ページ読み込み待機
        time.sleep(3)
        
        try:
            # カードリストが表示されるまで待機
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "section.card-list-section"))
            )
            print("✅ カードリスト読み込み完了")
        except:
            print("❌ カードリストが見つかりませんでした")
            return []
        
        # カード要素を全て取得
        card_elements = self.driver.find_elements(By.CSS_SELECTOR, "section.card-list-section li")
        
        total_found = len(card_elements)
        print(f"📊 {total_found}枚のカードを発見")
        
        if max_cards:
            card_elements = card_elements[:max_cards]
            print(f"⚡ 最初の{max_cards}枚のみ取得します")
        
        cards = []
        for idx, element in enumerate(card_elements, 1):
            try:
                # カードリンクを取得
                link_elem = element.find_element(By.CSS_SELECTOR, "a")
                card_url = link_elem.get_attribute("href")
                
                # カード画像を取得
                img_elem = element.find_element(By.CSS_SELECTOR, "img")
                card_img_url = img_elem.get_attribute("src")
                
                # カード名を取得（alt属性から）
                card_name = img_elem.get_attribute("alt")
                
                cards.append({
                    "name": card_name,
                    "url": card_url,
                    "image_url": card_img_url
                })
                
                print(f"  [{idx}/{len(card_elements)}] {card_name}")
                
            except Exception as e:
                print(f"  ⚠️ カード情報の取得に失敗: {e}")
                continue
        
        print(f"\n✅ {len(cards)}枚のカード情報を取得しました")
        return cards
    
    def scrape_card_detail(self, card_url):
        """
        個別カードページから詳細情報を取得
        
        Args:
            card_url: カード詳細ページのURL
        
        Returns:
            カード詳細情報の辞書
        """
        print(f"\n🔍 詳細取得中: {card_url}")
        self.driver.get(card_url)
        time.sleep(2)
        
        card_data = {}
        
        try:
            # カード名
            try:
                card_name = self.driver.find_element(By.CSS_SELECTOR, "h1.card_name span").text
                card_data["name"] = card_name
                print(f"  📛 カード名: {card_name}")
            except:
                card_data["name"] = "不明"
            
            # カード画像URL
            try:
                img_url = self.driver.find_element(By.CSS_SELECTOR, "div.card_image img").get_attribute("src")
                card_data["image_url"] = img_url
            except:
                card_data["image_url"] = None
            
            # HP（ポケモンカードの場合）
            try:
                hp = self.driver.find_element(By.CSS_SELECTOR, "div.card_status dl dt:contains('HP') + dd").text
                card_data["hp"] = int(hp.replace("HP", "").strip())
            except:
                try:
                    # 別の方法で取得を試みる
                    status_text = self.driver.find_element(By.CSS_SELECTOR, "div.card_status").text
                    if "HP" in status_text:
                        hp_text = status_text.split("HP")[1].split()[0]
                        card_data["hp"] = int(hp_text)
                    else:
                        card_data["hp"] = None
                except:
                    card_data["hp"] = None
            
            # タイプ
            try:
                card_type = self.driver.find_element(By.CSS_SELECTOR, "div.card_status .type").text
                card_data["type"] = card_type
            except:
                card_data["type"] = None
            
            # 進化段階
            try:
                evolution = self.driver.find_element(By.CSS_SELECTOR, "div.card_status .evolution").text
                card_data["evolution_stage"] = evolution
            except:
                card_data["evolution_stage"] = None
            
            # カードカテゴリ（ポケモン/トレーナー/エネルギー）
            try:
                category = self.driver.find_element(By.CSS_SELECTOR, "div.card_info .card_category").text
                card_data["category"] = category
            except:
                card_data["category"] = None
            
            # レアリティ
            try:
                rarity = self.driver.find_element(By.CSS_SELECTOR, "div.card_info .rarity").text
                card_data["rarity"] = rarity
            except:
                card_data["rarity"] = None
            
            # 収録商品
            try:
                product = self.driver.find_element(By.CSS_SELECTOR, "div.card_info .product_name").text
                card_data["product"] = product
            except:
                card_data["product"] = None
            
            # 弱点
            try:
                weakness = self.driver.find_element(By.CSS_SELECTOR, "div.weakness .type").text
                weakness_value = self.driver.find_element(By.CSS_SELECTOR, "div.weakness .value").text
                card_data["weakness"] = {"type": weakness, "value": weakness_value}
            except:
                card_data["weakness"] = None
            
            # 抵抗力
            try:
                resistance = self.driver.find_element(By.CSS_SELECTOR, "div.resistance .type").text
                resistance_value = self.driver.find_element(By.CSS_SELECTOR, "div.resistance .value").text
                card_data["resistance"] = {"type": resistance, "value": resistance_value}
            except:
                card_data["resistance"] = None
            
            # 逃げるコスト
            try:
                retreat_cost = len(self.driver.find_elements(By.CSS_SELECTOR, "div.retreat img"))
                card_data["retreat_cost"] = retreat_cost
            except:
                card_data["retreat_cost"] = None
            
            # 攻撃（わざ）
            attacks = []
            try:
                attack_blocks = self.driver.find_elements(By.CSS_SELECTOR, "div.ability_block")
                for attack_block in attack_blocks:
                    attack = {}
                    
                    # 攻撃名
                    try:
                        attack_name = attack_block.find_element(By.CSS_SELECTOR, ".ability_name").text
                        attack["name"] = attack_name
                    except:
                        continue
                    
                    # エネルギーコスト
                    try:
                        cost_imgs = attack_block.find_elements(By.CSS_SELECTOR, ".ability_cost img")
                        cost = []
                        for img in cost_imgs:
                            energy_type = img.get_attribute("alt")
                            cost.append(energy_type)
                        attack["cost"] = cost
                    except:
                        attack["cost"] = []
                    
                    # ダメージ
                    try:
                        damage = attack_block.find_element(By.CSS_SELECTOR, ".ability_damage").text
                        attack["damage"] = damage
                    except:
                        attack["damage"] = None
                    
                    # 効果テキスト
                    try:
                        effect = attack_block.find_element(By.CSS_SELECTOR, ".ability_text").text
                        attack["effect"] = effect
                    except:
                        attack["effect"] = None
                    
                    attacks.append(attack)
            except:
                pass
            
            card_data["attacks"] = attacks
            
            # 特性
            try:
                special_ability = self.driver.find_element(By.CSS_SELECTOR, "div.special_ability .ability_text").text
                card_data["special_ability"] = special_ability
            except:
                card_data["special_ability"] = None
            
            print(f"  ✅ 詳細取得完了")
            return card_data
            
        except Exception as e:
            print(f"  ❌ エラー: {e}")
            return None
    
    def download_image(self, image_url, save_path):
        """
        カード画像をダウンロード
        
        Args:
            image_url: 画像URL
            save_path: 保存先パス
        
        Returns:
            成功したかどうか
        """
        try:
            response = requests.get(image_url, timeout=10)
            response.raise_for_status()
            
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            with open(save_path, 'wb') as f:
                f.write(response.content)
            
            return True
        except Exception as e:
            print(f"  ⚠️ 画像ダウンロード失敗: {e}")
            return False
    
    def save_to_json(self, data, filename):
        """JSONファイルに保存"""
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"💾 保存完了: {filename}")
    
    def close(self):
        """ブラウザを閉じる"""
        print("\n🔚 ブラウザを閉じています...")
        self.driver.quit()
        print("✅ 完了")


def main():
    """
    メイン実行関数
    ここを編集して好きなカードを取得できます
    """
    
    print("=" * 60)
    print("🎴 ポケモンカード公式サイト スクレイピングツール")
    print("=" * 60)
    
    # スクレイパーを初期化
    scraper = PokemonCardScraper(headless=True)
    
    try:
        # ========================================
        # 例1: ピカチュウのカードを10枚取得
        # ========================================
        print("\n【例1】ピカチュウのカードを取得")
        cards = scraper.scrape_card_list(
            keyword="ピカチュウ",
            # product_id=869,  # VSTARユニバース
            max_cards=10  # 最初は10枚でテスト
        )
        
        # カード一覧を保存
        scraper.save_to_json(
            cards,
            "backend/data/scraped/raw/pikachu_list.json"
        )
        
        # ========================================
        # 各カードの詳細を取得
        # ========================================
        print("\n【詳細情報を取得中】")
        detailed_cards = []
        
        for i, card in enumerate(cards, 1):
            print(f"\n[{i}/{len(cards)}] {card['name']}")
            
            # 詳細取得
            detail = scraper.scrape_card_detail(card['url'])
            
            if detail:
                detailed_cards.append(detail)
                
                # 画像をダウンロード（optional）
                if detail.get('image_url'):
                    # ファイル名を生成
                    safe_name = "".join(c for c in detail['name'] if c.isalnum() or c in (' ', '_', '-'))
                    image_path = f"backend/data/images/official/{safe_name}.png"
                    
                    print(f"  🖼️ 画像ダウンロード中...")
                    scraper.download_image(detail['image_url'], image_path)
            
            # サーバー負荷軽減（重要！）
            time.sleep(2)
        
        # 詳細情報を保存
        scraper.save_to_json(
            detailed_cards,
            "backend/data/scraped/raw/pikachu_detailed.json"
        )
        
        # ========================================
        # 例2: 特定の弾のカードを取得（コメントアウト）
        # ========================================
        # print("\n【例2】VSTARユニバースのカードを取得")
        # cards = scraper.scrape_card_list(
        #     product_id="869",  # VSTARユニバース
        #     max_cards=5
        # )
        # scraper.save_to_json(
        #     cards,
        #     "backend/data/scraped/raw/vstar_universe_list.json"
        # )
        
        print("\n" + "=" * 60)
        print("✅ すべての処理が完了しました！")
        print("=" * 60)
        print(f"\n取得カード数: {len(detailed_cards)}枚")
        print(f"保存先: backend/data/scraped/raw/")
        
    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # ブラウザを閉じる
        scraper.close()


if __name__ == "__main__":
    main()