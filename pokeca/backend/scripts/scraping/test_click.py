"""
カードをクリックしてみるテスト
"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import time

print("🔧 初期化中...")
chrome_options = Options()
# chrome_options.add_argument('--headless')  # 画面を見たいのでコメントアウト
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=chrome_options)

try:
    url = "https://www.pokemon-card.com/card-search/?keyword=ピカチュウ"
    print(f"📍 アクセス: {url}")
    driver.get(url)
    
    print("⏳ 待機（30秒）...")
    time.sleep(30)
    
    print("\n🔍 最初のカードを取得...")
    items = driver.find_elements(By.CSS_SELECTOR, "li.List_item")
    
    if len(items) == 0:
        print("❌ カードが見つかりません")
    else:
        print(f"✅ {len(items)}枚のカードを発見")
        
        first_item = items[0]
        
        # カード名を取得
        img = first_item.find_element(By.TAG_NAME, "img")
        card_name = img.get_attribute("alt")
        print(f"\n📛 最初のカード: {card_name}")
        
        # カードをクリック
        print("\n👆 カードをクリックします...")
        link = first_item.find_element(By.TAG_NAME, "a")
        link.click()
        
        print("⏳ モーダル表示を待機（10秒）...")
        time.sleep(10)
        
        # ページのHTMLを保存
        print("\n💾 クリック後のHTMLを保存...")
        with open("backend/data/scraped/raw/after_click.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        
        # スクリーンショット
        driver.save_screenshot("backend/data/scraped/raw/after_click.png")
        
        print("\n✅ 保存完了:")
        print("  - backend/data/scraped/raw/after_click.html")
        print("  - backend/data/scraped/raw/after_click.png")
        
        # ページのテキストを表示
        body_text = driver.find_element(By.TAG_NAME, "body").text
        print(f"\n📝 ページテキスト（先頭1000文字）:")
        print(body_text[:1000])
    
    print("\n\n60秒後に閉じます（HTMLを確認してください）...")
    time.sleep(60)

except Exception as e:
    print(f"\n❌ エラー: {e}")
    import traceback
    traceback.print_exc()

finally:
    driver.quit()