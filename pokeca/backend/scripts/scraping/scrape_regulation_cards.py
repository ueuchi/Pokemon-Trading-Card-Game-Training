"""
スタンダードレギュレーション（H/I/J）カード全件スクレイピング

処理フロー:
    1. 指定URLを開く
    2. 検索条件「スタンダード」を適用（既に適用済みならそのまま）
    3. ページネーションを辿って全カードの詳細URLを収集
    4. 各詳細ページからカード情報を取得
    5. レギュレーションマークが H/I/J のカードのみ保存

使い方:
    python scrape_regulation_cards.py                         # H/I/J 全件
    python scrape_regulation_cards.py --marks H,I,J          # 対象マーク指定
    python scrape_regulation_cards.py --limit 50             # テスト用件数制限
    python scrape_regulation_cards.py --no-headless          # ブラウザ表示
    python scrape_regulation_cards.py --list-only            # URL収集のみ
"""

import sys
import os
import json
import time
import re
import argparse
import html
from urllib.parse import urljoin

import requests

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))
RAW_DIR = os.path.join(BACKEND_DIR, "data", "scraped", "raw")
SEARCH_BASE = "https://www.pokemon-card.com/card-search/index.php"
STANDARD_SEARCH_URL = (
    "https://www.pokemon-card.com/card-search/index.php"
    "?keyword=&se_ta=&regulation_sidebar_form=XY&pg=&illust=&sm_and_keyword=true"
)
DETAIL_BASE = "https://www.pokemon-card.com"
WAIT_SEC = 1.5
DEFAULT_TARGET_MARKS = {"H", "I", "J"}
REQUEST_TIMEOUT_SEC = 20


# ──────────────────────────────────────────────
# Selenium セットアップ
# ──────────────────────────────────────────────

def _find_cached_chromedriver() -> str | None:
    """~/.wdm キャッシュから最新の chromedriver バイナリを返す"""
    import glob
    import platform

    arch = platform.machine().lower()
    if "arm" in arch or "aarch" in arch:
        patterns = [
            os.path.expanduser("~/.wdm/drivers/chromedriver/mac64/*/chromedriver-mac-arm64/chromedriver"),
            os.path.expanduser("~/.wdm/drivers/chromedriver/mac_arm64/*/chromedriver"),
        ]
    else:
        patterns = [
            os.path.expanduser("~/.wdm/drivers/chromedriver/mac64/*/chromedriver-mac-x64/chromedriver"),
            os.path.expanduser("~/.wdm/drivers/chromedriver/mac64/*/chromedriver"),
        ]

    candidates = []
    for pattern in patterns:
        candidates.extend(glob.glob(pattern))

    if not candidates:
        return None
    # バージョン番号で降順ソート（最新版を選択）
    candidates.sort(reverse=True)
    return candidates[0]


def get_driver(headless: bool = True):
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager

    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1280,900")
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)
    driver.implicitly_wait(5)
    return driver


# ──────────────────────────────────────────────
# Phase 1: カード詳細URLを収集
# ──────────────────────────────────────────────

def _ensure_standard_condition(driver) -> None:
    """検索条件「スタンダード」を適用する（適用済みなら変更なし）。"""
    from selenium.webdriver.common.by import By

    # まずは select の選択状態がすでに「スタンダード」か確認
    selected_standard = bool(driver.execute_script("""
const selects = Array.from(document.querySelectorAll('select'));
return selects.some(select => {
  const current = select.options && select.options[select.selectedIndex];
  return current && (current.textContent || '').includes('スタンダード');
});
"""))
    if selected_standard:
        return

    # select から「スタンダード」を選択（構造変更に備えて JS で横断探索）
    script = """
const selects = Array.from(document.querySelectorAll('select'));
let changed = false;
for (const select of selects) {
  const option = Array.from(select.options || []).find(o => (o.textContent || '').includes('スタンダード'));
  if (option) {
    select.value = option.value;
    select.dispatchEvent(new Event('change', { bubbles: true }));
    changed = true;
  }
}
return changed;
"""
    changed = bool(driver.execute_script(script))
    if changed:
        time.sleep(2)

    # 注意: 「条件を追加する」ボタンはクリックしない
    # （条件追加UIを開くだけで一覧取得には不要なため）


