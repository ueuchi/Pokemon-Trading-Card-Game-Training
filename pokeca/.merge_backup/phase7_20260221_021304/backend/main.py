from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import sqlite3

from models.card import PokemonCard, CardCreateRequest, CardUpdateRequest
from database.connection import get_db_connection
from repositories.card_repository import CardRepository
from api.deck import router as decks_router, init_deck_tables


# 起動・終了時の処理
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 起動時
    init_deck_tables()
    print("=" * 60)
    print("🚀 ポケモンカードゲーム API 起動")
    print("=" * 60)
    print("📍 URL: http://localhost:8000")
    print("📖 API Docs: http://localhost:8000/docs")
    print("=" * 60)
    yield
    # 終了時（必要であれば処理を追加）


# FastAPIアプリケーション初期化
app = FastAPI(
    title="ポケモンカードゲーム API",
    description="ポケモンカードの管理・検索API",
    version="1.0.0",
    lifespan=lifespan
    
)

app.include_router(decks_router)

# CORS設定（Angular開発サーバーからのアクセスを許可）
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4200",  # Angular開発サーバー
        "http://127.0.0.1:4200",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== エンドポイント ====================

@app.get("/")
async def root():
    """
    ルートエンドポイント
    """
    return {
        "message": "ポケモンカードゲーム API",
        "version": "1.0.0",
        "endpoints": {
            "cards": "/api/cards",
            "card_by_id": "/api/cards/{id}",
            "search_by_type": "/api/cards/type/{type}",
            "search_by_name": "/api/cards/search?name={name}",
            "docs": "/docs"
        }
    }


@app.get("/api/cards", response_model=List[PokemonCard])
async def get_all_cards():
    """
    全カード一覧を取得
    
    Returns:
        List[PokemonCard]: カード一覧
    """
    try:
        with get_db_connection() as conn:
            repository = CardRepository(conn)
            cards = repository.get_all_cards()
            return cards
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"カードの取得に失敗しました: {str(e)}")


@app.get("/api/cards/{card_id}", response_model=PokemonCard)
async def get_card(card_id: int):
    """
    IDでカードを取得
    
    Args:
        card_id: カードID
    
    Returns:
        PokemonCard: カード情報
    """
    try:
        with get_db_connection() as conn:
            repository = CardRepository(conn)
            card = repository.get_card_by_id(card_id)
            
            if not card:
                raise HTTPException(status_code=404, detail=f"カードが見つかりません (ID: {card_id})")
            
            return card
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"カードの取得に失敗しました: {str(e)}")


@app.get("/api/cards/type/{card_type}", response_model=List[PokemonCard])
async def get_cards_by_type(card_type: str):
    """
    タイプでカードを検索
    
    Args:
        card_type: カードタイプ（草、炎、水、雷、超、闘、悪、鋼、ドラゴン、フェアリー、無色）
    
    Returns:
        List[PokemonCard]: 該当カード一覧
    """
    try:
        with get_db_connection() as conn:
            repository = CardRepository(conn)
            cards = repository.get_cards_by_type(card_type)
            return cards
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"カードの検索に失敗しました: {str(e)}")


@app.get("/api/cards/search", response_model=List[PokemonCard])
async def search_cards_by_name(name: str):
    """
    名前でカードを検索（部分一致）
    
    Args:
        name: カード名（部分一致）
    
    Returns:
        List[PokemonCard]: 該当カード一覧
    """
    try:
        with get_db_connection() as conn:
            repository = CardRepository(conn)
            cards = repository.get_cards_by_name(name)
            return cards
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"カードの検索に失敗しました: {str(e)}")


@app.post("/api/cards", response_model=PokemonCard, status_code=201)
async def create_card(card_data: CardCreateRequest):
    """
    新しいカードを作成
    
    Args:
        card_data: カード作成データ
    
    Returns:
        PokemonCard: 作成されたカード
    """
    try:
        with get_db_connection() as conn:
            repository = CardRepository(conn)
            card_id = repository.create_card(card_data.dict())
            card = repository.get_card_by_id(card_id)
            return card
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"カードの作成に失敗しました: {str(e)}")


@app.put("/api/cards/{card_id}", response_model=PokemonCard)
async def update_card(card_id: int, card_data: CardUpdateRequest):
    """
    カードを更新
    
    Args:
        card_id: カードID
        card_data: 更新データ
    
    Returns:
        PokemonCard: 更新されたカード
    """
    try:
        with get_db_connection() as conn:
            repository = CardRepository(conn)
            
            # 既存カードの確認
            existing_card = repository.get_card_by_id(card_id)
            if not existing_card:
                raise HTTPException(status_code=404, detail=f"カードが見つかりません (ID: {card_id})")
            
            # 更新実行
            update_data = card_data.dict(exclude_unset=True)
            repository.update_card(card_id, update_data)
            
            # 更新後のカードを取得
            updated_card = repository.get_card_by_id(card_id)
            return updated_card
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"カードの更新に失敗しました: {str(e)}")


@app.delete("/api/cards/{card_id}", status_code=204)
async def delete_card(card_id: int):
    """
    カードを削除
    
    Args:
        card_id: カードID
    """
    try:
        with get_db_connection() as conn:
            repository = CardRepository(conn)
            
            # 既存カードの確認
            existing_card = repository.get_card_by_id(card_id)
            if not existing_card:
                raise HTTPException(status_code=404, detail=f"カードが見つかりません (ID: {card_id})")
            
            # 削除実行
            repository.delete_card(card_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"カードの削除に失敗しました: {str(e)}")


@app.get("/api/stats")
async def get_stats():
    """
    統計情報を取得
    
    Returns:
        dict: カード統計
    """
    try:
        with get_db_connection() as conn:
            repository = CardRepository(conn)
            total_cards = repository.get_card_count()
            
            return {
                "total_cards": total_cards,
                "database": "pokemon_cards.db"
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"統計情報の取得に失敗しました: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)