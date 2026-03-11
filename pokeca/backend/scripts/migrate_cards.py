"""
カードテーブルマイグレーション
実行方法: backend/ ディレクトリで
  python scripts/migrate_cards.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.connection import get_db_connection

def migrate():
    with get_db_connection() as conn:
        cursor = conn.execute("PRAGMA table_info(cards)")
        existing_cols = {row["name"] for row in cursor.fetchall()}
        print(f"既存カラム: {existing_cols}")
        migrations = [
            ("pokemon_type",       "TEXT DEFAULT NULL"),
            ("card_rule",          "TEXT DEFAULT NULL"),
            ("ability",            "TEXT DEFAULT NULL"),
            ("image_url",          "TEXT DEFAULT NULL"),
            ("energy_type",        "TEXT DEFAULT NULL"),
            ("trainer_type",       "TEXT DEFAULT NULL"),
            ("is_ace_spec",        "INTEGER DEFAULT 0"),
            ("effect_description", "TEXT DEFAULT NULL"),
        ]
        added = 0
        for col_name, col_def in migrations:
            if col_name not in existing_cols:
                conn.execute(f"ALTER TABLE cards ADD COLUMN {col_name} {col_def}")
                print(f"  ✅ カラム追加: {col_name}")
                added += 1
            else:
                print(f"  ⚠️  スキップ (既存): {col_name}")
        conn.commit()
        print(f"\n✅ マイグレーション完了 ({added} カラム追加)")

if __name__ == "__main__":
    migrate()
