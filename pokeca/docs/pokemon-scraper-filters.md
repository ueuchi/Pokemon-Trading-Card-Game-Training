# 🎴 ポケモンカード スクレイピング拡張版
# 商品ID取得 & タイプ別・特性別フィルタリング

## 📦 追加機能

### 1. 商品ID一覧取得スクリプト

```python
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
```

### 実行すると生成されるファイル: `backend/data/scraped/product_ids.json`

```json
[
  {
    "id": "1234",
    "name": "スカーレットex"
  },
  {
    "id": "1235",
    "name": "バイオレットex"
  },
  {
    "id": "869",
    "name": "VSTARユニバース"
  },
  {
    "id": "1236",
    "name": "トリプレットビート"
  }
]
```

---

## 🎯 2. タイプ別・特性別フィルタリング

### タイプ別・EX別で取得する拡張版スクレイパー

```python
"""
タイプ別・特性別フィルタリング機能付きスクレイパー
backend/scripts/scraping/scraper_advanced.py
"""

from scraper import PokemonCardScraper  # 既存のスクレイパーをインポート
import json

class AdvancedScraper(PokemonCardScraper):
    """
    既存のスクレイパーを拡張
    タイプ別・特性別フィルタリング機能を追加
    """
    
    def filter_by_type(self, cards, card_type):
        """
        タイプでフィルタリング
        
        Args:
            cards: カードのリスト
            card_type: フィルタするタイプ（"炎", "水", "雷" など）
        
        Returns:
            フィルタされたカードリスト
        """
        filtered = [card for card in cards if card.get('type') == card_type]
        print(f"🔍 {card_type}タイプ: {len(filtered)}枚")
        return filtered
    
    def filter_by_category(self, cards, category):
        """
        カテゴリでフィルタリング
        
        Args:
            cards: カードのリスト
            category: フィルタするカテゴリ（"ポケモン", "トレーナー", "エネルギー"）
        
        Returns:
            フィルタされたカードリスト
        """
        filtered = [card for card in cards if card.get('category') == category]
        print(f"🔍 {category}: {len(filtered)}枚")
        return filtered
    
    def filter_by_evolution_stage(self, cards, stage):
        """
        進化段階でフィルタリング
        
        Args:
            cards: カードのリスト
            stage: 進化段階（"たね", "1進化", "2進化"）
        
        Returns:
            フィルタされたカードリスト
        """
        filtered = [card for card in cards if card.get('evolution_stage') == stage]
        print(f"🔍 {stage}ポケモン: {len(filtered)}枚")
        return filtered
    
    def filter_by_name_pattern(self, cards, pattern):
        """
        名前のパターンでフィルタリング（EX, V, VMAX, VSTARなど）
        
        Args:
            cards: カードのリスト
            pattern: 名前に含まれるパターン（"ex", "V", "VMAX", "VSTAR"）
        
        Returns:
            フィルタされたカードリスト
        """
        filtered = [card for card in cards if pattern in card.get('name', '')]
        print(f"🔍 {pattern}を含むカード: {len(filtered)}枚")
        return filtered
    
    def filter_by_rarity(self, cards, rarity):
        """
        レアリティでフィルタリング
        
        Args:
            cards: カードのリスト
            rarity: レアリティ（"C", "U", "R", "RR", "SR", "UR"）
        
        Returns:
            フィルタされたカードリスト
        """
        filtered = [card for card in cards if card.get('rarity') == rarity]
        print(f"🔍 {rarity}レアリティ: {len(filtered)}枚")
        return filtered
    
    def filter_by_hp_range(self, cards, min_hp=None, max_hp=None):
        """
        HP範囲でフィルタリング
        
        Args:
            cards: カードのリスト
            min_hp: 最小HP
            max_hp: 最大HP
        
        Returns:
            フィルタされたカードリスト
        """
        filtered = []
        for card in cards:
            hp = card.get('hp')
            if hp is None:
                continue
            
            if min_hp is not None and hp < min_hp:
                continue
            if max_hp is not None and hp > max_hp:
                continue
            
            filtered.append(card)
        
        print(f"🔍 HP {min_hp}〜{max_hp}: {len(filtered)}枚")
        return filtered
    
    def get_statistics(self, cards):
        """
        カード統計情報を取得
        
        Args:
            cards: カードのリスト
        
        Returns:
            統計情報の辞書
        """
        stats = {
            "total": len(cards),
            "by_type": {},
            "by_category": {},
            "by_evolution": {},
            "by_rarity": {},
            "special_cards": {
                "ex": 0,
                "V": 0,
                "VMAX": 0,
                "VSTAR": 0
            }
        }
        
        for card in cards:
            # タイプ別
            card_type = card.get('type', '不明')
            stats['by_type'][card_type] = stats['by_type'].get(card_type, 0) + 1
            
            # カテゴリ別
            category = card.get('category', '不明')
            stats['by_category'][category] = stats['by_category'].get(category, 0) + 1
            
            # 進化段階別
            evolution = card.get('evolution_stage', '不明')
            stats['by_evolution'][evolution] = stats['by_evolution'].get(evolution, 0) + 1
            
            # レアリティ別
            rarity = card.get('rarity', '不明')
            stats['by_rarity'][rarity] = stats['by_rarity'].get(rarity, 0) + 1
            
            # 特殊カード
            name = card.get('name', '')
            if 'ex' in name:
                stats['special_cards']['ex'] += 1
            if 'V' in name and 'VMAX' not in name and 'VSTAR' not in name:
                stats['special_cards']['V'] += 1
            if 'VMAX' in name:
                stats['special_cards']['VMAX'] += 1
            if 'VSTAR' in name:
                stats['special_cards']['VSTAR'] += 1
        
        return stats
    
    def print_statistics(self, stats):
        """統計情報を表示"""
        print("\n" + "="*60)
        print("📊 カード統計")
        print("="*60)
        
        print(f"\n総カード数: {stats['total']}枚")
        
        print("\n【タイプ別】")
        for card_type, count in sorted(stats['by_type'].items(), key=lambda x: x[1], reverse=True):
            print(f"  {card_type}: {count}枚")
        
        print("\n【カテゴリ別】")
        for category, count in stats['by_category'].items():
            print(f"  {category}: {count}枚")
        
        print("\n【進化段階別】")
        for evolution, count in stats['by_evolution'].items():
            print(f"  {evolution}: {count}枚")
        
        print("\n【レアリティ別】")
        for rarity, count in sorted(stats['by_rarity'].items()):
            print(f"  {rarity}: {count}枚")
        
        print("\n【特殊カード】")
        for special_type, count in stats['special_cards'].items():
            print(f"  {special_type}: {count}枚")


def main():
    """
    使用例: タイプ別・特性別フィルタリング
    """
    print("=" * 60)
    print("🎴 ポケモンカード 拡張スクレイピングツール")
    print("=" * 60)
    
    scraper = AdvancedScraper(headless=True)
    
    try:
        # ============================================
        # 例1: 炎タイプのカードだけ取得
        # ============================================
        print("\n【例1】炎タイプのカードを取得")
        
        # まず全体を取得
        all_cards = scraper.scrape_card_list(product_id="869", max_cards=50)
        
        # 詳細情報を取得（簡易版、ここではスキップ）
        # ... 実際は詳細取得が必要
        
        # 炎タイプでフィルタ
        fire_cards = scraper.filter_by_type(all_cards, "炎")
        scraper.save_to_json(fire_cards, "backend/data/scraped/raw/fire_type.json")
        
        
        # ============================================
        # 例2: exポケモンだけ取得
        # ============================================
        print("\n【例2】exポケモンを取得")
        
        # キーワード検索で効率化
        ex_cards = scraper.scrape_card_list(keyword="ex", max_cards=30)
        
        # 詳細取得
        detailed_ex_cards = []
        for i, card in enumerate(ex_cards[:10], 1):  # 最初の10枚のみ
            print(f"\n[{i}/10] {card['name']}")
            detail = scraper.scrape_card_detail(card['url'])
            if detail:
                detailed_ex_cards.append(detail)
            time.sleep(2)
        
        scraper.save_to_json(detailed_ex_cards, "backend/data/scraped/raw/ex_pokemon.json")
        
        
        # ============================================
        # 例3: 統計情報を表示
        # ============================================
        print("\n【例3】カード統計を表示")
        
        # JSONから読み込み（既にスクレイピング済みの場合）
        with open("backend/data/scraped/raw/pikachu_detailed.json", 'r') as f:
            cards = json.load(f)
        
        stats = scraper.get_statistics(cards)
        scraper.print_statistics(stats)
        
        
        # ============================================
        # 例4: 複数条件でフィルタ
        # ============================================
        print("\n【例4】HP200以上の雷タイプexポケモン")
        
        # 条件1: 雷タイプ
        thunder_cards = scraper.filter_by_type(cards, "雷")
        
        # 条件2: exを含む
        thunder_ex = scraper.filter_by_name_pattern(thunder_cards, "ex")
        
        # 条件3: HP200以上
        high_hp_thunder_ex = scraper.filter_by_hp_range(thunder_ex, min_hp=200)
        
        scraper.save_to_json(high_hp_thunder_ex, "backend/data/scraped/raw/thunder_ex_high_hp.json")
        
        
        print("\n" + "="*60)
        print("✅ すべての処理が完了しました！")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        scraper.close()


if __name__ == "__main__":
    import time
    main()
```

