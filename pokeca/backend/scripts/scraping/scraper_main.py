"""
ポケモンカードスクレイパー
スクレイピング実行コマンド
python3 scripts/scraping/scraper_main.py

スクレイピング後、以下を実行
python3 scripts/import_regulation_cards.py \
  --file backend/data/scraped/raw/pokemon_cards.json

"""

from __future__ import annotations

import json
import os
import re
import time
import traceback
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.remote.webelement import WebElement
from webdriver_manager.chrome import ChromeDriverManager


# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

BASE_URL = "https://www.pokemon-card.com"
CARD_SEARCH_URL = f"{BASE_URL}/card-search/"
DEBUG_DIR = Path("backend/data/scraped/raw")

TYPE_MAP: dict[str, str] = {
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
    "icon-colorless": "無色",
}


# ---------------------------------------------------------------------------
# データクラス
# ---------------------------------------------------------------------------

@dataclass
class Attack:
    name: str
    energy: list[str]
    energy_count: int
    damage: int
    description: str


@dataclass
class Resistance:
    type: Optional[str]
    value: str


@dataclass
class CardDetail:
    name: str = "不明"
    hp: Optional[int] = None
    type: str = "不明"
    evolution_stage: str = "不明"
    attacks: list[Attack] = field(default_factory=list)
    weakness: Optional[str] = None
    resistance: Optional[Resistance] = None
    retreat_cost: int = 0


@dataclass
class CardInfo:
    name: str
    image_url: Optional[str]
    list_index: int


# ---------------------------------------------------------------------------
# ユーティリティ
# ---------------------------------------------------------------------------

def resolve_icon_type(element: WebElement) -> Optional[str]:
    """アイコン要素からタイプ名を返す。"""
    icon_class = element.get_attribute("class") or ""
    for key, value in TYPE_MAP.items():
        if key in icon_class:
            return value
    return None


def resolve_icons_type(cell: WebElement) -> Optional[str]:
    """セル内の最初のアイコン要素からタイプ名を返す。"""
    icons = cell.find_elements(By.CSS_SELECTOR, ".icon")
    if icons:
        return resolve_icon_type(icons[0])
    return None


def build_image_url(src: Optional[str]) -> Optional[str]:
    if not src:
        return None
    return src if src.startswith("http") else f"{BASE_URL}{src}"


# ---------------------------------------------------------------------------
# ドライバファクトリ
# ---------------------------------------------------------------------------

def build_driver(headless: bool = True) -> webdriver.Chrome:
    options = Options()
    if headless:
        options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)


# ---------------------------------------------------------------------------
# スクレイパー本体
# ---------------------------------------------------------------------------

