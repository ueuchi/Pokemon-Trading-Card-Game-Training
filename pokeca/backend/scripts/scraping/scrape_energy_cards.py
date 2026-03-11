"""
基本エネルギーカード スクレイピングスクリプト

対象URL:
  https://www.pokemon-card.com/card-search/index.php?
    keyword=&se_ta=energy&regulation_sidebar_form=all&sc_energy_basic=1&
    pg=&illust=&sm_and_keyword=true

処理内容:
  1. 全ページ（最大 MAX_PAGES ページ）を巡回してカード一覧を取得
  2. 各カードの画像を data/scraped/processed/energy/ にダウンロード
  3. 取得結果を data/scraped/raw/energy_cards.json に保存
  4. 中断・再実行に対応（取得済みファイルはスキップ）

実行方法:
  cd pokeca/backend
  python3 scripts/scraping/scrape_energy_cards.py

オプション:
  --headless  : デフォルトTrue（ブラウザ非表示）
  --max-pages : 取得ページ数の上限（デフォルト: 全ページ）
  --dry-run   : 画像ダウンロードせずにカード情報のみ取得
"""

import os
import sys
import json
import time
import re
import argparse
import requests
from pathlib import Path
from urllib.parse import urlparse

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# ==================== 定数 ====================

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # backend/

SEARCH_BASE_URL = (
    "https://www.pokemon-card.com/card-search/index.php"
    "?keyword=&se_ta=energy&regulation_sidebar_form=all"
    "&sc_energy_basic=1&pg=&illust=&sm_and_keyword=true"
    "&page={page}"
)

OUTPUT_IMAGE_DIR = BASE_DIR / "data" / "scraped" / "processed" / "energy"
OUTPUT_JSON_PATH = BASE_DIR / "data" / "scraped" / "raw" / "energy_cards.json"

CARD_ITEM_SELECTOR   = "li.List_item"
NEXT_PAGE_SELECTOR   = "a.next"               # 「次のページ」ボタン
PAGE_INFO_SELECTOR   = "p.pager_text"         # 「17ページ中 1ページ目」
IMG_SELECTOR         = "img"

PAGE_WAIT_SEC        = 4    # ページ読み込み待機（秒）
SCROLL_WAIT_SEC      = 1    # スクロール後待機（秒）
DOWNLOAD_WAIT_SEC    = 0.5  # 画像ダウンロード間隔（秒）
MAX_RETRIES          = 3    # ページ取得リトライ回数


# ==================== セットアップ ====================

def build_driver(headless: bool) -> webdriver.Chrome:
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--disable-gpu")
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=opts)


def scroll_to_bottom(driver: webdriver.Chrome, times: int = 3) -> None:
    for _ in range(times):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(SCROLL_WAIT_SEC)


# ==================== ページ取得 ====================

def get_total_pages(driver: webdriver.Chrome) -> int:
    """ページ数を取得（例：「17ページ中 1ページ目」→ 17）"""
    try:
        text = driver.find_element(By.CSS_SELECTOR, PAGE_INFO_SELECTOR).text
        # 「N ページ中」を抽出
        m = re.search(r'(\d+)\s*ページ中', text)
        if m:
            return int(m.group(1))
    except Exception:
        pass
    # フォールバック: 「次のページ」があれば継続
    return 99


def scrape_page(driver: webdriver.Chrome, page: int) -> list[dict]:
    """1ページ分のカード情報を取得"""
    url = SEARCH_BASE_URL.format(page=page)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"\n  📄 ページ {page} 取得中 (attempt {attempt}): {url}")
            driver.get(url)
            time.sleep(PAGE_WAIT_SEC)
            scroll_to_bottom(driver)

            items = driver.find_elements(By.CSS_SELECTOR, CARD_ITEM_SELECTOR)
            if not items:
                print(f"  ⚠️  カード要素が見つかりません（ページ {page}）")
                return []

            cards = []
            for item in items:
                try:
                    img = item.find_element(By.TAG_NAME, IMG_SELECTOR)
                    name = img.get_attribute("alt") or ""
                    img_src = img.get_attribute("src") or ""

                    # 相対URLを絶対URLに変換
                    if img_src and not img_src.startswith("http"):
                        img_src = f"https://www.pokemon-card.com{img_src}"

                    # カード詳細URLを取得
                    try:
                        link = item.find_element(By.TAG_NAME, "a")
                        detail_url = link.get_attribute("href") or ""
                        if detail_url and not detail_url.startswith("http"):
                            detail_url = f"https://www.pokemon-card.com{detail_url}"
                    except Exception:
                        detail_url = ""

                    if name:
                        cards.append({
                            "name": name,
                            "image_url": img_src,
                            "detail_url": detail_url,
                            "page": page,
                        })

                except Exception as e:
                    continue

            print(f"  ✅ {len(cards)} 件取得")
            return cards

        except Exception as e:
            print(f"  ❌ エラー (attempt {attempt}): {e}")
            if attempt < MAX_RETRIES:
                time.sleep(3)

    return []


def has_next_page(driver: webdriver.Chrome) -> bool:
    """「次のページ」リンクが存在するか確認"""
    try:
        elements = driver.find_elements(By.CSS_SELECTOR, NEXT_PAGE_SELECTOR)
        return len(elements) > 0
    except Exception:
        return False


