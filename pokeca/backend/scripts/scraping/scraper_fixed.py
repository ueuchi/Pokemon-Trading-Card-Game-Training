"""
ウィンドウ切り替え修正版
"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import json
import time
import os
import re

class FixedWindowScraper:
    def __init__(self, headless=True):
        print("🔧 Seleniumを初期化中...")
        
        chrome_options = Options()
        if headless:
            chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--window-size=1920,1080')
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        
        print("✅ 初期化完了！")
    
    def scrape_card_list(self, keyword="", max_cards=None):
        """カード一覧を取得"""
        url = f"https://www.pokemon-card.com/card-search/?keyword={keyword}"
        
        print(f"\n🔍 カード検索中: {url}")
        self.driver.get(url)
        
        print("⏳ Vue.jsの読み込み待機（10秒）...")
        time.sleep(3)
        
        print("📜 ページをスクロール...")
        for i in range(3):
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
        
        cards = []
        
        print("\n🔍 カード要素を取得中...")
        items = self.driver.find_elements(By.CSS_SELECTOR, "li.List_item")
        print(f"📊 {len(items)}個の要素を発見")
        
        for i, item in enumerate(items, 1):
            try:
                img = item.find_element(By.TAG_NAME, "img")
                card_name = img.get_attribute("alt")
                img_src = img.get_attribute("src")
                
                if img_src and not img_src.startswith("http"):
                    img_url = f"https://www.pokemon-card.com{img_src}"
                else:
                    img_url = img_src
                
                if card_name:
                    cards.append({
                        "name": card_name,
                        "image_url": img_url,
                        "list_index": i - 1
                    })
                    print(f"  ✅ [{i}] {card_name}")
            
            except Exception as e:
                continue
        
        print(f"\n📊 合計 {len(cards)}枚のカードを取得")
        
        if max_cards:
            cards = cards[:max_cards]
            print(f"⚡ 最初の{max_cards}枚のみ処理します")
        
        return cards
    
    def scrape_card_detail(self, card_info, list_url):
        """カード詳細を取得（ウィンドウ切り替え修正版）"""
        print(f"\n{'='*60}")
        print(f"📄 詳細取得: {card_info['name']}")
        print(f"{'='*60}")
        
        try:
            # 一覧ページに移動
            print("  🔄 一覧ページに移動...")
            self.driver.get(list_url)
            time.sleep(3)
            
            # スクロール
            for i in range(3):
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1)
            
            # 現在のウィンドウハンドルを保存
            original_window = self.driver.current_window_handle
            print(f"  📌 元のウィンドウ: {original_window}")
            
            # カードをクリック
            items = self.driver.find_elements(By.CSS_SELECTOR, "li.List_item")
            target_item = items[card_info['list_index']]
            link = target_item.find_element(By.TAG_NAME, "a")
            
            print("  👆 カードをクリック...")
            link.click()
            
            # 新しいウィンドウが開くまで待機
            print("  ⏳ 新しいウィンドウを待機（3秒）...")
            time.sleep(3)
            
            # 全てのウィンドウハンドルを取得
            all_windows = self.driver.window_handles
            print(f"  📊 ウィンドウ数: {len(all_windows)}")
            
            # 新しいウィンドウに切り替え
            new_window = None
            for window in all_windows:
                if window != original_window:
                    new_window = window
                    break
            
            if new_window:
                print(f"  ✅ 新しいウィンドウに切り替え: {new_window}")
                self.driver.switch_to.window(new_window)
                
                # ページが完全に読み込まれるまで待機
                time.sleep(3)
                
                # 現在のURLを確認
                current_url = self.driver.current_url
                print(f"  🌐 現在のURL: {current_url}")
                
                # HTMLを保存（デバッグ用）
                with open(f"backend/data/scraped/raw/detail_{card_info['list_index']}.html", "w", encoding="utf-8") as f:
                    f.write(self.driver.page_source)
                
                # スクリーンショット（デバッグ用）
                self.driver.save_screenshot(f"backend/data/scraped/raw/detail_{card_info['list_index']}.png")
                
                # 詳細情報を抽出
                detail = self.extract_detail_from_page()
                
                # 元のウィンドウに戻る
                print("  🔄 元のウィンドウに戻る...")
                self.driver.close()
                self.driver.switch_to.window(original_window)
                
                return detail
            else:
                print("  ❌ 新しいウィンドウが見つかりませんでした")
                return None
        
        except Exception as e:
            print(f"  ❌ エラー: {e}")
            import traceback
            traceback.print_exc()
            
            # エラー時もウィンドウを戻す
            try:
                if len(self.driver.window_handles) > 1:
                    self.driver.switch_to.window(self.driver.window_handles[-1])
                    self.driver.close()
                    self.driver.switch_to.window(self.driver.window_handles[0])
            except:
                pass
            
            return None
    
    def extract_detail_from_page(self):
        """詳細ページから情報を抽出（改善版）"""
        detail = {}
        
        print("  🔍 詳細情報を抽出中...")
        
        try:
            # カード名
            try:
                h1 = self.driver.find_element(By.CSS_SELECTOR, "h1.Heading1")
                detail["name"] = h1.text.strip()
                print(f"    📛 カード名: {detail['name']}")
            except:
                detail["name"] = "不明"
            
            # HP
            try:
                hp_elem = self.driver.find_element(By.CSS_SELECTOR, ".hp-num")
                detail["hp"] = int(hp_elem.text.strip())
                print(f"    ❤️ HP: {detail['hp']}")
            except:
                detail["hp"] = None
            
            # タイプ（アイコンのクラス名から判定）
            try:
                type_icon = self.driver.find_element(By.CSS_SELECTOR, ".hp-type + .icon")
                icon_class = type_icon.get_attribute("class")
                
                type_map = {
                    "icon-grass": "草",
                    "icon-fire": "炎",
                    "icon-water": "水",
                    "icon-lightning": "雷",
                    "icon-psychic": "超",
                    "icon-fighting": "闘",
                    "icon-darkness": "悪",
                    "icon-metal": "鋼",
                    "icon-dragon": "ドラゴン",
                    "icon-fairy": "フェアリー",
                    "icon-colorless": "無色"
                }
                
                for key, value in type_map.items():
                    if key in icon_class:
                        detail["type"] = value
                        break
                else:
                    detail["type"] = "不明"
                
                print(f"    ⚡ タイプ: {detail['type']}")
            except Exception as e:
                detail["type"] = "不明"
                print(f"    ⚠️ タイプ取得失敗: {e}")
            
            # 進化段階
            try:
                evo_elem = self.driver.find_element(By.CSS_SELECTOR, ".type")
                evo_text = evo_elem.text.strip()
                detail["evolution_stage"] = evo_text
                print(f"    🌱 進化段階: {detail['evolution_stage']}")
            except:
                detail["evolution_stage"] = "不明"
            
            # ワザ（改善版）
            attacks = []
            try:
                # ワザセクションを探す
                waza_section = self.driver.find_element(By.XPATH, "//h2[contains(text(), 'ワザ')]")
                parent = waza_section.find_element(By.XPATH, "..")
                
                # h4タグ（ワザ名とダメージ）を取得
                waza_headers = parent.find_elements(By.TAG_NAME, "h4")
                waza_descriptions = parent.find_elements(By.XPATH, ".//h4/following-sibling::p[1]")
                
                for i, h4 in enumerate(waza_headers):
                    try:
                        # エネルギーアイコンを取得
                        energy_icons = h4.find_elements(By.CSS_SELECTOR, ".icon")
                        energies = []
                        
                        energy_map = {
                            "icon-grass": "草",
                            "icon-fire": "炎",
                            "icon-water": "水",
                            "icon-lightning": "雷",
                            "icon-psychic": "超",
                            "icon-fighting": "闘",
                            "icon-darkness": "悪",
                            "icon-metal": "鋼",
                            "icon-dragon": "ドラゴン",
                            "icon-fairy": "フェアリー",
                            "icon-none": "無色",
                            "icon-colorless": "無色"
                        }
                        
                        for icon in energy_icons:
                            icon_class = icon.get_attribute("class")
                            for key, value in energy_map.items():
                                if key in icon_class:
                                    energies.append(value)
                                    break
                        
                        # ワザ名を取得（アイコンとダメージを除く）
                        h4_text = h4.text.strip()
                        # 数字部分（ダメージ）を抽出
                        damage_match = re.search(r'(\d+)$', h4_text)
                        damage = int(damage_match.group(1)) if damage_match else 0
                        
                        # ワザ名を抽出（エネルギーアイコンの後、ダメージの前）
                        waza_name = re.sub(r'\d+$', '', h4_text).strip()
                        
                        # 説明文を取得
                        description = ""
                        if i < len(waza_descriptions):
                            description = waza_descriptions[i].text.strip()
                        
                        attack = {
                            "name": waza_name,
                            "energy": energies,
                            "energy_count": len(energies),
                            "damage": damage,
                            "description": description
                        }
                        
                        attacks.append(attack)
                        print(f"    ⚔️ ワザ: {waza_name} ({'/'.join(energies)} × {len(energies)}) ダメージ{damage}")
                    
                    except Exception as e:
                        print(f"    ⚠️ ワザ解析エラー: {e}")
                        continue
            
            except Exception as e:
                print(f"    ⚠️ ワザセクション取得失敗: {e}")
            
            detail["attacks"] = attacks
            
            # 弱点・抵抗力・逃げるエネルギー（テーブルから取得）
            try:
                table = self.driver.find_element(By.CSS_SELECTOR, "table")
                rows = table.find_elements(By.TAG_NAME, "tr")
                
                if len(rows) >= 2:
                    cells = rows[1].find_elements(By.TAG_NAME, "td")
                    
                    # 弱点
                    if len(cells) > 0:
                        weakness_cell = cells[0]
                        weakness_text = weakness_cell.text.strip()
                        
                        if weakness_text and weakness_text != "--":
                            # アイコンからタイプを取得
                            weakness_icons = weakness_cell.find_elements(By.CSS_SELECTOR, ".icon")
                            weakness_type = None
                            
                            if weakness_icons:
                                icon_class = weakness_icons[0].get_attribute("class")
                                
                                energy_map = {
                                    "icon-grass": "草",
                                    "icon-fire": "炎",
                                    "icon-water": "水",
                                    "icon-lightning": "雷",
                                    "icon-psychic": "超",
                                    "icon-fighting": "闘",
                                    "icon-darkness": "悪",
                                    "icon-metal": "鋼",
                                    "icon-dragon": "ドラゴン",
                                    "icon-fairy": "フェアリー",
                                    "icon-colorless": "無色"
                                }
                                
                                for key, value in energy_map.items():
                                    if key in icon_class:
                                        weakness_type = value
                                        break
                            
                            detail["weakness"] =  weakness_type,
                            print(f"    ⚠️ 弱点: {weakness_type} ")
                        else:
                            detail["weakness"] = None
                    else:
                        detail["weakness"] = None
                    
                    # 抵抗力
                    if len(cells) > 1:
                        resistance_cell = cells[1]
                        resistance_text = resistance_cell.text.strip()
                        
                        if resistance_text and resistance_text != "--":
                            # アイコンからタイプを取得
                            resistance_icons = resistance_cell.find_elements(By.CSS_SELECTOR, ".icon")
                            resistance_type = None
                            
                            if resistance_icons:
                                icon_class = resistance_icons[0].get_attribute("class")
                                
                                energy_map = {
                                    "icon-grass": "草",
                                    "icon-fire": "炎",
                                    "icon-water": "水",
                                    "icon-lightning": "雷",
                                    "icon-psychic": "超",
                                    "icon-fighting": "闘",
                                    "icon-darkness": "悪",
                                    "icon-metal": "鋼",
                                    "icon-dragon": "ドラゴン",
                                    "icon-fairy": "フェアリー",
                                    "icon-colorless": "無色"
                                }
                                
                                for key, value in energy_map.items():
                                    if key in icon_class:
                                        resistance_type = value
                                        break
                            
                            # 軽減値を取得
                            reduction_match = re.search(r'-(\d+)', resistance_text)
                            reduction = f"-{reduction_match.group(1)}" if reduction_match else "-20"
                            
                            detail["resistance"] = {
                                "type": resistance_type,
                                "value": reduction
                            }
                            print(f"    🛡️ 抵抗力: {resistance_type} {reduction}")
                        else:
                            detail["resistance"] = None
                    else:
                        detail["resistance"] = None
                    
                    # 逃げるエネルギー
                    if len(cells) > 2:
                        escape_icons = cells[2].find_elements(By.CSS_SELECTOR, ".icon")
                        detail["retreat_cost"] = len(escape_icons)
                        print(f"    🏃 逃げエネ: {detail['retreat_cost']}")
                    else:
                        detail["retreat_cost"] = 0
            
            except Exception as e:
                print(f"    ⚠️ テーブル情報取得失敗: {e}")
                detail["weakness"] = None
                detail["resistance"] = None
                detail["retreat_cost"] = 0
            
            return detail
        
        except Exception as e:
            print(f"    ❌ 抽出エラー: {e}")
            import traceback
            traceback.print_exc()
            return {}
    
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
    print("=" * 60)
    print("🎴 ポケモンカード ウィンドウ切り替え修正版")
    print("=" * 60)
    
    scraper = FixedWindowScraper(headless=True)  # 画面非表示で確認
    
    try:
        list_url = "https://www.pokemon-card.com/card-search"
        # list_url = "https://www.pokemon-card.com/card-search/?keyword=ピカチュウ"
        
        # カード一覧を取得
        cards = scraper.scrape_card_list(
            # keyword="ピカチュウ",
            max_cards=3
        )
        
        if len(cards) == 0:
            print("\n❌ カードが取得できませんでした")
            return
        
        # 各カードの詳細を取得
        detailed_cards = []
        
        for i, card in enumerate(cards, 1):
            print(f"\n[{i}/{len(cards)}] 処理中...")
            
            detail = scraper.scrape_card_detail(card, list_url)
            
            if detail:
                full_card = {**card, **detail}
                detailed_cards.append(full_card)
            
            time.sleep(2)
        
        # 保存
        scraper.save_to_json(
            detailed_cards,
            "backend/data/scraped/raw/pikachu_fixed.json"
        )
        
        print("\n" + "=" * 60)
        print("✅ すべての処理が完了しました！")
        print("=" * 60)
        print(f"\n📊 取得カード数: {len(detailed_cards)}枚")
        print(f"💾 保存先: backend/data/scraped/raw/pikachu_fixed.json")
        
        print(f"\n📁 デバッグファイル:")
        print(f"  - backend/data/scraped/raw/detail_*.html")
        print(f"  - backend/data/scraped/raw/detail_*.png")
        
    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        scraper.close()


if __name__ == "__main__":
    main()