def _extract_cards_from_html(page_html: str) -> list[dict]:
    """一覧ページHTMLからカード情報（name/url/image_url）を抽出する。"""
    cards = []

    # li.List_item 単位で抽出
    li_blocks = re.findall(
        r"<li[^>]*class=[\"'][^\"']*List_item[^\"']*[\"'][^>]*>(.*?)</li>",
        page_html,
        flags=re.DOTALL | re.IGNORECASE,
    )

    for block in li_blocks:
        href_match = re.search(r"<a[^>]*href=[\"']([^\"']+)[\"']", block, flags=re.IGNORECASE)
        img_match = re.search(r"<img[^>]*>", block, flags=re.IGNORECASE)
        if not href_match or not img_match:
            continue

        href = html.unescape(href_match.group(1).strip())
        img_tag = img_match.group(0)

        alt_match = re.search(r"alt=[\"']([^\"']*)[\"']", img_tag, flags=re.IGNORECASE)
        src_match = re.search(r"src=[\"']([^\"']+)[\"']", img_tag, flags=re.IGNORECASE)

        name = html.unescape(alt_match.group(1).strip()) if alt_match else ""
        image_url = html.unescape(src_match.group(1).strip()) if src_match else ""

        if href and not href.startswith("http"):
            href = urljoin(DETAIL_BASE, href)
        if image_url and not image_url.startswith("http"):
            image_url = urljoin(DETAIL_BASE, image_url)

        # カード詳細ページ以外（外部リンク・ナビリンク）を除外
        if "/card-search/details.php" not in href:
            continue
        if "pokemon-card.com" not in href:
            continue

        cards.append({
            "name": name,
            "url": href,
            "image_url": image_url,
        })

    return cards


def _detect_total_pages(page_html: str) -> int | None:
    """「130ページ中 1ページ目」形式から総ページ数を抽出する。"""
    m = re.search(r"(\d+)\s*ページ中\s*\d+\s*ページ目", page_html)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    return None


def _collect_card_urls_via_http(limit: int | None = None) -> list[dict]:
    """HTTPリクエストで一覧ページを巡回してカードURLを収集する。"""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": "https://www.pokemon-card.com/",
    }

    cards = []
    seen_urls: set[str] = set()

    page = 1
    total_pages = None

    while True:
        url = f"{STANDARD_SEARCH_URL}&page={page}"
        print(f"\n[Phase 1][HTTP] ページ {page} 取得中: {url}")

        resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT_SEC)
        resp.raise_for_status()
        page_html = resp.text

        if total_pages is None:
            total_pages = _detect_total_pages(page_html)
            if total_pages:
                print(f"  総ページ数: {total_pages}")

        page_cards = _extract_cards_from_html(page_html)
        print(f"  → {len(page_cards)} 件抽出")

        if not page_cards:
            # 1ページ目で0件なら即終了、それ以外は末尾到達扱い
            if page == 1:
                print("  [WARN] 1ページ目で0件。HTTP抽出失敗の可能性があります。")
            break

        new_count = 0
        for c in page_cards:
            href = c.get("url") or ""
            if not href or href in seen_urls:
                continue
            seen_urls.add(href)
            cards.append(c)
            new_count += 1

            if limit and len(cards) >= limit:
                print(f"  上限 {limit} 件に達しました。")
                return cards

        print(f"  新規追加: {new_count} 件 / 累計: {len(cards)} 件")

        if total_pages and page >= total_pages:
            break

        # next リンクがなければ終了（ページャーの a.next のみに限定）
        has_next = bool(re.search(r"<a[^>]*class=[\"'][^\"']*next[^\"']*[\"'][^>]*>", page_html, flags=re.IGNORECASE))
        if not has_next and not total_pages:
            break

        page += 1
        time.sleep(0.4)

    return cards


