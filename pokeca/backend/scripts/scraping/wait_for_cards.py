"""
明示的待機を使用したスクレイパー
"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import time
import json
import os

print("🔧 初期化中...")
chrome_options = Options()
# chrome_options.add_argument('--headless')
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=chrome_options)

try:
    url = "https://www.pokemon-card.com/card-search/?keyword=ピカチュウ"
    print(f"📍 アクセス: {url}")
    driver.get(url)
    
    # 特定の要素が表示されるまで待機（最大60秒）
    print("⏳ カード要素が表示されるまで待機（最大60秒）...")
    
    # 試すセレクタのリスト
    selectors_to_try = [
        "img[src*='card']",
        "a[href*='card']", 
        "li",
        "div[class*='card']",
        "div[class*='result']"
    ]
    
    found = False
    for selector in selectors_to_try:
        try:
            print(f"  試行中: {selector}")
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            print(f"  ✅ 見つかった: {len(elements)}個")
            found = True
            break
        except:
            print(f"  ❌ 見つからない")
            continue
    
    if not found:
        print("\n⚠️ どのセレクタでも要素が見つかりませんでした")
    
    # さらに待機
    print("\n⏳ 追加で20秒待機...")
    time.sleep(20)
    
    # ページのHTMLを保存
    print("\n💾 HTMLを保存...")
    os.makedirs("backend/data/scraped/raw", exist_ok=True)
    with open("backend/data/scraped/raw/wait_debug.html", "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    
    # スクリーンショット
    driver.save_screenshot("backend/data/scraped/raw/wait_debug.png")
    
    # ページのテキストを表示
    body_text = driver.find_element(By.TAG_NAME, "body").text
    print("\n📝 ページテキスト（最初の1000文字）:")
    print(body_text[:1000])
    
    print("\n✅ 保存完了:")
    print("  - backend/data/scraped/raw/wait_debug.html")
    print("  - backend/data/scraped/raw/wait_debug.png")
    
    print("\n30秒後に閉じます...")
    time.sleep(30)

except Exception as e:
    print(f"\n❌ エラー: {e}")
    import traceback
    traceback.print_exc()

finally:
    driver.quit()