class PokemonCardScraper:
    def __init__(self, headless: bool = True) -> None:
        print("🔧 Selenium を初期化中...")
        self.driver = build_driver(headless)
        print("✅ 初期化完了！")

    # ------------------------------------------------------------------
    # カード一覧
    # ------------------------------------------------------------------

    def fetch_card_list(
        self,
        keyword: str = "",
        start_index: int = 0,
        end_index: Optional[int] = None,
    ) -> list[CardInfo]:
        """カード一覧ページからカード情報を取得する。"""
        url = CARD_SEARCH_URL + (f"?keyword={keyword}" if keyword else "")
        print(f"\n🔍 カード検索中: {url}")
        self.driver.get(url)
        self._wait_and_scroll()

        items = self.driver.find_elements(By.CSS_SELECTOR, "li.List_item")
        print(f"📊 {len(items)} 個の要素を発見")

        cards: list[CardInfo] = []
        for idx, item in enumerate(items):
            try:
                img = item.find_element(By.TAG_NAME, "img")
                name = img.get_attribute("alt")
                if name:
                    cards.append(CardInfo(
                        name=name,
                        image_url=build_image_url(img.get_attribute("src")),
                        list_index=idx,
                    ))
                    print(f"  ✅ [{idx + 1}] {name}")
            except Exception:
                continue

        cards = self._slice_cards(cards, start_index, end_index)
        print(f"\n📊 対象カード: {len(cards)} 枚")
        return cards

    @staticmethod
    def _slice_cards(
        cards: list[CardInfo],
        start: int,
        end: Optional[int],
    ) -> list[CardInfo]:
        if start > 0 or end is not None:
            sliced = cards[start:end]
            print(f"⚡ {start + 1} 枚目〜{(end or len(cards))} 枚目を対象にします（{len(sliced)} 枚）")
            return sliced
        return cards

    # ------------------------------------------------------------------
    # カード詳細
    # ------------------------------------------------------------------

    def fetch_card_detail(self, card: CardInfo, list_url: str) -> Optional[CardDetail]:
        """カード詳細ページから情報を取得する。"""
        print(f"\n{'=' * 60}")
        print(f"📄 詳細取得: {card.name}")
        print(f"{'=' * 60}")

        try:
            self.driver.get(list_url)
            self._wait_and_scroll(sleep_after_load=3, scroll_times=3, scroll_sleep=1)

            original_window = self.driver.current_window_handle
            self._click_card(card.list_index)
            new_window = self._wait_for_new_window(original_window)

            if new_window is None:
                print("  ❌ 新しいウィンドウが見つかりませんでした")
                return None

            self.driver.switch_to.window(new_window)
            time.sleep(3)
            print(f"  🌐 現在の URL: {self.driver.current_url}")

            self._save_debug_files(card.list_index)
            detail = self._extract_detail()

            self.driver.close()
            self.driver.switch_to.window(original_window)
            return detail

        except Exception as e:
            print(f"  ❌ エラー: {e}")
            traceback.print_exc()
            self._recover_windows()
            return None

    def _click_card(self, list_index: int) -> None:
        items = self.driver.find_elements(By.CSS_SELECTOR, "li.List_item")
        link = items[list_index].find_element(By.TAG_NAME, "a")
        print("  👆 カードをクリック...")
        link.click()

    def _wait_for_new_window(self, original: str, timeout: int = 3) -> Optional[str]:
        print(f"  ⏳ 新しいウィンドウを待機（{timeout} 秒）...")
        time.sleep(timeout)
        handles = self.driver.window_handles
        print(f"  📊 ウィンドウ数: {len(handles)}")
        for handle in handles:
            if handle != original:
                print(f"  ✅ 新しいウィンドウを検出: {handle}")
                return handle
        return None

    def _recover_windows(self) -> None:
        try:
            handles = self.driver.window_handles
            if len(handles) > 1:
                self.driver.switch_to.window(handles[-1])
                self.driver.close()
                self.driver.switch_to.window(handles[0])
        except Exception:
            pass

    # ------------------------------------------------------------------
    # 詳細ページのパース
    # ------------------------------------------------------------------

    def _extract_detail(self) -> CardDetail:
        detail = CardDetail()
        print("  🔍 詳細情報を抽出中...")

        detail.name = self._extract_name()
        detail.hp = self._extract_hp()
        detail.type = self._extract_type()
        detail.evolution_stage = self._extract_evolution_stage()
        detail.attacks = self._extract_attacks()
        self._extract_table_info(detail)

        return detail

    def _extract_name(self) -> str:
        try:
            name = self.driver.find_element(By.CSS_SELECTOR, "h1.Heading1").text.strip()
            print(f"    📛 カード名: {name}")
            return name
        except Exception:
            return "不明"

    def _extract_hp(self) -> Optional[int]:
        try:
            hp = int(self.driver.find_element(By.CSS_SELECTOR, ".hp-num").text.strip())
            print(f"    ❤️ HP: {hp}")
            return hp
        except Exception:
            return None

    def _extract_type(self) -> str:
        try:
            icon = self.driver.find_element(By.CSS_SELECTOR, ".hp-type + .icon")
            pokemon_type = resolve_icon_type(icon) or "不明"
            print(f"    ⚡ タイプ: {pokemon_type}")
            return pokemon_type
        except Exception as e:
            print(f"    ⚠️ タイプ取得失敗: {e}")
            return "不明"

    def _extract_evolution_stage(self) -> str:
        try:
            stage = self.driver.find_element(By.CSS_SELECTOR, ".type").text.strip()
            print(f"    🌱 進化段階: {stage}")
            return stage
        except Exception:
            return "不明"

    def _extract_attacks(self) -> list[Attack]:
        attacks: list[Attack] = []
        try:
            waza_section = self.driver.find_element(
                By.XPATH, "//h2[contains(text(), 'ワザ')]"
            )
            parent = waza_section.find_element(By.XPATH, "..")
            headers = parent.find_elements(By.TAG_NAME, "h4")
            descriptions = parent.find_elements(
                By.XPATH, ".//h4/following-sibling::p[1]"
            )

            for i, h4 in enumerate(headers):
                attack = self._parse_attack(h4, descriptions[i] if i < len(descriptions) else None)
                if attack:
                    attacks.append(attack)

        except Exception as e:
            print(f"    ⚠️ ワザセクション取得失敗: {e}")

        return attacks

    def _parse_attack(
        self, h4: WebElement, desc_elem: Optional[WebElement]
    ) -> Optional[Attack]:
        try:
            energies = [
                resolve_icon_type(icon)
                for icon in h4.find_elements(By.CSS_SELECTOR, ".icon")
                if resolve_icon_type(icon)
            ]

            h4_text = h4.text.strip()
            damage_match = re.search(r"(\d+)$", h4_text)
            damage = int(damage_match.group(1)) if damage_match else 0
            name = re.sub(r"\d+$", "", h4_text).strip()
            description = desc_elem.text.strip() if desc_elem else ""

            print(
                f"    ⚔️ ワザ: {name} ({'/'.join(energies)} × {len(energies)}) ダメージ{damage}"
            )
            return Attack(
                name=name,
                energy=energies,
                energy_count=len(energies),
                damage=damage,
                description=description,
            )
        except Exception as e:
            print(f"    ⚠️ ワザ解析エラー: {e}")
            return None

    def _extract_table_info(self, detail: CardDetail) -> None:
        try:
            table = self.driver.find_element(By.CSS_SELECTOR, "table")
            rows = table.find_elements(By.TAG_NAME, "tr")
            if len(rows) < 2:
                return

            cells = rows[1].find_elements(By.TAG_NAME, "td")

            # 弱点
            if len(cells) > 0:
                detail.weakness = self._parse_weakness(cells[0])

            # 抵抗力
            if len(cells) > 1:
                detail.resistance = self._parse_resistance(cells[1])

            # 逃げるエネルギー
            if len(cells) > 2:
                detail.retreat_cost = len(cells[2].find_elements(By.CSS_SELECTOR, ".icon"))
                print(f"    🏃 逃げエネ: {detail.retreat_cost}")

        except Exception as e:
            print(f"    ⚠️ テーブル情報取得失敗: {e}")

    def _parse_weakness(self, cell: WebElement) -> Optional[str]:
        text = cell.text.strip()
        if not text or text == "--":
            return None
        weakness = resolve_icons_type(cell)
        print(f"    ⚠️ 弱点: {weakness}")
        return weakness

    def _parse_resistance(self, cell: WebElement) -> Optional[Resistance]:
        text = cell.text.strip()
        if not text or text == "--":
            return None
        res_type = resolve_icons_type(cell)
        reduction_match = re.search(r"-(\d+)", text)
        value = f"-{reduction_match.group(1)}" if reduction_match else "-20"
        print(f"    🛡️ 抵抗力: {res_type} {value}")
        return Resistance(type=res_type, value=value)

    # ------------------------------------------------------------------
    # ヘルパー
    # ------------------------------------------------------------------

    def _wait_and_scroll(
        self,
        sleep_after_load: int = 3,
        scroll_times: int = 3,
        scroll_sleep: int = 2,
    ) -> None:
        time.sleep(sleep_after_load)
        for _ in range(scroll_times):
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(scroll_sleep)

    def _save_debug_files(self, index: int) -> None:
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        html_path = DEBUG_DIR / f"detail_{index}.html"
        png_path = DEBUG_DIR / f"detail_{index}.png"
        html_path.write_text(self.driver.page_source, encoding="utf-8")
        self.driver.save_screenshot(str(png_path))

    # ------------------------------------------------------------------
    # 保存・終了
    # ------------------------------------------------------------------

    def save_json(self, data: list[dict], path: str | Path) -> None:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"💾 保存完了: {out}")

    def close(self) -> None:
        print("\n🔚 ブラウザを終了しています...")
        self.driver.quit()
        print("✅ 完了")


