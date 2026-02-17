"""
ポケモンカードデータベースのセットアップスクリプト
JSONファイルからSQLiteデータベースを作成
"""
import sqlite3
import json
import os
from pathlib import Path


def create_database(db_path: str = "data/pokemon_cards.db"):
    """
    データベースを作成してテーブルを初期化
    """
    # データベースディレクトリを作成
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 既存のテーブルを削除（再作成用）
    cursor.execute('DROP TABLE IF EXISTS cards')
    
    # カードテーブルを作成
    cursor.execute('''
        CREATE TABLE cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            image_url TEXT,
            list_index INTEGER,
            hp INTEGER,
            type TEXT,
            evolution_stage TEXT,
            weakness_type TEXT,
            weakness_value TEXT,
            resistance_type TEXT,
            resistance_value TEXT,
            retreat_cost INTEGER,
            attacks TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # インデックスを作成（検索高速化）
    cursor.execute('CREATE INDEX idx_name ON cards(name)')
    cursor.execute('CREATE INDEX idx_type ON cards(type)')
    cursor.execute('CREATE INDEX idx_evolution_stage ON cards(evolution_stage)')
    
    conn.commit()
    conn.close()
    print(f"✅ データベースを作成しました: {db_path}")


def import_json_data(
    json_path: str = "backend/data/scraped/raw/pikachu_fixed.json",
    db_path: str = "backend/data/pokemon_cards.db"
):
    """
    JSONファイルからカードデータをインポート
    """
    # JSONファイルの存在確認
    if not os.path.exists(json_path):
        print(f"⚠️  JSONファイルが見つかりません: {json_path}")
        print("サンプルデータを使用します...")
        import_sample_data(db_path)
        return
    
    # JSONデータを読み込み
    with open(json_path, 'r', encoding='utf-8') as f:
        cards = json.load(f)
    
    if not cards:
        print("⚠️  JSONファイルにデータがありません")
        return
    
    # データベースに接続
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # カードデータを挿入
    imported_count = 0
    for card in cards:
        try:
            cursor.execute('''
                INSERT INTO cards (
                    name, image_url, list_index, hp, type, evolution_stage,
                    weakness_type, weakness_value, 
                    resistance_type, resistance_value,
                    retreat_cost, attacks
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                card.get('name'),
                card.get('image_url'),
                card.get('list_index'),
                card.get('hp'),
                card.get('type'),
                card.get('evolution_stage'),
                card.get('weakness', {}).get('type') if card.get('weakness') else None,
                card.get('weakness', {}).get('value') if card.get('weakness') else None,
                card.get('resistance', {}).get('type') if card.get('resistance') else None,
                card.get('resistance', {}).get('value') if card.get('resistance') else None,
                card.get('retreat_cost'),
                json.dumps(card.get('attacks', []), ensure_ascii=False)
            ))
            imported_count += 1
        except Exception as e:
            print(f"❌ カードのインポートに失敗: {card.get('name', 'Unknown')} - {e}")
    
    conn.commit()
    conn.close()
    print(f"✅ {imported_count}枚のカードをインポートしました")


