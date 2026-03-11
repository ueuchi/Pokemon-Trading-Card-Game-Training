"""
DBに登録されているカードの攻撃テキストを公式サイトからスクレイピングする。

処理フロー:
  1. DBのcardsテーブルからポケモンカードを一覧取得
  2. 各カード名で公式サイトを検索 → 最もマッチするカードの詳細URLを取得
  3. 詳細ページからワザ名・ダメージ・効果テキストをスクレイピング
  4. data/scraped/raw/card_attacks.json に保存

使い方:
  python scrape_attacks.py              # 全カードを処理
  python scrape_attacks.py --dry-run    # DB読み込みのみ（通信なし）
  python scrape_attacks.py --no-headless # ブラウザを表示して実行
"""
import sys
import os
import json
import time
import sqlite3
import re

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))
DB_PATH = os.path.join(BACKEND_DIR, "data", "pokemon_cards.db")
OUTPUT_PATH = os.path.join(BACKEND_DIR, "data", "scraped", "raw", "card_attacks.json")
SEARCH_URL = "https://www.pokemon-card.com/card-search/index.php?keyword={name}&sm_and_keyword=true"
DETAIL_BASE = "https://www.pokemon-card.com"
WAIT_SEC = 2.0  # サーバー負荷軽減のウェイト


def get_driver(headless: bool = True):
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from webdriver_manager.chrome import ChromeDriverManager

    options = Options()
    if headless:
        options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1280,900")
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)


def fetch_card_attacks(driver, card_name: str) -> list[dict]:
    """
    公式サイトで card_name を検索し、最初にヒットしたカードのワザ情報を返す。

    Returns:
        [{"name": str, "damage": int, "description": str}, ...]
    """
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    url = SEARCH_URL.format(name=card_name)
    driver.get(url)
    time.sleep(WAIT_SEC)

    # 検索結果から最初のカードの詳細リンクを取得
    try:
        wait = WebDriverWait(driver, 8)
        # カード一覧コンテナ
        first_card = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "ul.card-list li a, .cardList li a"))
        )
        detail_href = first_card.get_attribute("href")
        if not detail_href:
            print(f"  [WARN] 詳細URLが取得できません: {card_name}")
            return []
    except Exception as e:
        print(f"  [WARN] 検索結果なし: {card_name} ({e})")
        return []

    # 詳細ページに移動
    detail_url = detail_href if detail_href.startswith("http") else DETAIL_BASE + detail_href
    driver.get(detail_url)
    time.sleep(WAIT_SEC)

    attacks = []
    try:
        from selenium.webdriver.common.by import By

        # ワザブロックを取得（公式サイトのCSS構造に合わせて複数セレクタ試行）
        waza_blocks = driver.find_elements(By.CSS_SELECTOR,
            "section.skills-wrap .skill, .skills .skill, div.skill")

        if not waza_blocks:
            # 別の構造パターン
            waza_blocks = driver.find_elements(By.CSS_SELECTOR, "table.skills tr")

        for block in waza_blocks:
            attack = {}
            # ワザ名
            try:
                name_el = block.find_element(By.CSS_SELECTOR,
                    ".skill-name, h4, .name, td.name")
                attack["name"] = name_el.text.strip()
            except Exception:
                continue

            if not attack["name"]:
                continue

            # ダメージ
            try:
                dmg_el = block.find_element(By.CSS_SELECTOR,
                    ".skill-damage, .damage, td.damage")
                dmg_text = dmg_el.text.strip()
                dmg_num = re.sub(r"[^\d]", "", dmg_text)
                attack["damage"] = int(dmg_num) if dmg_num else 0
            except Exception:
                attack["damage"] = 0

            # 効果テキスト
            try:
                desc_el = block.find_element(By.CSS_SELECTOR,
                    ".skill-description, .description, .text, td.text")
                attack["description"] = desc_el.text.strip()
            except Exception:
                attack["description"] = ""

            attacks.append(attack)

    except Exception as e:
        print(f"  [WARN] ワザ取得エラー: {card_name} ({e})")

    return attacks


def load_pokemon_cards_from_db() -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, name, attacks FROM cards WHERE card_type = 'pokemon' ORDER BY id"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def load_existing_results() -> dict:
    """中間保存ファイルを読み込む（スキップ用）"""
    if os.path.exists(OUTPUT_PATH):
        with open(OUTPUT_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return {item["card_id"]: item for item in data}
    return {}


def save_results(results: list[dict]):
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)


def main(dry_run: bool = False, headless: bool = True):
    cards = load_pokemon_cards_from_db()
    print(f"対象カード: {len(cards)}件")

    if dry_run:
        print("\n[DRY-RUN] DBから取得したカード一覧:")
        for c in cards:
            existing_attacks = json.loads(c["attacks"] or "[]")
            print(f"  id={c['id']} {c['name']} / ワザ数={len(existing_attacks)}")
        return

    existing = load_existing_results()
    results = list(existing.values())
    already_ids = set(existing.keys())
    print(f"  スキップ済み: {len(already_ids)}件")

    driver = get_driver(headless=headless)
    try:
        for i, card in enumerate(cards):
            card_id = str(card["id"])
            if card_id in already_ids:
                print(f"[{i+1}/{len(cards)}] スキップ: {card['name']}")
                continue

            print(f"[{i+1}/{len(cards)}] スクレイピング: {card['name']}")
            scraped_attacks = fetch_card_attacks(driver, card["name"])

            result = {
                "card_id": card_id,
                "card_name": card["name"],
                "scraped_attacks": scraped_attacks,
            }
            results.append(result)

            # 中間保存
            save_results(results)
            print(f"  → ワザ {len(scraped_attacks)}件取得")

            # サーバー負荷軽減
            time.sleep(WAIT_SEC)

    finally:
        driver.quit()

    print(f"\n完了: {len(results)}件保存 → {OUTPUT_PATH}")


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    headless = "--no-headless" not in sys.argv
    main(dry_run=dry, headless=headless)