# ---------------------------------------------------------------------------
# エントリーポイント
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 60)
    print("🎴 ポケモンカードスクレイパー")
    print("=" * 60)

    # ===== スクレイピング範囲の設定 =====
    START_INDEX = 19   # 開始位置（1 始まり）
    END_INDEX   = 20   # 終了位置（exclusive）。末尾まで取得する場合は None
    OUTPUT_PATH = DEBUG_DIR / "pokemon_cards.json"
    # ======================================

    scraper = PokemonCardScraper(headless=True)
    try:
        cards = scraper.fetch_card_list(
            # keyword="ピカチュウ",
            start_index=START_INDEX ,
            end_index=END_INDEX ,
        )

        if not cards:
            print("\n❌ カードが取得できませんでした")
            return

        detailed_cards: list[dict] = []
        for i, card in enumerate(cards, 1):
            print(f"\n[{i}/{len(cards)}] 処理中...")
            detail = scraper.fetch_card_detail(card, CARD_SEARCH_URL)
            if detail:
                merged = {**asdict(card), **asdict(detail)}
                detailed_cards.append(merged)
            time.sleep(2)

        scraper.save_json(detailed_cards, OUTPUT_PATH)

        print("\n" + "=" * 60)
        print("✅ すべての処理が完了しました！")
        print("=" * 60)
        print(f"\n📊 取得カード数: {len(detailed_cards)} 枚")
        print(f"💾 保存先: {OUTPUT_PATH}")
        print(f"📁 デバッグファイル: {DEBUG_DIR}/detail_*.html / *.png")

    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        traceback.print_exc()
    finally:
        scraper.close()


if __name__ == "__main__":
    main()