def collect_card_urls(driver, limit: int | None = None) -> list[dict]:
    """
    スタンダード条件でページネーションを巡回し、全カードの URL / 画像URL を収集する。
    Returns: [{"name": str, "url": str, "image_url": str}, ...]
    """
    from selenium.webdriver.common.by import By

    # まずHTTP取得を試みる（高速・安定）
    try:
        cards = _collect_card_urls_via_http(limit=limit)
        if cards:
            print(f"\n[Phase 1] HTTP取得成功: {len(cards)} 件")
            return cards
        print("\n[Phase 1] HTTP取得が0件のため Selenium にフォールバック")
    except Exception as e:
        print(f"\n[Phase 1] HTTP取得失敗（Seleniumへフォールバック）: {e}")

    cards = []
    seen_urls: set[str] = set()

    print(f"\n[Phase 1] 一覧を取得中: {STANDARD_SEARCH_URL}")
    driver.get(STANDARD_SEARCH_URL)
    time.sleep(3)

    _ensure_standard_condition(driver)

    page = 1
    while True:
        print(f"\n[Phase 1] ページ {page} を解析中")

        # カードリスト読み込み待機
        time.sleep(2)
        # スクロールして遅延読み込みを促す
        for _ in range(2):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)

        # カード要素 (li.List_item) を取得
        items = driver.find_elements(By.CSS_SELECTOR, "li.List_item")
        print(f"  → {len(items)} 件取得")

        if not items:
            # 他のセレクタを試行
            items = driver.find_elements(By.CSS_SELECTOR, "ul.card-list li, section.card-list-section li")
            print(f"  → フォールバックセレクタで {len(items)} 件取得")

        if not items:
            print("  カードが見つかりません。収集終了。")
            _dump_page_source(driver, f"standard_page{page}_debug.html")
            break

        new_count = 0
        for item in items:
            try:
                link = item.find_element(By.TAG_NAME, "a")
                href = link.get_attribute("href") or ""
                if not href or href in seen_urls:
                    continue
                if not href.startswith("http"):
                    href = DETAIL_BASE + href
                if "/card-search/details.php" not in href:
                    continue
                if "pokemon-card.com" not in href:
                    continue

                img_el = item.find_element(By.TAG_NAME, "img")
                name = img_el.get_attribute("alt") or img_el.get_attribute("title") or ""
                image_url = img_el.get_attribute("src") or ""

                seen_urls.add(href)
                cards.append({"name": name.strip(), "url": href, "image_url": image_url})
                new_count += 1

                if limit and len(cards) >= limit:
                    print(f"  上限 {limit} 件に達しました。")
                    return cards
            except Exception:
                continue

        print(f"  新規追加: {new_count} 件 / 累計: {len(cards)} 件")

        # 次ページへ遷移
        try:
            next_btn = driver.find_element(By.CSS_SELECTOR, "a.next")
            if not next_btn.is_displayed():
                print("  「次のページ」ボタンなし → 収集完了")
                break
            next_href = next_btn.get_attribute("href")
            if not next_href:
                print("  次ページURLなし → 収集完了")
                break
            driver.get(next_href)
            time.sleep(2)
        except Exception:
            print("  「次のページ」ボタンなし → 収集完了")
            break

        page += 1
        time.sleep(1)

    print(f"\n  合計 {len(cards)} 件のカードURLを収集（スタンダード条件）")
    return cards


# ──────────────────────────────────────────────
# Phase 2: カード詳細スクレイピング
# ──────────────────────────────────────────────

TYPE_MAP = {
    "icon-grass": "草", "Grass": "草",
    "icon-fire": "炎", "Fire": "炎",
    "icon-water": "水", "Water": "水",
    "icon-lightning": "雷", "Lightning": "雷",
    "icon-psychic": "超", "Psychic": "超",
    "icon-fighting": "闘", "Fighting": "闘",
    "icon-darkness": "悪", "Darkness": "悪",
    "icon-metal": "鋼", "Metal": "鋼",
    "icon-dragon": "ドラゴン", "Dragon": "ドラゴン",
    "icon-fairy": "フェアリー", "Fairy": "フェアリー",
    "icon-colorless": "無色", "Colorless": "無色",
    "icon-none": "無色",
}

EVOLUTION_MAP = {
    "たねポケモン": "たね",
    "1進化": "1進化",
    "2進化": "2進化",
    "VMAX": "VMAX",
    "VSTAR": "VSTAR",
    "V": "V",
    "ex": "ex",
    "GX": "GX",
    "EX": "EX",
}


def _class_to_type(class_str: str) -> str | None:
    for key, val in TYPE_MAP.items():
        if key in class_str:
            return val
    return None