def import_sample_data(db_path: str = "backend/data/pokemon_cards.db"):
    """
    サンプルデータをインポート
    """
    sample_cards = [
        {
            "name": "アリアドス",
            "image_url": "https://www.pokemon-card.com/assets/images/card_images/large/M3/049635_P_ARIADOSU.jpg",
            "list_index": 0,
            "hp": 110,
            "type": "草",
            "evolution_stage": "1 進化",
            "attacks": [
                {
                    "name": "ポイズンサークル",
                    "energy": ["草"],
                    "energy_count": 1,
                    "damage": 50,
                    "description": "相手のバトルポケモンをどくにする。次の相手の番、このワザを受けたポケモンは、にげられない。"
                }
            ],
            "weakness": {
                "type": "炎",
                "value": "×2"
            },
            "resistance": None,
            "retreat_cost": 1
        },
        {
            "name": "ピカチュウ",
            "image_url": "https://www.pokemon-card.com/assets/images/card_images/large/SV8/042289_P_PIKACHUU.jpg",
            "list_index": 1,
            "hp": 70,
            "type": "雷",
            "evolution_stage": "たね",
            "attacks": [
                {
                    "name": "でんきショック",
                    "energy": ["雷"],
                    "energy_count": 1,
                    "damage": 20,
                    "description": "コインを1回投げオモテなら、相手のバトルポケモンをマヒにする。"
                }
            ],
            "weakness": {
                "type": "闘",
                "value": "×2"
            },
            "resistance": None,
            "retreat_cost": 1
        },
        {
            "name": "リザードン",
            "image_url": "https://www.pokemon-card.com/assets/images/card_images/large/SV8a/042435_P_RIZAADON.jpg",
            "list_index": 2,
            "hp": 180,
            "type": "炎",
            "evolution_stage": "2 進化",
            "attacks": [
                {
                    "name": "かえんほうしゃ",
                    "energy": ["炎", "炎", "無色"],
                    "energy_count": 3,
                    "damage": 120,
                    "description": "このポケモンについているエネルギーを1個選び、トラッシュする。"
                }
            ],
            "weakness": {
                "type": "水",
                "value": "×2"
            },
            "resistance": None,
            "retreat_cost": 2
        }
    ]
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    for card in sample_cards:
        cursor.execute('''
            INSERT INTO cards (
                name, image_url, list_index, hp, type, evolution_stage,
                weakness_type, weakness_value, 
                resistance_type, resistance_value,
                retreat_cost, attacks
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            card['name'],
            card['image_url'],
            card['list_index'],
            card['hp'],
            card['type'],
            card['evolution_stage'],
            card['weakness']['type'] if card['weakness'] else None,
            card['weakness']['value'] if card['weakness'] else None,
            card['resistance']['type'] if card['resistance'] else None,
            card['resistance']['value'] if card['resistance'] else None,
            card['retreat_cost'],
            json.dumps(card['attacks'], ensure_ascii=False)
        ))
    
    conn.commit()
    conn.close()
    print(f"✅ {len(sample_cards)}枚のサンプルカードをインポートしました")


def find_json_files(base_dir: str) -> list:
    """
    指定ディレクトリ以下のJSONファイルを全て検索
    """
    json_files = []
    for path in Path(base_dir).rglob("*.json"):
        json_files.append(str(path))
    return json_files


def import_all_json_files(
    scraped_dir: str,
    db_path: str = "data/pokemon_cards.db"
):
    """
    スクレイピングディレクトリ内の全JSONファイルをインポート
    """
    json_files = find_json_files(scraped_dir)

    if not json_files:
        print(f"⚠️  JSONファイルが見つかりません: {scraped_dir}")
        print("サンプルデータを使用します...")
        import_sample_data(db_path)
        return

    print(f"📁 {len(json_files)}個のJSONファイルを発見:")
    for f in json_files:
        print(f"   - {f}")

    total_imported = 0
    for json_file in json_files:
        print(f"\n📥 インポート中: {json_file}")
        before = get_card_count(db_path)
        import_json_data(json_file, db_path)
        after = get_card_count(db_path)
        total_imported += after - before

    print(f"\n✅ 合計 {total_imported}枚のカードをインポートしました")


def get_card_count(db_path: str) -> int:
    """
    現在のカード総数を取得
    """
    if not os.path.exists(db_path):
        return 0
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM cards')
    count = cursor.fetchone()[0]
    conn.close()
    return count


def main():
    """
    メイン処理
    backendディレクトリ内から実行: python3 -m database.setup
    """
    print("=" * 60)
    print("ポケモンカードデータベース セットアップ")
    print("=" * 60)

    # backendディレクトリ内から実行する想定のパス
    db_path = "data/pokemon_cards.db"
    scraped_dir = "scripts/scraping/backend/data/scraped/raw"

    # ステップ1: データベース作成
    print("\n[1/2] データベースを作成中...")
    create_database(db_path)

    # ステップ2: JSONファイルを全て動的にインポート
    print("\n[2/2] スクレイピングデータをインポート中...")
    import_all_json_files(scraped_dir, db_path)

    # 結果確認
    count = get_card_count(db_path)

    print("\n" + "=" * 60)
    print(f"✅ セットアップ完了！")
    print(f"📊 登録カード数: {count}枚")
    print(f"💾 データベース: {db_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()