---

## 🎯 3. 実用的な使用例

### ケース1: 炎タイプのカードだけ取得

```python
scraper = AdvancedScraper(headless=True)

# VSTARユニバースから全カード取得
cards = scraper.scrape_card_list(product_id="869", max_cards=None)

# 各カードの詳細を取得
detailed_cards = []
for card in cards:
    detail = scraper.scrape_card_detail(card['url'])
    if detail:
        detailed_cards.append(detail)
    time.sleep(2)

# 炎タイプでフィルタ
fire_cards = scraper.filter_by_type(detailed_cards, "炎")

# 保存
scraper.save_to_json(fire_cards, "backend/data/scraped/raw/fire_type.json")
```

### ケース2: exポケモンだけ取得

```python
# 方法1: キーワード検索（効率的）
ex_cards = scraper.scrape_card_list(keyword="ex", max_cards=None)

# 方法2: 全カード取得後にフィルタ
all_cards = scraper.scrape_card_list(max_cards=None)
ex_cards = scraper.filter_by_name_pattern(all_cards, "ex")
```

### ケース3: HP200以上のVMAXポケモン

```python
# 全カード取得
all_cards = scraper.scrape_card_list(max_cards=None)

# フィルタ1: VMAXを含む
vmax_cards = scraper.filter_by_name_pattern(all_cards, "VMAX")

# フィルタ2: HP200以上
high_hp_vmax = scraper.filter_by_hp_range(vmax_cards, min_hp=200)
```