def _extract_regulation_mark(driver) -> str | None:
    """詳細ページからレギュレーションマーク（例: H/I/J）を抽出する。"""
    from selenium.webdriver.common.by import By

    # テキストからの抽出
    text_selectors = [
        ".regulation", ".regulation-mark", ".mark", "p[class*='regulation']", "span[class*='regulation']",
    ]
    for sel in text_selectors:
        try:
            text = driver.find_element(By.CSS_SELECTOR, sel).text.strip()
            m = re.search(r"\b([A-Z])\b", text)
            if m:
                return m.group(1)
        except Exception:
            pass

    # 画像 alt / class からの抽出
    try:
        imgs = driver.find_elements(By.CSS_SELECTOR, "img")
        for img in imgs:
            alt = (img.get_attribute("alt") or "")
            cls = (img.get_attribute("class") or "")
            src = (img.get_attribute("src") or "")
            for target in (alt, cls, src):
                m = re.search(r"(?:regulation|レギュレーション)[^A-Z]*([A-Z])", target, flags=re.IGNORECASE)
                if m:
                    return m.group(1).upper()
    except Exception:
        pass

    # HTML全体からの抽出（最後のフォールバック）
    page_text = driver.page_source[:50000]
    m = re.search(r"レギュレーション[^A-Z]{0,20}([A-Z])", page_text)
    if m:
        return m.group(1)

    return None


def scrape_card_detail(driver, card_url: str) -> dict | None:
    """
    カード詳細ページをスクレイピングして辞書を返す。
    """
    from selenium.webdriver.common.by import By

    driver.get(card_url)
    time.sleep(WAIT_SEC)

    data: dict = {"url": card_url}
    data["regulation_mark"] = _extract_regulation_mark(driver)

    # ── カード名 ──
    name_selectors = [
        "h1.Heading1", "h1.card_name span", "h1.card_name",
        "h1[class*='name']", "h1",
    ]
    for sel in name_selectors:
        try:
            el = driver.find_element(By.CSS_SELECTOR, sel)
            text = el.text.strip()
            if text:
                data["name"] = text
                break
        except Exception:
            pass

    if not data.get("name"):
        # titleタグから取得を試みる
        title = driver.title
        if title:
            data["name"] = title.split("|")[0].strip()

    # ── カードカテゴリ（pokemon / trainer / energy） ──
    category_text = ""
    cat_selectors = [
        ".type-name", ".card-category", ".cardCategory",
        "//h2[contains(@class,'Heading2')]",
        "//p[contains(@class,'type')]",
    ]
    # 画像URLのパスからカテゴリを推測
    page_text = driver.page_source[:5000]
    if "ポケモン" in page_text[:2000]:
        category_text = "pokemon"
    elif "トレーナーズ" in page_text[:2000] or "グッズ" in page_text[:2000] or "サポート" in page_text[:2000]:
        category_text = "trainer"
    elif "基本エネルギー" in page_text[:2000] or "特殊エネルギー" in page_text[:2000]:
        category_text = "energy"
    else:
        category_text = "pokemon"  # デフォルト
    data["card_type"] = category_text

    # ── HP ──
    hp_selectors = [".hp-num", ".HP", "span[class*='hp']", "//span[contains(text(),'HP')]"]
    for sel in hp_selectors:
        try:
            if sel.startswith("//"):
                el = driver.find_element(By.XPATH, sel)
            else:
                el = driver.find_element(By.CSS_SELECTOR, sel)
            hp_text = re.sub(r"[^\d]", "", el.text)
            if hp_text:
                data["hp"] = int(hp_text)
                break
        except Exception:
            pass

    # HP が取れなければページ全体から正規表現で探す
    if not data.get("hp"):
        m = re.search(r"HP\s*(\d+)", driver.page_source[:3000])
        if m:
            data["hp"] = int(m.group(1))

    # ── タイプ ──
    type_selectors = [
        ".hp-type + .icon", ".type-icon", ".pokemon-type img",
        "//div[contains(@class,'type')]//img",
    ]
    for sel in type_selectors:
        try:
            if sel.startswith("//"):
                el = driver.find_element(By.XPATH, sel)
                cls = el.get_attribute("class") or ""
                alt = el.get_attribute("alt") or ""
            else:
                el = driver.find_element(By.CSS_SELECTOR, sel)
                cls = el.get_attribute("class") or ""
                alt = el.get_attribute("alt") or ""
            t = _class_to_type(cls) or _class_to_type(alt)
            if t:
                data["type"] = t
                break
        except Exception:
            pass

    # ── 進化段階 ──
    evo_selectors = [".evolution-stage", ".category", ".type", "//p[contains(@class,'regulation')]"]
    for sel in evo_selectors:
        try:
            if sel.startswith("//"):
                el = driver.find_element(By.XPATH, sel)
            else:
                el = driver.find_element(By.CSS_SELECTOR, sel)
            text = el.text.strip()
            for k, v in EVOLUTION_MAP.items():
                if k in text:
                    data["evolution_stage"] = v
                    break
            if data.get("evolution_stage"):
                break
        except Exception:
            pass

    # ── ワザ ──
    attacks = _scrape_attacks(driver)
    data["attacks"] = attacks

    # ── 特性（とくせい） ──
    ability = _scrape_ability(driver)
    if ability:
        data["ability"] = ability

    # ── 弱点・抵抗力・逃げるコスト（テーブル形式） ──
    _scrape_battle_info(driver, data)

    # ── 画像URL（og:imageまたはcard img） ──
    if not data.get("image_url"):
        try:
            og = driver.find_element(By.CSS_SELECTOR, "meta[property='og:image']")
            data["image_url"] = og.get_attribute("content") or ""
        except Exception:
            pass
        if not data.get("image_url"):
            try:
                img = driver.find_element(By.CSS_SELECTOR, ".card-img img, .cardImage img, .card_img img")
                data["image_url"] = img.get_attribute("src") or ""
            except Exception:
                pass

    return data


