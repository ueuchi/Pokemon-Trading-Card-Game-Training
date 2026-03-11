"""
フェーズ6: デッキ管理API

エンドポイント:
  GET    /api/decks              全デッキ一覧
  POST   /api/decks              デッキ新規作成
  GET    /api/decks/{id}         デッキ取得
  PUT    /api/decks/{id}         デッキ更新
  DELETE /api/decks/{id}         デッキ削除

DB スキーマ（初回起動時に自動作成）:
  decks テーブル:
    id          INTEGER PRIMARY KEY AUTOINCREMENT
    name        TEXT NOT NULL
    description TEXT DEFAULT ''
    energies    TEXT DEFAULT '{}'  -- 基本エネルギー枚数 JSON {"草": 10, "炎": 6}
    created_at  TEXT

  deck_cards テーブル:
    id       INTEGER PRIMARY KEY AUTOINCREMENT
    deck_id  INTEGER REFERENCES decks(id) ON DELETE CASCADE
    card_id  INTEGER REFERENCES cards(id)
    count    INTEGER NOT NULL DEFAULT 1
"""
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from database.connection import get_db_connection

router = APIRouter(prefix="/api/decks", tags=["デッキ管理"])

TOTAL_CARDS = 60
MAX_SAME_CARD = 4


# ==================== スキーマ初期化 ====================

