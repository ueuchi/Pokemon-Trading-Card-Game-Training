"""
デバッグ用：実際のサイト構造を確認
"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import time
import os

print("=" * 60)
print("🔍 ポケモンカード公式サイト構造チェック")
print("=" * 60)

# Chromeを起動（画面表示あり）
chrome_options = Options()
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=chrome_options)

try:
    url = "https://www.pokemon-card.com/card-search/?keyword=ピカチュウ"
    print(f"\n📍 アクセス: {url}")
    driver.get(url)
    
    print("\n⏳ ページ読み込み待機（10秒）...")
    time.sleep(10)
    
    print(f"\n📄 ページタイトル: {driver.title}")
    
    # スクリーンショット保存
    os.makedirs("backend/data/scraped/raw", exist_ok=True)
    screenshot_path = "backend/data/scraped/raw/debug_screenshot.png"
    driver.save_screenshot(screenshot_path)
    print(f"📸 スクリーンショット保存: {screenshot_path}")
    
    # HTMLをファイルに保存
    html_path = "backend/data/scraped/raw/debug_page.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    print(f"💾 HTML保存: {html_path}")
    
    # 様々なセレクタを試す
    print("\n🔍 カード要素の検索:")
    
    selectors = [
        ("section.card-list-section li", "現在のスクリプト"),
        ("div.card-list li", "パターン1"),
        ("ul.card-list li", "パターン2"),
        ("li.card-item", "パターン3"),
        ("div.result-list li", "パターン4"),
        ("ul li", "全てのli要素"),
        ("img[alt]", "画像要素"),
        ("a[href*='details']", "詳細リンク"),
    ]
    
    found_selector = None
    max_elements = 0
    
    for selector, description in selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            count = len(elements)
            status = "✅" if count > 0 else "❌"
            print(f"  {status} {description}: '{selector}' → {count}個")
            
            if count > max_elements:
                max_elements = count
                found_selector = selector
                
            if count > 0 and count < 100:
                for i, elem in enumerate(elements[:3]):
                    try:
                        text = elem.text[:50] if elem.text else "[テキストなし]"
                        print(f"      [{i+1}] {text}")
                    except:
                        pass
        except Exception as e:
            print(f"  ⚠️ {description}: エラー ({e})")
    
    if found_selector:
        print(f"\n🎯 最も多く見つかったセレクタ: '{found_selector}' ({max_elements}個)")
    
    # ページのbody全体のテキストを確認
    try:
        body_text = driver.find_element(By.TAG_NAME, "body").text[:500]
        print(f"\n📝 ページのテキスト（先頭500文字）:")
        print(body_text)
    except:
        pass
    
    print("\n" + "=" * 60)
    print("✅ 調査完了")
    print("=" * 60)
    print("\n次のステップ:")
    print("1. backend/data/scraped/raw/debug_screenshot.png を開いて画面を確認")
    print("2. backend/data/scraped/raw/debug_page.html を開いてHTML構造を確認")
    print("3. 上記の結果を報告してください")
    print("\nブラウザは30秒後に閉じます...")
    time.sleep(30)
    
except Exception as e:
    print(f"\n❌ エラー発生: {e}")
    import traceback
    traceback.print_exc()

finally:
    driver.quit()
    print("\n✅ ブラウザを閉じました")