# ==================== 画像ダウンロード ====================

def safe_filename(name: str, url: str, index: int) -> str:
    """
    ファイル名を安全な形式に変換。
    同名カードが複数存在するのでインデックスを付加する。
    """
    safe = re.sub(r'[\\/:*?"<>|]', '_', name).strip()
    ext = Path(urlparse(url).path).suffix or ".jpg"
    return f"{index:04d}_{safe}{ext}"


def download_image(url: str, save_path: Path, retries: int = 3) -> bool:
    if save_path.exists():
        print(f"    ⏭️  スキップ（取得済み）: {save_path.name}")
        return True

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": "https://www.pokemon-card.com/",
    }

    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            save_path.parent.mkdir(parents=True, exist_ok=True)
            save_path.write_bytes(resp.content)
            print(f"    ⬇️  ダウンロード完了: {save_path.name}")
            return True
        except Exception as e:
            print(f"    ❌ ダウンロード失敗 (attempt {attempt}): {e}")
            if attempt < retries:
                time.sleep(2)

    return False


# ==================== メイン処理 ====================

def load_existing(json_path: Path) -> list[dict]:
    if json_path.exists():
        try:
            return json.loads(json_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def save_json(data: list[dict], json_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main(headless: bool, max_pages: int, dry_run: bool) -> None:
    print("=" * 60)
    print("🔋 基本エネルギーカード スクレイピング開始")
    print(f"   保存先（画像）: {OUTPUT_IMAGE_DIR}")
    print(f"   保存先（JSON） : {OUTPUT_JSON_PATH}")
    print(f"   headless={headless}  dry_run={dry_run}  max_pages={max_pages}")
    print("=" * 60)

    OUTPUT_IMAGE_DIR.mkdir(parents=True, exist_ok=True)

    # 既存データを読み込み（再実行時に追記）
    all_cards: list[dict] = load_existing(OUTPUT_JSON_PATH)
    existing_urls = {c["image_url"] for c in all_cards}
    print(f"\n📂 既存データ: {len(all_cards)} 件")

    driver = build_driver(headless)

    try:
        # 1ページ目を読み込んでページ数を取得
        driver.get(SEARCH_BASE_URL.format(page=1))
        time.sleep(PAGE_WAIT_SEC)
        total_pages = get_total_pages(driver)
        total_pages = min(total_pages, max_pages)
        print(f"\n📊 取得対象: {total_pages} ページ")

        new_cards: list[dict] = []

        for page in range(1, total_pages + 1):
            print(f"\n{'─'*50}")
            print(f"🗂️  ページ {page} / {total_pages}")

            page_cards = scrape_page(driver, page)

            # 重複排除
            for card in page_cards:
                if card["image_url"] not in existing_urls:
                    new_cards.append(card)
                    existing_urls.add(card["image_url"])

            # 中間保存（10ページごと）
            if page % 10 == 0:
                save_json(all_cards + new_cards, OUTPUT_JSON_PATH)
                print(f"  💾 中間保存: {len(all_cards) + len(new_cards)} 件")

            # 最終ページ判定
            if not has_next_page(driver) and page < total_pages:
                print(f"\n  ℹ️  「次のページ」が見つからないため終了 (page={page})")
                break

            time.sleep(1)

    finally:
        driver.quit()

    # JSON保存
    all_cards.extend(new_cards)
    save_json(all_cards, OUTPUT_JSON_PATH)
    print(f"\n✅ JSON保存完了: {OUTPUT_JSON_PATH}  （合計 {len(all_cards)} 件）")

    # 画像ダウンロード
    if dry_run:
        print("\n⚡ dry-run モード: 画像ダウンロードをスキップ")
    else:
        print(f"\n{'='*60}")
        print(f"📥 画像ダウンロード開始（新規 {len(new_cards)} 件）")
        print(f"{'='*60}")

        success = 0
        for i, card in enumerate(all_cards, 1):
            fname = safe_filename(card["name"], card["image_url"], i)
            save_path = OUTPUT_IMAGE_DIR / fname

            # image_url をファイルパスと紐付けて更新
            card["local_path"] = str(save_path.relative_to(BASE_DIR))

            if card["image_url"]:
                ok = download_image(card["image_url"], save_path)
                if ok:
                    success += 1
            time.sleep(DOWNLOAD_WAIT_SEC)

        # local_path を追記して再保存
        save_json(all_cards, OUTPUT_JSON_PATH)

        print(f"\n{'='*60}")
        print(f"🎉 完了！  成功: {success} / {len(all_cards)} 件")
        print(f"   画像保存先: {OUTPUT_IMAGE_DIR}")
        print(f"   JSON保存先: {OUTPUT_JSON_PATH}")
        print(f"{'='*60}")


# ==================== エントリポイント ====================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="基本エネルギーカードスクレイピング")
    parser.add_argument(
        "--no-headless", action="store_true",
        help="ブラウザを表示して実行（デバッグ用）"
    )
    parser.add_argument(
        "--max-pages", type=int, default=9999,
        help="取得するページ数の上限（デフォルト: 全件）"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="画像ダウンロードせずカード情報のみ取得"
    )
    args = parser.parse_args()

    main(
        headless=not args.no_headless,
        max_pages=args.max_pages,
        dry_run=args.dry_run,
    )
