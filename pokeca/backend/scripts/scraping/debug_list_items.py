"""
List_item の中身を詳しく調査
"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import time

print("🔧 初期化中...")
chrome_options = Options()
# chrome_options.add_argument('--headless')
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=chrome_options)

try:
    url = "https://www.pokemon-card.com/card-search/?keyword=ピカチュウ"
    print(f"📍 アクセス: {url}")
    driver.get(url)
    
    print("⏳ 待機（30秒）...")
    time.sleep(30)
    
    print("📜 スクロール...")
    for i in range(3):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
    
    print("\n🔍 List_item を調査:")
    items = driver.find_elements(By.CSS_SELECTOR, "li.List_item")
    print(f"合計: {len(items)}個\n")
    
    for i, item in enumerate(items[:5], 1):  # 最初の5個だけ調査
        print(f"{'='*60}")
        print(f"要素 {i}:")
        print(f"{'='*60}")
        
        # 要素のHTML全体を表示
        print("\nHTML:")
        print(item.get_attribute('outerHTML')[:500])
        
        # テキスト内容
        print(f"\nテキスト: {item.text[:100]}")
        
        # img要素を探す
        print("\n🔍 img要素を検索:")
        try:
            imgs = item.find_elements(By.TAG_NAME, "img")
            print(f"  見つかった数: {len(imgs)}個")
            for j, img in enumerate(imgs, 1):
                print(f"  img[{j}]:")
                print(f"    alt: {img.get_attribute('alt')}")
                print(f"    src: {img.get_attribute('src')[:80] if img.get_attribute('src') else 'なし'}")
        except Exception as e:
            print(f"  ❌ エラー: {e}")
        
        # a要素を探す
        print("\n🔍 a要素を検索:")
        try:
            links = item.find_elements(By.TAG_NAME, "a")
            print(f"  見つかった数: {len(links)}個")
            for j, link in enumerate(links, 1):
                print(f"  a[{j}]:")
                print(f"    href: {link.get_attribute('href')}")
                print(f"    text: {link.text[:50]}")
        except Exception as e:
            print(f"  ❌ エラー: {e}")
        
        print()
    
    print("\n30秒後に閉じます...")
    time.sleep(30)

except Exception as e:
    print(f"\n❌ エラー: {e}")
    import traceback
    traceback.print_exc()

finally:
    driver.quit()