def _scrape_attacks(driver) -> list[dict]:
    from selenium.webdriver.common.by import By

    attacks = []

    # ワザブロックを複数セレクタで試行
    block_selectors = [
        "section.skills-wrap .skill",
        ".skills .skill",
        "div.skill",
        ".waza-block",
        "table.skills tr",
    ]

    blocks = []
    for sel in block_selectors:
        blocks = driver.find_elements(By.CSS_SELECTOR, sel)
        if blocks:
            break

    for block in blocks:
        atk: dict = {}

        # ワザ名
        for sel in [".skill-name", "h4.skill-name", "h4", ".name", "td.name"]:
            try:
                el = block.find_element(By.CSS_SELECTOR, sel)
                atk["name"] = el.text.strip()
                break
            except Exception:
                pass
        if not atk.get("name"):
            continue

        # ダメージ
        for sel in [".skill-damage", ".damage", "td.damage", ".point"]:
            try:
                el = block.find_element(By.CSS_SELECTOR, sel)
                dmg = re.sub(r"[^\d]", "", el.text)
                atk["damage"] = int(dmg) if dmg else 0
                break
            except Exception:
                pass
        if "damage" not in atk:
            atk["damage"] = 0

        # エネルギーコスト（アイコンのクラスから取得）
        energies = []
        for sel in [".skill-cost .icon", ".cost .icon", ".energy-icon", "td.cost img"]:
            try:
                icons = block.find_elements(By.CSS_SELECTOR, sel)
                for icon in icons:
                    cls = icon.get_attribute("class") or ""
                    alt = icon.get_attribute("alt") or ""
                    t = _class_to_type(cls) or _class_to_type(alt)
                    if t:
                        energies.append(t)
                if energies:
                    break
            except Exception:
                pass
        atk["energy"] = energies
        atk["energy_count"] = len(energies)

        # 効果テキスト
        for sel in [".skill-description", ".description", ".text", "td.text", "p"]:
            try:
                el = block.find_element(By.CSS_SELECTOR, sel)
                atk["description"] = el.text.strip()
                break
            except Exception:
                pass
        if "description" not in atk:
            atk["description"] = ""

        attacks.append(atk)

    return attacks