### ケース4: 雷タイプのたねポケモンのみ

```python
# 全カード取得
all_cards = scraper.scrape_card_list(max_cards=None)

# フィルタ1: 雷タイプ
thunder_cards = scraper.filter_by_type(all_cards, "雷")

# フィルタ2: たねポケモン
thunder_basic = scraper.filter_by_evolution_stage(thunder_cards, "たね")
```

---

## 📊 4. 商品IDの一覧（主要な弾）

よく使われる商品IDの例：

| 商品名 | Product ID | 備考 |
|--------|-----------|------|
| スカーレットex | 1234 | 仮ID |
| バイオレットex | 1235 | 仮ID |
| VSTARユニバース | 869 | 例で使用 |
| トリプレットビート | 1236 | 仮ID |
| クレイバースト | 1237 | 仮ID |
| スノーハザード | 1238 | 仮ID |

※ 正確なIDは `get_product_ids.py` で取得してください

---

## 📝 まとめ

### 質問1: IDはどこから取得？
**3つの方法:**
1. ブラウザでURLを確認（簡単）
2. `get_product_ids.py` で自動取得（推奨）
3. 公式サイトのセレクトボックスから確認

### 質問2: タイプ別・EX別で取得するには？
**2つのアプローチ:**
1. **検索時に絞る**: `keyword="ex"` でexポケモンのみ検索
2. **取得後に絞る**: 全カード取得 → `filter_by_type()` でフィルタ

### おすすめの流れ
```python
# 1. 商品ID一覧を取得
python get_product_ids.py

# 2. 特定の弾からカードを取得
cards = scraper.scrape_card_list(product_id="869")

# 3. フィルタリング
fire_cards = scraper.filter_by_type(cards, "炎")
ex_cards = scraper.filter_by_name_pattern(cards, "ex")
```

どのコードが必要ですか？全部まとめて提供しますか？🚀
