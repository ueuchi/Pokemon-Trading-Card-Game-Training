"""
データベース接続ユーティリティ
"""
import sqlite3
from contextlib import contextmanager
from typing import Generator


DATABASE_PATH = "data/pokemon_cards.db"


@contextmanager
def get_db_connection() -> Generator[sqlite3.Connection, None, None]:
    """
    データベース接続のコンテキストマネージャー
    
    使用例:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM cards")
    """
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row  # 辞書形式でアクセス可能にする
    try:
        yield conn
    finally:
        conn.close()


def get_db() -> sqlite3.Connection:
    """
    データベース接続を取得（FastAPI用）
    
    使用例:
        @app.get("/cards")
        def get_cards(db: sqlite3.Connection = Depends(get_db)):
            cursor = db.cursor()
            cursor.execute("SELECT * FROM cards")
    """
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        return conn
    except Exception:
        conn.close()
        raise