def _scrape_ability(driver) -> dict | None:
    from selenium.webdriver.common.by import By

    ability_selectors = [
        ".ability-block", ".tokusei-block", "section.ability",
        "div.ability",
    ]
    for sel in ability_selectors:
        try:
            block = driver.find_element(By.CSS_SELECTOR, sel)
            name = ""
            desc = ""
            for ns in [".ability-name", "h4", ".name"]:
                try:
                    name = block.find_element(By.CSS_SELECTOR, ns).text.strip()
                    break
                except Exception:
                    pass
            for ds in [".ability-text", ".description", "p"]:
                try:
                    desc = block.find_element(By.CSS_SELECTOR, ds).text.strip()
                    break
                except Exception:
                    pass
            if name:
                return {"name": name, "description": desc}
        except Exception:
            pass
    return None


def _scrape_battle_info(driver, data: dict):
    from selenium.webdriver.common.by import By

    # ── 弱点 ──
    for sel in [".weakness .icon", ".weakness-icon", "//td[@class='weak']//img"]:
        try:
            if sel.startswith("//"):
                el = driver.find_element(By.XPATH, sel)
            else:
                el = driver.find_element(By.CSS_SELECTOR, sel)
            cls = el.get_attribute("class") or ""
            alt = el.get_attribute("alt") or ""
            t = _class_to_type(cls) or _class_to_type(alt)
            if t:
                data["weakness_type"] = t
                data["weakness_value"] = "×2"  # デフォルト
                break
        except Exception:
            pass

    # 弱点倍率テキスト
    for sel in [".weakness .value", ".weakness-value"]:
        try:
            v = driver.find_element(By.CSS_SELECTOR, sel).text.strip()
            if v:
                data["weakness_value"] = v
            break
        except Exception:
            pass

    # ── 抵抗力 ──
    for sel in [".resistance .icon", ".resistance-icon"]:
        try:
            el = driver.find_element(By.CSS_SELECTOR, sel)
            cls = el.get_attribute("class") or ""
            alt = el.get_attribute("alt") or ""
            t = _class_to_type(cls) or _class_to_type(alt)
            if t:
                data["resistance_type"] = t
                data["resistance_value"] = "-30"  # デフォルト
                break
        except Exception:
            pass

    for sel in [".resistance .value", ".resistance-value"]:
        try:
            v = driver.find_element(By.CSS_SELECTOR, sel).text.strip()
            if v:
                data["resistance_value"] = v
            break
        except Exception:
            pass

    # ── 逃げるコスト ──
    for sel in [".escape .icon", ".retreat .icon", ".retreat-cost .icon"]:
        try:
            icons = driver.find_elements(By.CSS_SELECTOR, sel)
            data["retreat_cost"] = len(icons)
            break
        except Exception:
            pass
    if "retreat_cost" not in data:
        data["retreat_cost"] = 0


# ──────────────────────────────────────────────
# ユーティリティ
# ──────────────────────────────────────────────

def _dump_page_source(driver, filename: str):
    path = os.path.join(RAW_DIR, filename)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    print(f"  [DEBUG] HTMLを保存: {path}")


def load_existing(output_path: str) -> dict:
    if os.path.exists(output_path):
        with open(output_path, encoding="utf-8") as f:
            data = json.load(f)
        return {item["url"]: item for item in data}
    return {}


def save_results(results: list[dict], output_path: str):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)


def _is_valid_card_url_list(card_urls: list[dict]) -> bool:
    if not card_urls:
        return False
    valid = 0
    for item in card_urls:
        href = str(item.get("url", ""))
        if "pokemon-card.com" in href and "/card-search/details.php" in href:
            valid += 1
    # 少なくとも1件は詳細URLであること
    return valid > 0