def init_deck_tables():
    """デッキ関連テーブルを初期化（存在しない場合のみ作成）"""
    with get_db_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS decks (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                description TEXT DEFAULT '',
                energies    TEXT DEFAULT '{}',
                created_at  TEXT DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TABLE IF NOT EXISTS deck_cards (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                deck_id  INTEGER NOT NULL REFERENCES decks(id) ON DELETE CASCADE,
                card_id  INTEGER NOT NULL REFERENCES cards(id),
                count    INTEGER NOT NULL DEFAULT 1,
                UNIQUE(deck_id, card_id)
            );
        """)


# ==================== リクエスト/レスポンスモデル ====================

class DeckCardEntry(BaseModel):
    card_id: int
    count: int


class DeckCreateRequest(BaseModel):
    name: str
    description: Optional[str] = ''
    cards: list[DeckCardEntry] = []
    energies: dict[str, int] = {}   # {"草": 10, "炎": 6} 基本エネルギー枚数


class DeckUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    cards: Optional[list[DeckCardEntry]] = None
    energies: Optional[dict[str, int]] = None


# ==================== ヘルパー ====================

def _fetch_deck(conn, deck_id: int) -> dict:
    """デッキIDからデッキ情報（カード一覧・エネルギー含む）を取得"""
    deck_row = conn.execute(
        "SELECT id, name, description, energies, created_at FROM decks WHERE id = ?",
        (deck_id,)
    ).fetchone()
    if not deck_row:
        return None

    cards = conn.execute("""
        SELECT dc.card_id, dc.count,
               c.name, c.hp, c.type, c.evolution_stage, c.image_url, c.card_type
        FROM deck_cards dc
        JOIN cards c ON c.id = dc.card_id
        WHERE dc.deck_id = ?
        ORDER BY c.evolution_stage, c.name
    """, (deck_id,)).fetchall()

    energies = json.loads(deck_row["energies"] or '{}')
    energy_total = sum(energies.values())
    card_total = sum(r["count"] for r in cards)

    return {
        "id": deck_row["id"],
        "name": deck_row["name"],
        "description": deck_row["description"],
        "energies": energies,
        "created_at": deck_row["created_at"],
        "total_count": card_total + energy_total,
        "cards": [
            {
                "card_id": r["card_id"],
                "count": r["count"],
                "name": r["name"],
                "hp": r["hp"],
                "type": r["type"],
                "evolution_stage": r["evolution_stage"],
                "image_url": r["image_url"],
                "card_type": r["card_type"],
            }
            for r in cards
        ],
    }


def _validate(cards: list[DeckCardEntry], energies: dict[str, int], conn=None) -> list[str]:
    """バリデーション。エラーメッセージのリストを返す
    conn が渡された場合、card_type='energy' のカードは枚数制限なしとして扱う。
    """
    errors = []
    card_total = sum(c.count for c in cards)
    energy_total = sum(energies.values())
    total = card_total + energy_total

    if total > TOTAL_CARDS:
        errors.append(f"デッキは{TOTAL_CARDS}枚以内にしてください（現在: {total}枚）")

    # DB からエネルギーカードIDを取得（枚数制限なし対象）
    energy_card_ids: set[int] = set()
    if conn and cards:
        card_ids = [c.card_id for c in cards]
        placeholders = ','.join('?' * len(card_ids))
        rows = conn.execute(
            f"SELECT id FROM cards WHERE id IN ({placeholders}) AND card_type = 'energy'",
            card_ids
        ).fetchall()
        energy_card_ids = {r['id'] for r in rows}

    for entry in cards:
        if entry.count < 1:
            errors.append(f"カードID {entry.card_id} の枚数が不正です")
        elif entry.card_id not in energy_card_ids and entry.count > MAX_SAME_CARD:
            errors.append(
                f"カードID {entry.card_id} は{MAX_SAME_CARD}枚まで入れられます（指定: {entry.count}枚）"
            )
    for energy_type, count in energies.items():
        if count < 1:
            errors.append(f"{energy_type}エネルギーの枚数が不正です")
    return errors


# ==================== エンドポイント ====================

@router.get("")
async def list_decks():
    with get_db_connection() as conn:
        rows = conn.execute("SELECT id FROM decks ORDER BY created_at DESC").fetchall()
        return [_fetch_deck(conn, r["id"]) for r in rows]


@router.post("", status_code=201)
async def create_deck(req: DeckCreateRequest):
    if not req.name.strip():
        raise HTTPException(status_code=400, detail="デッキ名は必須です")

    with get_db_connection() as conn:
        errors = _validate(req.cards, req.energies, conn)
        if errors:
            raise HTTPException(status_code=400, detail={"errors": errors})

        cur = conn.execute(
            "INSERT INTO decks (name, description, energies) VALUES (?, ?, ?)",
            (req.name.strip(), req.description or '', json.dumps(req.energies, ensure_ascii=False))
        )
        deck_id = cur.lastrowid
        for entry in req.cards:
            conn.execute(
                "INSERT INTO deck_cards (deck_id, card_id, count) VALUES (?, ?, ?)",
                (deck_id, entry.card_id, entry.count)
            )
        return _fetch_deck(conn, deck_id)


@router.get("/{deck_id}")
async def get_deck(deck_id: int):
    with get_db_connection() as conn:
        deck = _fetch_deck(conn, deck_id)
    if not deck:
        raise HTTPException(status_code=404, detail=f"デッキが見つかりません: {deck_id}")
    return deck


@router.put("/{deck_id}")
async def update_deck(deck_id: int, req: DeckUpdateRequest):
    with get_db_connection() as conn:
        if not conn.execute("SELECT id FROM decks WHERE id = ?", (deck_id,)).fetchone():
            raise HTTPException(status_code=404, detail=f"デッキが見つかりません: {deck_id}")

        if req.name is not None:
            if not req.name.strip():
                raise HTTPException(status_code=400, detail="デッキ名は必須です")
            conn.execute("UPDATE decks SET name = ? WHERE id = ?", (req.name.strip(), deck_id))

        if req.description is not None:
            conn.execute("UPDATE decks SET description = ? WHERE id = ?", (req.description, deck_id))

        if req.energies is not None:
            conn.execute(
                "UPDATE decks SET energies = ? WHERE id = ?",
                (json.dumps(req.energies, ensure_ascii=False), deck_id)
            )

        if req.cards is not None:
            current_energies = json.loads(
                conn.execute("SELECT energies FROM decks WHERE id = ?", (deck_id,))
                .fetchone()["energies"] or '{}'
            )
            errors = _validate(req.cards, req.energies or current_energies, conn)
            if errors:
                raise HTTPException(status_code=400, detail={"errors": errors})

            conn.execute("DELETE FROM deck_cards WHERE deck_id = ?", (deck_id,))
            for entry in req.cards:
                conn.execute(
                    "INSERT INTO deck_cards (deck_id, card_id, count) VALUES (?, ?, ?)",
                    (deck_id, entry.card_id, entry.count)
                )

        return _fetch_deck(conn, deck_id)


@router.delete("/{deck_id}", status_code=204)
async def delete_deck(deck_id: int):
    with get_db_connection() as conn:
        result = conn.execute("DELETE FROM decks WHERE id = ?", (deck_id,))
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"デッキが見つかりません: {deck_id}")