# ──────────────────────────────────────────────
# メイン
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="スタンダード(H/I/J)カード全件スクレイピング")
    parser.add_argument("--marks", default="H,I,J", help="対象レギュレーションマーク（カンマ区切り）例: H,I,J")
    parser.add_argument("--limit", type=int, default=None, help="最大取得カード数（省略時=全件）")
    parser.add_argument("--no-headless", action="store_true", help="ブラウザを表示して実行")
    parser.add_argument("--list-only", action="store_true", help="URL収集のみ（詳細スクレイピングなし）")
    parser.add_argument("--resume", action="store_true", help="中断した場合に再開（デフォルト有効）")
    parser.add_argument("--include-unknown-mark", action="store_true", help="マーク抽出不可カードも保存する")
    args = parser.parse_args()

    target_marks = {m.strip().upper() for m in args.marks.split(",") if m.strip()}
    if not target_marks:
        target_marks = set(DEFAULT_TARGET_MARKS)

    headless = not args.no_headless
    marks_label = "".join(sorted(target_marks))
    output_path = os.path.join(RAW_DIR, f"standard_{marks_label}_cards.json")
    url_list_path = os.path.join(RAW_DIR, f"standard_{marks_label}_urls.json")

    print("=" * 60)
    print(f"🎴 ポケモンカード スタンダード全件スクレイピング（対象: {','.join(sorted(target_marks))}）")
    print("=" * 60)
    print(f"  出力先: {output_path}")
    if args.limit:
        print(f"  上限: {args.limit}件")

    driver = get_driver(headless)

    try:
        # ── Phase 1: URL収集 ──
        # URLリストが既に存在する場合は再利用（ただし0件は再収集）
        if os.path.exists(url_list_path):
            with open(url_list_path, encoding="utf-8") as f:
                card_urls = json.load(f)
            if _is_valid_card_url_list(card_urls):
                print(f"\n[Phase 1] 既存URLリスト再利用: {len(card_urls)}件")
            else:
                print("\n[Phase 1] 既存URLリストが不正または空 → 再収集")
                card_urls = collect_card_urls(driver, limit=args.limit)
                save_results(card_urls, url_list_path)
        else:
            card_urls = collect_card_urls(driver, limit=args.limit)
            save_results(card_urls, url_list_path)
            print(f"  URLリストを保存: {url_list_path}")

        if args.list_only:
            print(f"\n✅ URLリスト収集完了: {len(card_urls)}件")
            return

        if args.limit:
            card_urls = card_urls[: args.limit]

        # ── Phase 2: 詳細スクレイピング（リジューム対応） ──
        existing = load_existing(output_path)
        results = list(existing.values())
        already_urls = set(existing.keys())
        skip_count = len(already_urls)
        if skip_count:
            print(f"\n[Phase 2] スキップ済み: {skip_count}件 / {len(card_urls)}件")

        total = len(card_urls)
        for i, card_info in enumerate(card_urls, 1):
            card_url = card_info["url"]

            if card_url in already_urls:
                print(f"  [{i}/{total}] スキップ: {card_info.get('name', card_url)}")
                continue

            print(f"\n  [{i}/{total}] スクレイピング: {card_info.get('name', card_url)}")
            print(f"    URL: {card_url}")

            try:
                detail = scrape_card_detail(driver, card_url)
                if detail:
                    # URLリストの name/image_url で補完
                    if not detail.get("name") and card_info.get("name"):
                        detail["name"] = card_info["name"]
                    if not detail.get("image_url") and card_info.get("image_url"):
                        detail["image_url"] = card_info["image_url"]

                    mark = (detail.get("regulation_mark") or "").upper()
                    if mark and mark not in target_marks:
                        print(f"    → スキップ（対象外マーク: {mark}）")
                        continue
                    if not mark and not args.include_unknown_mark:
                        print("    → スキップ（マーク抽出不可）")
                        continue

                    results.append(detail)
                    already_urls.add(card_url)

                    print(f"    → {detail.get('name', '?')} "
                          f"マーク:{detail.get('regulation_mark', '-')} "
                          f"HP:{detail.get('hp', '-')} "
                          f"タイプ:{detail.get('type', '-')} "
                          f"ワザ:{len(detail.get('attacks', []))}個")
                else:
                    print(f"    [WARN] 詳細取得失敗: {card_url}")

            except Exception as e:
                print(f"    [ERROR] {e}")

            # 10件ごとに中間保存
            if i % 10 == 0:
                save_results(results, output_path)
                print(f"  💾 中間保存: {len(results)}件")

            time.sleep(WAIT_SEC)

        # 最終保存
        save_results(results, output_path)

        print("\n" + "=" * 60)
        print(f"✅ スクレイピング完了: {len(results)}件")
        print(f"   保存先: {output_path}")
        print("=" * 60)

    except KeyboardInterrupt:
        print("\n\n⚠️  中断されました。途中まで保存済みです。")
        print("   再開するには同じコマンドを実行してください。")
    except Exception as e:
        import traceback
        print(f"\n❌ エラー: {e}")
        traceback.print_exc()
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
