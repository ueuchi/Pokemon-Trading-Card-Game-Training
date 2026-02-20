#!/bin/bash
# ポケモンTCGエンジン セットアップスクリプト
# プロジェクトルートで実行: bash setup.sh

set -e
echo "セットアップ開始..."

# ---- backend/api/deck.py ----
mkdir -p "backend/api"
cat > 'backend/api/deck.py' << 'FILEOF'
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
               c.name, c.hp, c.type, c.evolution_stage, c.image_url
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
            }
            for r in cards
        ],
    }


def _validate(cards: list[DeckCardEntry], energies: dict[str, int]) -> list[str]:
    """バリデーション。エラーメッセージのリストを返す"""
    errors = []
    card_total = sum(c.count for c in cards)
    energy_total = sum(energies.values())
    total = card_total + energy_total

    if total > TOTAL_CARDS:
        errors.append(f"デッキは{TOTAL_CARDS}枚以内にしてください（現在: {total}枚）")
    for entry in cards:
        if entry.count < 1:
            errors.append(f"カードID {entry.card_id} の枚数が不正です")
        elif entry.count > MAX_SAME_CARD:
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

    errors = _validate(req.cards, req.energies)
    if errors:
        raise HTTPException(status_code=400, detail={"errors": errors})

    with get_db_connection() as conn:
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
            errors = _validate(req.cards, req.energies or current_energies)
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
FILEOF

# ---- backend/api/game.py ----
mkdir -p "backend/api"
cat > 'backend/api/game.py' << 'FILEOF'
"""
タスク4-3: CPU対戦 FastAPI エンドポイント

エンドポイント一覧:
  POST /api/game/cpu/start          ゲーム開始（セットアップ〜初期配置）
  GET  /api/game/cpu/{game_id}      ゲーム状態取得
  POST /api/game/cpu/{game_id}/place_initial   初期ポケモン配置
  POST /api/game/cpu/{game_id}/action          プレイヤーのアクション実行
  POST /api/game/cpu/{game_id}/end_turn        ターン終了（CPUが自動実行）
  POST /api/game/cpu/{game_id}/replace_active  きぜつ後のバトル場交代
  DELETE /api/game/cpu/{game_id}               セッション削除
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List

from engine.setup.game_setup import setup_game, place_initial_pokemon, start_game
from engine.turn.turn_manager import begin_turn, end_turn
from engine.actions.place_pokemon import place_to_active, place_to_bench
from engine.actions.evolve import evolve_active, evolve_bench
from engine.actions.attach_energy import attach_energy
from engine.actions.retreat import retreat
from engine.actions.trainer import use_supporter, use_goods, use_stadium
from engine.actions.attack import declare_attack
from engine.actions.faint import send_to_active_from_bench
from cpu.cpu_ai import cpu_take_turn, cpu_choose_active_after_faint
from cpu.game_session import create_session, get_session, delete_session
from database.connection import get_db_connection
from repositories.card_repository import CardRepository

router = APIRouter(prefix="/api/game/cpu", tags=["CPU対戦"])


# ==================== リクエストモデル ====================

class StartGameRequest(BaseModel):
    player_deck_id: int   # DBに保存されているデッキID（フェーズ6以降で利用）
    cpu_deck_id: Optional[int] = None  # 未指定の場合はサンプルデッキを使用


class PlaceInitialRequest(BaseModel):
    active_card_id: int
    bench_card_ids: List[int] = []


class ActionRequest(BaseModel):
    action_type: str   # "place_active" | "place_bench" | "attach_energy" |
                       # "evolve_active" | "evolve_bench" | "retreat" |
                       # "use_supporter" | "use_goods" | "use_stadium" | "attack"
    card_id: Optional[int] = None
    attack_index: Optional[int] = None
    bench_index: Optional[int] = None
    energy_indices: Optional[List[int]] = None
    target: Optional[str] = None   # "active" | "bench"


class ReplaceActiveRequest(BaseModel):
    bench_index: int


# ==================== エンドポイント ====================

@router.post("/start")
async def start_cpu_game(request: StartGameRequest):
    """
    CPU対戦を開始する。
    デッキIDを受け取り、両プレイヤーのデッキをDBから取得してゲームを初期化する。
    フェーズ4ではデッキIDは無視してサンプルカードで代替。
    """
    try:
        with get_db_connection() as conn:
            repo = CardRepository(conn)
            all_cards = repo.get_all_cards()

        if len(all_cards) < 2:
            raise HTTPException(status_code=400, detail="DBにカードが不足しています（最低2枚必要）")

        # サンプルデッキを作成（DBの全カードを繰り返して60枚にする）
        def make_sample_deck(cards, base_size=60):
            deck = []
            while len(deck) < base_size:
                deck.extend(cards)
            return deck[:base_size]

        p1_deck = make_sample_deck(all_cards)
        p2_deck = make_sample_deck(all_cards)

        game_state = setup_game(p1_deck, p2_deck)
        game_id = create_session(game_state)

        return {
            "game_id": game_id,
            "message": "ゲームを初期化しました。初期ポケモンを配置してください。",
            "state": game_state.to_dict(),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{game_id}")
async def get_game_state(game_id: str):
    """現在のゲーム状態を取得する"""
    game_state = get_session(game_id)
    if not game_state:
        raise HTTPException(status_code=404, detail=f"ゲームセッションが見つかりません: {game_id}")
    return game_state.to_dict()


@router.post("/{game_id}/place_initial")
async def place_initial(game_id: str, request: PlaceInitialRequest):
    """
    プレイヤーの初期ポケモンを配置し、CPUも自動配置してゲームを開始する。
    """
    game_state = get_session(game_id)
    if not game_state:
        raise HTTPException(status_code=404, detail="ゲームセッションが見つかりません")

    try:
        # プレイヤー1の配置
        p1 = game_state.player1
        active_card = next((c for c in p1.hand if c.id == request.active_card_id), None)
        if not active_card:
            raise HTTPException(status_code=400, detail="指定のカードが手札にありません")

        bench_cards = [c for c in p1.hand if c.id in request.bench_card_ids]
        place_initial_pokemon(game_state, "player1", active_card, bench_cards)

        # CPU（player2）の自動配置: HPが最大のたねポケモンをバトル場へ
        p2 = game_state.player2
        basics = [c for c in p2.hand if c.evolution_stage == "たね"]
        if not basics:
            raise HTTPException(status_code=500, detail="CPUの手札にたねポケモンがありません")

        cpu_active = max(basics, key=lambda c: c.hp or 0)
        cpu_bench = [c for c in basics if c.id != cpu_active.id][:5]
        place_initial_pokemon(game_state, "player2", cpu_active, cpu_bench)

        # ゲーム開始
        start_game(game_state)

        # 先行がCPUの場合は即ターンを実行
        cpu_actions = []
        if game_state.current_player_id == "player2":
            cpu_actions = cpu_take_turn(game_state)

        return {
            "message": "ゲーム開始！",
            "cpu_actions": cpu_actions,
            "state": game_state.to_dict(),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{game_id}/action")
async def player_action(game_id: str, request: ActionRequest):
    """
    プレイヤーの各種アクションを実行する。
    ターン開始時のドローは最初のアクション送信時に自動実行する。
    """
    game_state = get_session(game_id)
    if not game_state:
        raise HTTPException(status_code=404, detail="ゲームセッションが見つかりません")

    if game_state.is_game_over:
        raise HTTPException(status_code=400, detail="ゲームはすでに終了しています")
    if game_state.current_player_id != "player1":
        raise HTTPException(status_code=400, detail="プレイヤー1のターンではありません")

    # ターン開始（まだドローしていなければ実行）
    from engine.models.game_enums import TurnPhase
    draw_result = None
    if game_state.turn_phase == TurnPhase.DRAW:
        draw_result = begin_turn(game_state)
        if not draw_result["success"] or game_state.is_game_over:
            return {"draw_result": draw_result, "state": game_state.to_dict()}

    # アクション振り分け
    action = request.action_type
    result = None

    if action == "place_active":
        result = place_to_active(game_state, "player1", request.card_id)
    elif action == "place_bench":
        result = place_to_bench(game_state, "player1", request.card_id)
    elif action == "attach_energy":
        result = attach_energy(
            game_state, "player1", request.card_id,
            request.target or "active", request.bench_index or -1
        )
    elif action == "evolve_active":
        result = evolve_active(game_state, "player1", request.card_id)
    elif action == "evolve_bench":
        result = evolve_bench(game_state, "player1", request.bench_index, request.card_id)
    elif action == "retreat":
        result = retreat(
            game_state, "player1",
            request.bench_index, request.energy_indices or []
        )
    elif action == "use_supporter":
        result = use_supporter(game_state, "player1", request.card_id)
    elif action == "use_goods":
        result = use_goods(game_state, "player1", request.card_id)
    elif action == "use_stadium":
        result = use_stadium(game_state, "player1", request.card_id)
    elif action == "attack":
        result = declare_attack(game_state, "player1", request.attack_index or 0)
    else:
        raise HTTPException(status_code=400, detail=f"不明なアクション: {action}")

    if result and not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "アクション失敗"))

    return {
        "draw_result": draw_result,
        "action_result": result,
        "state": game_state.to_dict(),
    }


@router.post("/{game_id}/end_turn")
async def player_end_turn(game_id: str):
    """
    プレイヤーがターンを終了し、CPUが自動でターンを実行する。
    """
    game_state = get_session(game_id)
    if not game_state:
        raise HTTPException(status_code=404, detail="ゲームセッションが見つかりません")

    if game_state.is_game_over:
        raise HTTPException(status_code=400, detail="ゲームはすでに終了しています")
    if game_state.current_player_id != "player1":
        raise HTTPException(status_code=400, detail="プレイヤー1のターンではありません")

    # ドロー済みでなければ先にドロー
    from engine.models.game_enums import TurnPhase
    if game_state.turn_phase == TurnPhase.DRAW:
        begin_turn(game_state)

    # プレイヤーのターン終了
    end_result = end_turn(game_state)

    cpu_actions = []
    if not game_state.is_game_over:
        # CPUターン実行
        cpu_actions = cpu_take_turn(game_state)

        # CPUターン後にCPUのポケモンがきぜつしていたらCPUが自動で交代
        p2 = game_state.player2
        if not p2.has_active and p2.has_bench_pokemon and not game_state.is_game_over:
            replace = cpu_choose_active_after_faint(game_state)
            cpu_actions.append({"action": "CPU_REPLACE_ACTIVE", **replace})

    return {
        "end_result": end_result,
        "cpu_actions": cpu_actions,
        "state": game_state.to_dict(),
    }


@router.post("/{game_id}/replace_active")
async def replace_active(game_id: str, request: ReplaceActiveRequest):
    """
    プレイヤーのバトルポケモンがきぜつした後にベンチから選んで交代する。
    """
    game_state = get_session(game_id)
    if not game_state:
        raise HTTPException(status_code=404, detail="ゲームセッションが見つかりません")

    p1 = game_state.player1
    if p1.has_active:
        raise HTTPException(status_code=400, detail="バトル場にすでにポケモンがいます")

    result = send_to_active_from_bench(game_state, "player1", request.bench_index)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])

    return {
        "result": result,
        "state": game_state.to_dict(),
    }


@router.delete("/{game_id}")
async def delete_game(game_id: str):
    """ゲームセッションを削除する"""
    deleted = delete_session(game_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="ゲームセッションが見つかりません")
    return {"message": f"セッション {game_id} を削除しました"}
FILEOF

# ---- backend/cpu/cpu_ai.py ----
mkdir -p "backend/cpu"
cat > 'backend/cpu/cpu_ai.py' << 'FILEOF'
"""
CPU思考エンジン（難易度3段階対応）

難易度:
  EASY   - ランダム行動。攻撃できても攻撃しないことがある
  NORMAL - 簡易ルールベース（攻撃できれば攻撃・毎ターンエネルギー付与）
  HARD   - 最大ダメージ優先・KO狙い・進化を活用・HP考慮した交代選択
"""
import random
from enum import Enum
from typing import Optional

from engine.models.game_state import GameState
from engine.actions.place_pokemon import place_to_bench
from engine.actions.evolve import evolve_active, evolve_bench, NEXT_STAGE
from engine.actions.attach_energy import attach_energy
from engine.actions.attack import declare_attack, _check_energy_cost
from engine.actions.faint import send_to_active_from_bench
from engine.turn.turn_manager import begin_turn, end_turn


class CpuDifficulty(str, Enum):
    EASY = "easy"
    NORMAL = "normal"
    HARD = "hard"


class CpuAI:
    """
    難易度に応じた思考ロジックを持つCPU AIクラス。
    player_idはインスタンス生成時またはtake_turn()呼び出し時に決定する。
    """

    def __init__(self, difficulty: CpuDifficulty = CpuDifficulty.NORMAL, player_id: str = "player2"):
        self.difficulty = difficulty
        self.player_id = player_id

    def take_turn(self, game_state: GameState) -> list:
        """CPUが1ターン分の行動をすべて実行する。"""
        if self.difficulty == CpuDifficulty.EASY:
            return self._take_turn_easy(game_state)
        elif self.difficulty == CpuDifficulty.NORMAL:
            return self._take_turn_normal(game_state)
        else:
            return self._take_turn_hard(game_state)

    def choose_active_after_faint(self, game_state: GameState) -> dict:
        """きぜつ後のバトル場交代。難易度に応じた選択をする。"""
        player = game_state.get_player(self.player_id)
        if not player.has_bench_pokemon:
            return {"success": False, "message": "ベンチにポケモンがいません"}
        if self.difficulty == CpuDifficulty.EASY:
            index = random.randrange(len(player.bench))
        elif self.difficulty == CpuDifficulty.NORMAL:
            index = max(range(len(player.bench)), key=lambda i: player.bench[i].current_hp)
        else:
            index = self._best_bench_index_hard(player)
        return send_to_active_from_bench(game_state, self.player_id, index)

    # ===== EASY =====
    def _take_turn_easy(self, game_state: GameState) -> list:
        actions = []
        draw_result = begin_turn(game_state)
        actions.append({"action": "DRAW", **draw_result})
        if not draw_result["success"] or game_state.is_game_over:
            return actions

        player = game_state.get_player(self.player_id)
        if not player.has_active:
            r = self._fill_active(game_state)
            if r:
                actions.append(r)
            if game_state.is_game_over:
                return actions

        if random.random() < 0.5:
            actions.extend(self._fill_bench(game_state))
        if random.random() < 0.5:
            r = self._attach_energy_normal(game_state)
            if r:
                actions.append(r)
        if not game_state.is_first_turn and random.random() < 0.6:
            r = self._attack_random(game_state)
            if r:
                actions.append(r)
                if game_state.is_game_over:
                    return actions

        end_result = end_turn(game_state)
        actions.append({"action": "END_TURN", **end_result})
        return actions

    # ===== NORMAL =====
    def _take_turn_normal(self, game_state: GameState) -> list:
        actions = []
        draw_result = begin_turn(game_state)
        actions.append({"action": "DRAW", **draw_result})
        if not draw_result["success"] or game_state.is_game_over:
            return actions

        player = game_state.get_player(self.player_id)
        if not player.has_active:
            r = self._fill_active(game_state)
            if r:
                actions.append(r)
            if game_state.is_game_over:
                return actions

        actions.extend(self._fill_bench(game_state))
        r = self._attach_energy_normal(game_state)
        if r:
            actions.append(r)

        if not game_state.is_first_turn:
            r = self._attack_best_damage(game_state)
            if r:
                actions.append(r)
                if game_state.is_game_over:
                    return actions

        end_result = end_turn(game_state)
        actions.append({"action": "END_TURN", **end_result})
        return actions

    # ===== HARD =====
    def _take_turn_hard(self, game_state: GameState) -> list:
        actions = []
        draw_result = begin_turn(game_state)
        actions.append({"action": "DRAW", **draw_result})
        if not draw_result["success"] or game_state.is_game_over:
            return actions

        player = game_state.get_player(self.player_id)
        if not player.has_active:
            r = self._fill_active(game_state)
            if r:
                actions.append(r)
            if game_state.is_game_over:
                return actions

        r = self._try_evolve_active(game_state)
        if r:
            actions.append(r)
        actions.extend(self._try_evolve_bench(game_state))
        actions.extend(self._fill_bench_smart(game_state))

        r = self._attach_energy_smart(game_state)
        if r:
            actions.append(r)

        if not game_state.is_first_turn:
            r = self._attack_smart(game_state)
            if r:
                actions.append(r)
                if game_state.is_game_over:
                    return actions

        end_result = end_turn(game_state)
        actions.append({"action": "END_TURN", **end_result})
        return actions

    # ===== 共通ヘルパー =====
    def _fill_active(self, game_state):
        player = game_state.get_player(self.player_id)
        if player.has_active or not player.has_bench_pokemon:
            return None
        index = max(range(len(player.bench)), key=lambda i: player.bench[i].current_hp)
        r = send_to_active_from_bench(game_state, self.player_id, index)
        return {"action": "FILL_ACTIVE", **r}

    def _fill_bench(self, game_state):
        results = []
        player = game_state.get_player(self.player_id)
        for card in list(player.hand):
            if player.bench_is_full:
                break
            if card.evolution_stage == "たね":
                r = place_to_bench(game_state, self.player_id, card.id)
                if r["success"]:
                    results.append({"action": "PLACE_BENCH", **r})
        return results

    def _fill_bench_smart(self, game_state):
        results = []
        player = game_state.get_player(self.player_id)
        basics = sorted(
            [c for c in player.hand if c.evolution_stage == "たね"],
            key=lambda c: c.hp or 0, reverse=True
        )
        for card in basics:
            if player.bench_is_full:
                break
            r = place_to_bench(game_state, self.player_id, card.id)
            if r["success"]:
                results.append({"action": "PLACE_BENCH", **r})
        return results

    def _attach_energy_normal(self, game_state):
        player = game_state.get_player(self.player_id)
        if player.energy_attached_this_turn or not player.has_active:
            return None
        energy_cards = [c for c in player.hand if c.evolution_stage == "エネルギー"]
        if not energy_cards:
            return None
        active = player.active_pokemon
        needed = {e for atk in active.card.attacks for e in atk.energy}
        chosen = next((c for c in energy_cards if c.type in needed), energy_cards[0])
        r = attach_energy(game_state, self.player_id, chosen.id, "active")
        return {"action": "ATTACH_ENERGY", **r}

    def _attach_energy_smart(self, game_state):
        player = game_state.get_player(self.player_id)
        if player.energy_attached_this_turn or not player.has_active:
            return None
        energy_cards = [c for c in player.hand if c.evolution_stage == "エネルギー"]
        if not energy_cards:
            return None
        active = player.active_pokemon
        best_card, min_shortage = None, float("inf")
        for ec in energy_cards:
            for atk in active.card.attacks:
                shortage = _count_shortage(active.attached_energy + [ec.type], atk.energy)
                if shortage < min_shortage:
                    min_shortage = shortage
                    best_card = ec
        chosen = best_card or energy_cards[0]
        r = attach_energy(game_state, self.player_id, chosen.id, "active")
        return {"action": "ATTACH_ENERGY", **r}

    def _attack_random(self, game_state):
        player = game_state.get_player(self.player_id)
        opponent = game_state.get_opponent_of(self.player_id)
        if not player.has_active or not opponent.has_active:
            return None
        active = player.active_pokemon
        usable = [i for i, atk in enumerate(active.card.attacks)
                  if _check_energy_cost(active.attached_energy, atk.energy)["ok"]]
        if not usable:
            return None
        r = declare_attack(game_state, self.player_id, random.choice(usable))
        return {"action": "ATTACK", **r}

    def _attack_best_damage(self, game_state):
        player = game_state.get_player(self.player_id)
        opponent = game_state.get_opponent_of(self.player_id)
        if not player.has_active or not opponent.has_active:
            return None
        active = player.active_pokemon
        best_i, best_dmg = None, -1
        for i, atk in enumerate(active.card.attacks):
            if _check_energy_cost(active.attached_energy, atk.energy)["ok"] and atk.damage > best_dmg:
                best_dmg, best_i = atk.damage, i
        if best_i is None:
            return None
        r = declare_attack(game_state, self.player_id, best_i)
        return {"action": "ATTACK", **r}

    def _attack_smart(self, game_state):
        player = game_state.get_player(self.player_id)
        opponent = game_state.get_opponent_of(self.player_id)
        if not player.has_active or not opponent.has_active:
            return None
        attacker = player.active_pokemon
        defender = opponent.active_pokemon
        attacker_type = attacker.card.type or ""
        best_i, best_score = None, -1
        for i, atk in enumerate(attacker.card.attacks):
            if not _check_energy_cost(attacker.attached_energy, atk.energy)["ok"]:
                continue
            dmg = atk.damage
            if defender.card.weakness and defender.card.weakness.type == attacker_type:
                dmg *= 2
            if defender.card.resistance and defender.card.resistance.type == attacker_type:
                dmg = max(0, dmg - 30)
            # KOできればボーナス
            score = dmg * 10 if dmg >= defender.current_hp else dmg
            if score > best_score:
                best_score, best_i = score, i
        if best_i is None:
            return None
        r = declare_attack(game_state, self.player_id, best_i)
        return {"action": "ATTACK", **r}

    def _try_evolve_active(self, game_state):
        player = game_state.get_player(self.player_id)
        if not player.has_active:
            return None
        active = player.active_pokemon
        if active.turns_in_play == 0 or game_state.current_turn == 1:
            return None
        next_stage = NEXT_STAGE.get(active.card.evolution_stage)
        if not next_stage:
            return None
        evo_card = next((c for c in player.hand if c.evolution_stage == next_stage), None)
        if not evo_card:
            return None
        r = evolve_active(game_state, self.player_id, evo_card.id)
        return {"action": "EVOLVE_ACTIVE", **r} if r["success"] else None

    def _try_evolve_bench(self, game_state):
        results = []
        player = game_state.get_player(self.player_id)
        for i, bench_mon in enumerate(player.bench):
            if bench_mon.turns_in_play == 0 or game_state.current_turn == 1:
                continue
            next_stage = NEXT_STAGE.get(bench_mon.card.evolution_stage)
            if not next_stage:
                continue
            evo_card = next((c for c in player.hand if c.evolution_stage == next_stage), None)
            if not evo_card:
                continue
            r = evolve_bench(game_state, self.player_id, i, evo_card.id)
            if r["success"]:
                results.append({"action": "EVOLVE_BENCH", **r})
        return results

    def _best_bench_index_hard(self, player):
        return max(
            range(len(player.bench)),
            key=lambda i: player.bench[i].energy_count * 100 + player.bench[i].current_hp
        )


# ===== 後方互換（フェーズ3デモ等から呼ばれる） =====
def cpu_take_turn(game_state: GameState) -> list:
    return CpuAI(CpuDifficulty.NORMAL, player_id="player2").take_turn(game_state)

def cpu_choose_active_after_faint(game_state: GameState) -> dict:
    return CpuAI(CpuDifficulty.NORMAL, player_id="player2").choose_active_after_faint(game_state)


# ===== ユーティリティ =====
def _count_shortage(available: list, required: list) -> int:
    avail = available.copy()
    shortage = 0
    for e in [x for x in required if x != "無色"]:
        if e in avail:
            avail.remove(e)
        else:
            shortage += 1
    return shortage + max(0, required.count("無色") - len(avail))
FILEOF

# ---- backend/cpu/game_session.py ----
mkdir -p "backend/cpu"
cat > 'backend/cpu/game_session.py' << 'FILEOF'
"""
タスク4-3: ゲームセッション管理
メモリ上の dict で game_id → GameState を管理する
"""
from typing import Dict, Optional
from engine.models.game_state import GameState


# メモリ上のセッションストア
_sessions: Dict[str, GameState] = {}


def create_session(game_state: GameState) -> str:
    """GameStateを登録してgame_idを返す"""
    _sessions[game_state.game_id] = game_state
    return game_state.game_id


def get_session(game_id: str) -> Optional[GameState]:
    """game_idに対応するGameStateを返す（なければNone）"""
    return _sessions.get(game_id)


def delete_session(game_id: str) -> bool:
    """セッションを削除する"""
    if game_id in _sessions:
        del _sessions[game_id]
        return True
    return False


def list_sessions() -> list[str]:
    """全セッションのgame_idリストを返す"""
    return list(_sessions.keys())
FILEOF

# ---- backend/engine/actions/attach_energy.py ----
mkdir -p "backend/engine/actions"
cat > 'backend/engine/actions/attach_energy.py' << 'FILEOF'
"""
タスク3-7: エネルギー付与処理
1ターン1回、手札のエネルギーカードを場のポケモンに付与する
"""
from engine.models.game_state import GameState
from engine.models.game_enums import TurnPhase


def attach_energy(
    game_state: GameState,
    player_id: str,
    energy_card_id: int,
    target: str,
    bench_index: int = -1,
) -> dict:
    """
    手札のエネルギーカードを場のポケモンに付与する。

    Args:
        game_state: ゲーム状態
        player_id: 操作プレイヤーID
        energy_card_id: 手札のエネルギーカードID
        target: "active" or "bench"
        bench_index: targetが"bench"の場合のベンチインデックス（0始まり）

    Returns:
        {"success": bool, "message": str}
    """
    player = game_state.get_player(player_id)

    if game_state.current_player_id != player_id:
        return {"success": False, "message": "自分のターンではありません"}
    if game_state.turn_phase != TurnPhase.MAIN:
        return {"success": False, "message": "メインフェーズ以外ではエネルギーを付与できません"}

    # 1ターン1回制限チェック
    if player.energy_attached_this_turn:
        return {"success": False, "message": "このターンはすでにエネルギーを付与済みです"}

    # 手札からエネルギーカードを探す
    energy_card = None
    for card in player.hand:
        if card.id == energy_card_id:
            energy_card = card
            break

    if energy_card is None:
        return {"success": False, "message": f"手札にカードID={energy_card_id}が見つかりません"}

    # エネルギータイプの取得（エネルギーカードのtypeをそのまま使用）
    energy_type = energy_card.type or "無色"

    # 付与先ポケモンを特定
    if target == "active":
        if not player.has_active:
            return {"success": False, "message": "バトル場にポケモンがいません"}
        pokemon = player.active_pokemon
        target_name = pokemon.card.name
    elif target == "bench":
        if bench_index < 0 or bench_index >= len(player.bench):
            return {"success": False, "message": f"ベンチインデックス{bench_index}が無効です"}
        pokemon = player.bench[bench_index]
        target_name = pokemon.card.name
    else:
        return {"success": False, "message": f"無効なtarget: {target}。'active' or 'bench'を指定してください"}

    # エネルギーを付与
    pokemon.attached_energy.append(energy_type)
    player.hand = [c for c in player.hand if c.id != energy_card_id]
    player.discard_pile.append(energy_card)
    player.energy_attached_this_turn = True

    game_state.add_log(
        "ATTACH_ENERGY",
        f"{player_id}: {energy_type}エネルギーを{target_name}に付与"
    )
    return {
        "success": True,
        "message": f"{energy_type}エネルギーを{target_name}に付与した"
    }
FILEOF

# ---- backend/engine/actions/attack.py ----
mkdir -p "backend/engine/actions"
cat > 'backend/engine/actions/attack.py' << 'FILEOF'
"""
タスク3-10: 攻撃処理
攻撃宣言・エネルギーコスト確認・ダメージ計算（弱点・抵抗力・ダメージカウンター型）を実装する
"""
from engine.models.game_state import GameState
from engine.models.game_enums import TurnPhase, DamageType
from engine.actions.faint import check_and_process_faint


def declare_attack(
    game_state: GameState,
    player_id: str,
    attack_index: int,
) -> dict:
    """
    攻撃宣言を行いダメージを適用する。
    攻撃後はそのターンを終了し、相手のターンへ移行する。

    Args:
        game_state: ゲーム状態
        player_id: 攻撃プレイヤーID
        attack_index: 使用するワザのインデックス（0始まり）

    Returns:
        {"success": bool, "message": str, "damage": int, "fainted": bool}
    """
    player = game_state.get_player(player_id)
    opponent = game_state.get_opponent_of(player_id)

    if game_state.current_player_id != player_id:
        return {"success": False, "message": "自分のターンではありません", "damage": 0, "fainted": False}
    if game_state.turn_phase != TurnPhase.MAIN:
        return {"success": False, "message": "メインフェーズ以外では攻撃できません", "damage": 0, "fainted": False}
    if game_state.attacked_this_turn:
        return {"success": False, "message": "このターンはすでに攻撃済みです", "damage": 0, "fainted": False}

    # 先行プレイヤーの最初のターンは攻撃不可
    if game_state.is_first_turn:
        return {"success": False, "message": "先行プレイヤーの最初のターンは攻撃できません", "damage": 0, "fainted": False}

    # バトル場のポケモン確認
    if not player.has_active:
        return {"success": False, "message": "バトル場にポケモンがいません", "damage": 0, "fainted": False}
    if not opponent.has_active:
        return {"success": False, "message": "相手のバトル場にポケモンがいません", "damage": 0, "fainted": False}

    attacker = player.active_pokemon
    defender = opponent.active_pokemon

    # ワザ存在チェック
    if attack_index < 0 or attack_index >= len(attacker.card.attacks):
        return {"success": False, "message": f"ワザインデックス{attack_index}が無効です", "damage": 0, "fainted": False}

    attack = attacker.card.attacks[attack_index]

    # エネルギーコストチェック
    cost_check = _check_energy_cost(attacker.attached_energy, attack.energy)
    if not cost_check["ok"]:
        return {
            "success": False,
            "message": f"エネルギーが足りません。必要: {attack.energy}, 現在: {attacker.attached_energy}",
            "damage": 0,
            "fainted": False,
        }

    # ダメージ計算
    damage = _calculate_damage(attack, attacker, defender)

    # ダメージ適用
    damage_counters = damage // 10
    defender.damage_counters += damage_counters

    game_state.attacked_this_turn = True
    game_state.turn_phase = TurnPhase.ATTACK

    game_state.add_log(
        "ATTACK",
        f"{player_id}: {attacker.card.name}の「{attack.name}」→ {defender.card.name}に{damage}ダメージ"
    )

    # きぜつ判定
    faint_result = check_and_process_faint(game_state, player_id)

    return {
        "success": True,
        "message": f"{attacker.card.name}の「{attack.name}」が{defender.card.name}に{damage}ダメージ！",
        "damage": damage,
        "fainted": faint_result.get("fainted", False),
        "faint_detail": faint_result,
    }


def _check_energy_cost(attached: list[str], required: list[str]) -> dict:
    """
    付与されているエネルギーが必要コストを満たすか確認する。
    「無色」エネルギーはどのタイプでも代用可能。

    Args:
        attached: 付与されているエネルギータイプのリスト
        required: ワザに必要なエネルギータイプのリスト

    Returns:
        {"ok": bool}
    """
    available = attached.copy()

    # まず色指定のエネルギーを消費
    colored_required = [e for e in required if e != "無色"]
    colorless_required = required.count("無色")

    for energy_type in colored_required:
        if energy_type in available:
            available.remove(energy_type)
        else:
            return {"ok": False}

    # 残りで無色コストを満たせるか
    if len(available) < colorless_required:
        return {"ok": False}

    return {"ok": True}


def _calculate_damage(attack, attacker, defender) -> int:
    """
    ダメージを計算する。
    - attack.descriptionに"ダメカン"や"ダメージカウンター"が含まれる場合はカウンター型とみなす
    - それ以外は通常ダメージ（弱点×2、抵抗力-30）

    Returns:
        最終ダメージ（10の倍数）
    """
    base_damage = attack.damage

    # ダメージカウンター型の判定（descriptionで簡易判定）
    description = attack.description or ""
    is_counter_type = ("ダメカン" in description or "ダメージカウンター" in description)

    if is_counter_type:
        # ダメージカウンター型: 弱点・抵抗力の計算なし
        return base_damage

    # 通常ダメージ: 弱点・抵抗力を計算
    attacker_type = attacker.card.type or ""
    final_damage = base_damage

    # 弱点チェック（×2）
    if defender.card.weakness and defender.card.weakness.type == attacker_type:
        final_damage *= 2

    # 抵抗力チェック（-30）
    if defender.card.resistance and defender.card.resistance.type == attacker_type:
        final_damage -= 30
        if final_damage < 0:
            final_damage = 0

    return final_damage
FILEOF

# ---- backend/engine/actions/draw.py ----
mkdir -p "backend/engine/actions"
cat > 'backend/engine/actions/draw.py' << 'FILEOF'
"""
タスク3-4: ドロー処理
山札からカードを引く処理
"""
from engine.models.game_state import GameState


def draw_card(game_state: GameState, player_id: str) -> dict:
    """
    指定プレイヤーが山札から1枚引く。
    山札が0枚の場合はエラーを返す（山札切れ判定はbegin_turn側で行う）。

    Returns:
        {"success": bool, "message": str, "card_name": str | None}
    """
    player = game_state.get_player(player_id)

    if player.deck_count == 0:
        return {
            "success": False,
            "message": "山札が0枚です。カードを引けません。",
            "card_name": None,
        }

    card = player.deck.pop(0)
    player.hand.append(card)

    return {
        "success": True,
        "message": f"{card.name}を引いた",
        "card_name": card.name,
    }


def draw_cards(game_state: GameState, player_id: str, count: int) -> dict:
    """
    指定プレイヤーが山札からcount枚引く（サポートカード効果等で複数枚引く場合）。
    山札が足りない場合は引ける分だけ引く。

    Returns:
        {"success": bool, "message": str, "drew_count": int, "card_names": list[str]}
    """
    player = game_state.get_player(player_id)
    drew = []

    for _ in range(count):
        if player.deck_count == 0:
            break
        card = player.deck.pop(0)
        player.hand.append(card)
        drew.append(card.name)

    return {
        "success": True,
        "message": f"{len(drew)}枚引いた",
        "drew_count": len(drew),
        "card_names": drew,
    }
FILEOF

# ---- backend/engine/actions/evolve.py ----
mkdir -p "backend/engine/actions"
cat > 'backend/engine/actions/evolve.py' << 'FILEOF'
"""
タスク3-6: 進化処理
たねポケモン→1進化→2進化の進化ルールを実装する
"""
from engine.models.game_state import GameState
from engine.models.player_state import ActivePokemon, BenchPokemon
from engine.models.game_enums import TurnPhase, SpecialCondition

# 進化段階の順序マッピング
EVOLUTION_ORDER = {
    "たね": 0,
    "1 進化": 1,
    "2 進化": 2,
}

NEXT_STAGE = {
    "たね": "1 進化",
    "1 進化": "2 進化",
}


def evolve_active(game_state: GameState, player_id: str, card_id: int) -> dict:
    """
    バトル場のポケモンを進化させる。

    Args:
        game_state: ゲーム状態
        player_id: 操作プレイヤーID
        card_id: 手札の進化カードのID

    Returns:
        {"success": bool, "message": str}
    """
    player = game_state.get_player(player_id)

    if game_state.current_player_id != player_id:
        return {"success": False, "message": "自分のターンではありません"}
    if game_state.turn_phase != TurnPhase.MAIN:
        return {"success": False, "message": "メインフェーズ以外では進化できません"}
    if not player.has_active:
        return {"success": False, "message": "バトル場にポケモンがいません"}

    active = player.active_pokemon
    evo_check = _check_evolution_conditions(game_state, active)
    if not evo_check["can_evolve"]:
        return {"success": False, "message": evo_check["reason"]}

    # 手札から進化カードを探す
    evo_card = _find_card_in_hand(player, card_id)
    if evo_card is None:
        return {"success": False, "message": f"手札にカードID={card_id}が見つかりません"}

    # 進化先の段階チェック
    current_stage = active.card.evolution_stage
    expected_next = NEXT_STAGE.get(current_stage)
    if evo_card.evolution_stage != expected_next:
        return {
            "success": False,
            "message": f"{active.card.name}({current_stage})の次の進化は{expected_next}です。{evo_card.name}は{evo_card.evolution_stage}です"
        }

    # 進化元カードをトラッシュへ
    old_card = active.card
    player.discard_pile.append(old_card)

    # エネルギーを引き継ぎ、特殊状態はリセット
    old_energy = active.attached_energy.copy()
    old_damage = active.damage_counters

    # 手札から進化カードを取り出してバトル場へ
    player.hand = [c for c in player.hand if c.id != card_id]
    player.active_pokemon = ActivePokemon(
        card=evo_card,
        damage_counters=old_damage,
        attached_energy=old_energy,
        special_condition=SpecialCondition.NONE,  # 特殊状態リセット
        turns_in_play=0,  # 進化したターンは再度進化不可
    )

    game_state.add_log(
        "EVOLVE_ACTIVE",
        f"{player_id}: {old_card.name} → {evo_card.name}（バトル場）"
    )
    return {"success": True, "message": f"{old_card.name}が{evo_card.name}に進化した"}


def evolve_bench(game_state: GameState, player_id: str, bench_index: int, card_id: int) -> dict:
    """
    ベンチのポケモンを進化させる。

    Args:
        bench_index: ベンチの何番目のポケモンか（0始まり）
        card_id: 手札の進化カードのID
    """
    player = game_state.get_player(player_id)

    if game_state.current_player_id != player_id:
        return {"success": False, "message": "自分のターンではありません"}
    if game_state.turn_phase != TurnPhase.MAIN:
        return {"success": False, "message": "メインフェーズ以外では進化できません"}

    if bench_index < 0 or bench_index >= len(player.bench):
        return {"success": False, "message": f"ベンチインデックス{bench_index}が無効です"}

    bench_mon = player.bench[bench_index]
    evo_check = _check_evolution_conditions(game_state, bench_mon)
    if not evo_check["can_evolve"]:
        return {"success": False, "message": evo_check["reason"]}

    evo_card = _find_card_in_hand(player, card_id)
    if evo_card is None:
        return {"success": False, "message": f"手札にカードID={card_id}が見つかりません"}

    current_stage = bench_mon.card.evolution_stage
    expected_next = NEXT_STAGE.get(current_stage)
    if evo_card.evolution_stage != expected_next:
        return {
            "success": False,
            "message": f"{bench_mon.card.name}({current_stage})の次の進化は{expected_next}です"
        }

    old_card = bench_mon.card
    player.discard_pile.append(old_card)
    old_energy = bench_mon.attached_energy.copy()
    old_damage = bench_mon.damage_counters

    player.hand = [c for c in player.hand if c.id != card_id]
    player.bench[bench_index] = BenchPokemon(
        card=evo_card,
        damage_counters=old_damage,
        attached_energy=old_energy,
        special_condition=SpecialCondition.NONE,
        turns_in_play=0,
    )

    game_state.add_log(
        "EVOLVE_BENCH",
        f"{player_id}: {old_card.name} → {evo_card.name}（ベンチ{bench_index}）"
    )
    return {"success": True, "message": f"{old_card.name}が{evo_card.name}に進化した"}


def _check_evolution_conditions(game_state: GameState, pokemon) -> dict:
    """
    進化可能かどうかをチェックする共通処理。

    進化不可条件:
    - 最初のターン（先行・後攻共に）
    - 場に出した同一ターン内（turns_in_play == 0）
    """
    # ゲーム最初のターン（current_turn == 1）
    if game_state.current_turn == 1:
        return {"can_evolve": False, "reason": "最初のターンは進化できません"}

    # 場に出たターンは進化不可
    if pokemon.turns_in_play == 0:
        return {"can_evolve": False, "reason": f"{pokemon.card.name}は場に出たターンには進化できません"}

    # 2進化以上には進化できない
    if pokemon.card.evolution_stage == "2 進化":
        return {"can_evolve": False, "reason": f"{pokemon.card.name}はすでに最終進化です"}

    return {"can_evolve": True, "reason": ""}


def _find_card_in_hand(player, card_id: int):
    for card in player.hand:
        if card.id == card_id:
            return card
    return None
FILEOF

# ---- backend/engine/actions/faint.py ----
mkdir -p "backend/engine/actions"
cat > 'backend/engine/actions/faint.py' << 'FILEOF'
"""
タスク3-11: きぜつ処理
ポケモンのHP0判定・トラッシュ・サイド取得・バトル場交代を実装する
"""
from engine.models.game_state import GameState
from engine.models.game_enums import GamePhase


def check_and_process_faint(game_state: GameState, attacker_id: str) -> dict:
    """
    攻撃後、相手のバトル場ポケモンがきぜつしているか確認し、処理する。

    Args:
        attacker_id: 攻撃したプレイヤーのID

    Returns:
        {"fainted": bool, "message": str, "prize_taken": int, "game_over": bool}
    """
    opponent = game_state.get_opponent_of(attacker_id)
    attacker = game_state.get_player(attacker_id)

    if not opponent.has_active:
        return {"fainted": False, "message": "", "prize_taken": 0, "game_over": False}

    defender = opponent.active_pokemon

    if not defender.is_fainted:
        return {"fainted": False, "message": "", "prize_taken": 0, "game_over": False}

    # きぜつ処理
    fainted_name = defender.card.name

    # きぜつしたポケモンとエネルギーをトラッシュへ
    opponent.discard_pile.append(defender.card)
    opponent.active_pokemon = None

    game_state.add_log("FAINT", f"{fainted_name}がきぜつした")

    # サイドカードの取得（Phase 3では通常ポケモン = 1枚固定）
    prize_count = _get_prize_count(defender.card)
    prizes_taken = []
    for _ in range(prize_count):
        if attacker.prize_cards:
            prize = attacker.prize_cards.pop(0)
            attacker.hand.append(prize)
            prizes_taken.append(prize.name)

    game_state.add_log(
        "TAKE_PRIZE",
        f"{attacker_id}がサイドを{prize_count}枚取得（残り{attacker.prize_remaining}枚）"
    )

    # 勝利条件チェック（サイド全取得）
    if attacker.prize_remaining == 0:
        game_state.game_phase = GamePhase.GAME_OVER
        game_state.winner_id = attacker_id
        game_state.add_log("GAME_OVER", f"{attacker_id}がサイドを全取得して勝利！")
        return {
            "fainted": True,
            "message": f"{fainted_name}がきぜつ。{attacker_id}がサイドを全取得して勝利！",
            "prize_taken": prize_count,
            "game_over": True,
        }

    # 相手のバトル場が空になった場合（ベンチもなければ勝利）
    if not opponent.has_bench_pokemon:
        game_state.game_phase = GamePhase.GAME_OVER
        game_state.winner_id = attacker_id
        game_state.add_log("GAME_OVER", f"相手のバトル場とベンチが空になり{attacker_id}が勝利！")
        return {
            "fainted": True,
            "message": f"{fainted_name}がきぜつ。相手のポケモンがいなくなり{attacker_id}の勝利！",
            "prize_taken": prize_count,
            "game_over": True,
        }

    return {
        "fainted": True,
        "message": f"{fainted_name}がきぜつ。{attacker_id}がサイドを{prize_count}枚取得",
        "prize_taken": prize_count,
        "game_over": False,
        "need_replacement": True,  # 倒されたプレイヤーはポケモンを選ぶ必要がある
    }


def send_to_active_from_bench(
    game_state: GameState,
    player_id: str,
    bench_index: int,
) -> dict:
    """
    バトル場が空の場合に、ベンチからポケモンをバトル場に出す。
    きぜつ後の強制交代に使用する。

    Args:
        player_id: 操作プレイヤーID
        bench_index: バトル場に出すベンチポケモンのインデックス

    Returns:
        {"success": bool, "message": str}
    """
    from engine.models.player_state import ActivePokemon

    player = game_state.get_player(player_id)

    if player.has_active:
        return {"success": False, "message": "バトル場にすでにポケモンがいます"}

    if bench_index < 0 or bench_index >= len(player.bench):
        return {"success": False, "message": f"ベンチインデックス{bench_index}が無効です"}

    bench_mon = player.bench.pop(bench_index)
    player.active_pokemon = ActivePokemon(
        card=bench_mon.card,
        damage_counters=bench_mon.damage_counters,
        attached_energy=bench_mon.attached_energy.copy(),
        special_condition=bench_mon.special_condition,
        turns_in_play=bench_mon.turns_in_play,
    )

    game_state.add_log(
        "SEND_TO_ACTIVE",
        f"{player_id}: {player.active_pokemon.card.name}をバトル場に出した"
    )
    return {
        "success": True,
        "message": f"{player.active_pokemon.card.name}をバトル場に出した"
    }


def _get_prize_count(card) -> int:
    """
    きぜつしたポケモンのサイド取得枚数を返す。
    Phase 3では全て1枚固定（exやVなどの複数枚取得はPhase 9以降で実装）
    """
    return 1
FILEOF

# ---- backend/engine/actions/place_pokemon.py ----
mkdir -p "backend/engine/actions"
cat > 'backend/engine/actions/place_pokemon.py' << 'FILEOF'
"""
タスク3-5: ポケモンを場に出す処理
バトル場・ベンチへのポケモン配置ルールを実装する
"""
from models.card import PokemonCard
from engine.models.game_state import GameState
from engine.models.player_state import ActivePokemon, BenchPokemon
from engine.models.game_enums import TurnPhase


def place_to_active(game_state: GameState, player_id: str, card_id: int) -> dict:
    """
    手札のたねポケモンをバトル場に出す。
    バトル場が空の場合のみ配置可能（ポケモンがきぜつ後の交代はfaint.pyで処理）。

    Returns:
        {"success": bool, "message": str}
    """
    player = game_state.get_player(player_id)

    # フェーズチェック
    if game_state.turn_phase not in (TurnPhase.MAIN,):
        return {"success": False, "message": "メインフェーズ以外ではポケモンを出せません"}

    # 現在のプレイヤーのターンか
    if game_state.current_player_id != player_id:
        return {"success": False, "message": "自分のターンではありません"}

    # バトル場が空か
    if player.has_active:
        return {"success": False, "message": "バトル場にすでにポケモンがいます"}

    # 手札から対象カードを探す
    card = _find_card_in_hand(player, card_id)
    if card is None:
        return {"success": False, "message": f"手札にカードID={card_id}が見つかりません"}

    # たねポケモンのみ配置可能
    if card.evolution_stage != "たね":
        return {"success": False, "message": f"バトル場にはたねポケモンのみ出せます: {card.name}"}

    # 手札から取り出してバトル場へ
    player.hand = [c for c in player.hand if c.id != card_id]
    player.active_pokemon = ActivePokemon(card=card, turns_in_play=0)

    game_state.add_log("PLACE_ACTIVE", f"{player_id}: {card.name}をバトル場に出した")
    return {"success": True, "message": f"{card.name}をバトル場に出した"}


def place_to_bench(game_state: GameState, player_id: str, card_id: int) -> dict:
    """
    手札のたねポケモンをベンチに出す。
    ベンチは最大5枚まで。

    Returns:
        {"success": bool, "message": str}
    """
    player = game_state.get_player(player_id)

    # フェーズチェック
    if game_state.turn_phase not in (TurnPhase.MAIN,):
        return {"success": False, "message": "メインフェーズ以外ではポケモンを出せません"}

    if game_state.current_player_id != player_id:
        return {"success": False, "message": "自分のターンではありません"}

    # ベンチ満員チェック
    if player.bench_is_full:
        return {"success": False, "message": "ベンチが満員です（最大5枚）"}

    # 手札から対象カードを探す
    card = _find_card_in_hand(player, card_id)
    if card is None:
        return {"success": False, "message": f"手札にカードID={card_id}が見つかりません"}

    # たねポケモンのみ配置可能
    if card.evolution_stage != "たね":
        return {"success": False, "message": f"ベンチにはたねポケモンのみ出せます: {card.name}"}

    # 手札から取り出してベンチへ
    player.hand = [c for c in player.hand if c.id != card_id]
    player.bench.append(BenchPokemon(card=card, turns_in_play=0))

    game_state.add_log("PLACE_BENCH", f"{player_id}: {card.name}をベンチに出した")
    return {"success": True, "message": f"{card.name}をベンチに出した"}


def _find_card_in_hand(player, card_id: int):
    """手札からcard_idに一致するカードを返す（なければNone）"""
    for card in player.hand:
        if card.id == card_id:
            return card
    return None
FILEOF

# ---- backend/engine/actions/retreat.py ----
mkdir -p "backend/engine/actions"
cat > 'backend/engine/actions/retreat.py' << 'FILEOF'
"""
タスク3-8: 逃げる処理
1ターン1回、逃げエネルギーをトラッシュしてバトル場のポケモンをベンチと入れ替える
"""
from engine.models.game_state import GameState
from engine.models.player_state import ActivePokemon
from engine.models.game_enums import TurnPhase, SpecialCondition


def retreat(
    game_state: GameState,
    player_id: str,
    bench_index: int,
    energy_indices: list[int],
) -> dict:
    """
    バトル場のポケモンを逃がし、ベンチのポケモンと入れ替える。

    Args:
        game_state: ゲーム状態
        player_id: 操作プレイヤーID
        bench_index: バトル場に出すベンチポケモンのインデックス（0始まり）
        energy_indices: トラッシュするエネルギーのインデックスリスト（attached_energyのインデックス）

    Returns:
        {"success": bool, "message": str}
    """
    player = game_state.get_player(player_id)

    if game_state.current_player_id != player_id:
        return {"success": False, "message": "自分のターンではありません"}
    if game_state.turn_phase != TurnPhase.MAIN:
        return {"success": False, "message": "メインフェーズ以外では逃げられません"}

    # 1ターン1回制限チェック
    if player.retreated_this_turn:
        return {"success": False, "message": "このターンはすでに逃げています"}

    if not player.has_active:
        return {"success": False, "message": "バトル場にポケモンがいません"}

    active = player.active_pokemon

    # 特殊状態：まひ・ねむりは逃げられない
    if active.special_condition in (SpecialCondition.PARALYZED, SpecialCondition.ASLEEP):
        return {"success": False, "message": f"{active.card.name}は{active.special_condition.value}状態で逃げられません"}

    # 特殊状態：逃げられない
    if active.special_condition == SpecialCondition.CANT_RETREAT:
        return {"success": False, "message": f"{active.card.name}は逃げられない状態です"}

    # ベンチが空なら逃げられない
    if not player.has_bench_pokemon:
        return {"success": False, "message": "ベンチにポケモンがいないため逃げられません"}

    if bench_index < 0 or bench_index >= len(player.bench):
        return {"success": False, "message": f"ベンチインデックス{bench_index}が無効です"}

    # 逃げエネルギーのコストチェック
    retreat_cost = active.card.retreat_cost or 0
    if len(energy_indices) != retreat_cost:
        return {
            "success": False,
            "message": f"{active.card.name}の逃げエネルギーは{retreat_cost}個です。{len(energy_indices)}個指定されました"
        }

    # インデックスの有効性チェック
    for idx in energy_indices:
        if idx < 0 or idx >= len(active.attached_energy):
            return {"success": False, "message": f"エネルギーインデックス{idx}が無効です"}

    # 重複インデックスチェック
    if len(set(energy_indices)) != len(energy_indices):
        return {"success": False, "message": "同じエネルギーを複数回指定することはできません"}

    # エネルギーをトラッシュ（インデックスを降順でソートして後ろから削除）
    old_active_name = active.card.name
    for idx in sorted(energy_indices, reverse=True):
        trashed_energy_type = active.attached_energy.pop(idx)
        # エネルギーカード自体はトラッシュに積む（型を合わせるため簡易的にcard情報を記録）
        # 実際のエネルギーカードオブジェクトは手元にないため、ログのみ記録

    # バトル場とベンチを入れ替え
    bench_mon = player.bench[bench_index]
    new_active = ActivePokemon(
        card=bench_mon.card,
        damage_counters=bench_mon.damage_counters,
        attached_energy=bench_mon.attached_energy.copy(),
        special_condition=bench_mon.special_condition,
        turns_in_play=bench_mon.turns_in_play,
    )

    # 逃げたポケモンをベンチへ（特殊状態はリセット）
    from engine.models.player_state import BenchPokemon
    retreated_bench = BenchPokemon(
        card=active.card,
        damage_counters=active.damage_counters,
        attached_energy=active.attached_energy.copy(),
        special_condition=SpecialCondition.NONE,  # 逃げると特殊状態リセット
        turns_in_play=active.turns_in_play,
    )

    player.bench[bench_index] = retreated_bench
    player.active_pokemon = new_active
    player.retreated_this_turn = True

    game_state.add_log(
        "RETREAT",
        f"{player_id}: {old_active_name}が逃げ、{new_active.card.name}がバトル場に出た"
    )
    return {
        "success": True,
        "message": f"{old_active_name}が逃げ、{new_active.card.name}がバトル場に出た"
    }
FILEOF

# ---- backend/engine/actions/trainer.py ----
mkdir -p "backend/engine/actions"
cat > 'backend/engine/actions/trainer.py' << 'FILEOF'
"""
タスク3-9: トレーナーカード処理
サポート（1ターン1枚）・グッズ（無制限）・スタジアム（1ターン1枚）の使用ルールを実装する
Phase 3ではルール制限のみ実装。実際の効果はPhase 11で拡張。
"""
from engine.models.game_state import GameState, StadiumState
from engine.models.game_enums import TurnPhase


# カードのevolution_stageやtypeでトレーナー種別を判別するための定数
# ※ 実際のカードデータの構造に合わせて適宜調整が必要
TRAINER_CATEGORY_SUPPORTER = "サポート"
TRAINER_CATEGORY_GOODS = "グッズ"
TRAINER_CATEGORY_STADIUM = "スタジアム"


def use_supporter(game_state: GameState, player_id: str, card_id: int) -> dict:
    """
    サポートカードを使用する（1ターン1枚制限）。
    Phase 3では使用制限チェックのみ行い、効果は適用しない。

    Returns:
        {"success": bool, "message": str}
    """
    player = game_state.get_player(player_id)

    if game_state.current_player_id != player_id:
        return {"success": False, "message": "自分のターンではありません"}
    if game_state.turn_phase != TurnPhase.MAIN:
        return {"success": False, "message": "メインフェーズ以外ではサポートを使用できません"}
    if player.supporter_used_this_turn:
        return {"success": False, "message": "このターンはすでにサポートを使用済みです"}

    card = _find_card_in_hand(player, card_id)
    if card is None:
        return {"success": False, "message": f"手札にカードID={card_id}が見つかりません"}

    # 手札から取り出してトラッシュへ
    player.hand = [c for c in player.hand if c.id != card_id]
    player.discard_pile.append(card)
    player.supporter_used_this_turn = True

    game_state.add_log("USE_SUPPORTER", f"{player_id}: {card.name}を使用（効果はPhase 11で実装）")
    return {"success": True, "message": f"{card.name}を使用した（効果はPhase 11で実装）"}


def use_goods(game_state: GameState, player_id: str, card_id: int) -> dict:
    """
    グッズカードを使用する（使用回数制限なし）。
    Phase 3では使用制限チェックのみ行い、効果は適用しない。

    Returns:
        {"success": bool, "message": str}
    """
    player = game_state.get_player(player_id)

    if game_state.current_player_id != player_id:
        return {"success": False, "message": "自分のターンではありません"}
    if game_state.turn_phase != TurnPhase.MAIN:
        return {"success": False, "message": "メインフェーズ以外ではグッズを使用できません"}

    card = _find_card_in_hand(player, card_id)
    if card is None:
        return {"success": False, "message": f"手札にカードID={card_id}が見つかりません"}

    player.hand = [c for c in player.hand if c.id != card_id]
    player.discard_pile.append(card)

    game_state.add_log("USE_GOODS", f"{player_id}: {card.name}を使用（効果はPhase 11で実装）")
    return {"success": True, "message": f"{card.name}を使用した（効果はPhase 11で実装）"}


def use_stadium(game_state: GameState, player_id: str, card_id: int) -> dict:
    """
    スタジアムカードを使用する（1ターン1枚、既存スタジアムはトラッシュ）。

    Returns:
        {"success": bool, "message": str}
    """
    player = game_state.get_player(player_id)

    if game_state.current_player_id != player_id:
        return {"success": False, "message": "自分のターンではありません"}
    if game_state.turn_phase != TurnPhase.MAIN:
        return {"success": False, "message": "メインフェーズ以外ではスタジアムを使用できません"}

    card = _find_card_in_hand(player, card_id)
    if card is None:
        return {"success": False, "message": f"手札にカードID={card_id}が見つかりません"}

    # 既存のスタジアムがあればトラッシュ
    old_stadium_name = None
    if game_state.stadium is not None:
        old_card = game_state.stadium.card
        old_stadium_name = old_card.name
        # スタジアムを置いたプレイヤーのトラッシュへ
        old_owner = game_state.get_player(game_state.stadium.played_by)
        old_owner.discard_pile.append(old_card)

    # 新しいスタジアムを場に出す
    player.hand = [c for c in player.hand if c.id != card_id]
    game_state.stadium = StadiumState(card=card, played_by=player_id)

    detail = f"{player_id}: {card.name}をスタジアムに設置"
    if old_stadium_name:
        detail += f"（{old_stadium_name}をトラッシュ）"

    game_state.add_log("USE_STADIUM", detail)
    return {"success": True, "message": detail}


def _find_card_in_hand(player, card_id: int):
    for card in player.hand:
        if card.id == card_id:
            return card
    return None
FILEOF

# ---- backend/engine/demo.py ----
mkdir -p "backend/engine"
cat > 'backend/engine/demo.py' << 'FILEOF'
"""
フェーズ3 動作確認スクリプト
Pythonのみで1試合の流れをCLIシミュレーションする
実行方法: backend/ ディレクトリで python -m engine.demo
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.card import PokemonCard, Attack, Weakness, Resistance
from engine.setup.game_setup import setup_game, place_initial_pokemon, start_game
from engine.turn.turn_manager import begin_turn, end_turn
from engine.actions.attach_energy import attach_energy
from engine.actions.attack import declare_attack
from engine.actions.faint import send_to_active_from_bench
from engine.models.game_enums import GamePhase


def make_pikachu(card_id: int) -> PokemonCard:
    return PokemonCard(
        id=card_id, name="ピカチュウ", hp=70, type="雷",
        evolution_stage="たね",
        attacks=[Attack(name="でんきショック", energy=["雷"], energy_count=1, damage=20, description="コインを1回投げオモテなら、相手のバトルポケモンをマヒにする。")],
        weakness=Weakness(type="闘", value="×2"),
        resistance=None, retreat_cost=1,
    )

def make_energy(card_id: int, energy_type: str) -> PokemonCard:
    return PokemonCard(
        id=card_id, name=f"{energy_type}エネルギー", hp=0, type=energy_type,
        evolution_stage="エネルギー", attacks=[], retreat_cost=0,
    )

def make_deck(base_id: int) -> list:
    """ピカチュウ4枚 + 雷エネルギー56枚の簡易デッキ"""
    deck = []
    for i in range(4):
        deck.append(make_pikachu(base_id + i))
    for i in range(56):
        deck.append(make_energy(base_id + 4 + i, "雷"))
    return deck


def print_status(game_state):
    p1 = game_state.player1
    p2 = game_state.player2
    print(f"\n{'='*55}")
    print(f"ターン{game_state.current_turn} / 現在: {game_state.current_player_id}")
    print(f"  P1 バトル場: {p1.active_pokemon.card.name if p1.active_pokemon else 'なし'}"
          f"  HP:{p1.active_pokemon.current_hp if p1.active_pokemon else '-'}"
          f"  エネ:{p1.active_pokemon.attached_energy if p1.active_pokemon else []}"
          f"  サイド残:{p1.prize_remaining}")
    print(f"  P2 バトル場: {p2.active_pokemon.card.name if p2.active_pokemon else 'なし'}"
          f"  HP:{p2.active_pokemon.current_hp if p2.active_pokemon else '-'}"
          f"  エネ:{p2.active_pokemon.attached_energy if p2.active_pokemon else []}"
          f"  サイド残:{p2.prize_remaining}")
    print(f"{'='*55}")


def run():
    print("🎴 フェーズ3 ゲームエンジン 動作確認\n")

    # デッキ作成
    p1_deck = make_deck(base_id=1000)
    p2_deck = make_deck(base_id=2000)

    # セットアップ
    game = setup_game(p1_deck, p2_deck)
    print(f"先行: {game.first_player_id}")
    print(f"P1手札: {[c.name for c in game.player1.hand]}")
    print(f"P2手札: {[c.name for c in game.player2.hand]}")

    # 初期ポケモンを配置（手札の最初のたねポケモンを選ぶ）
    def pick_basic(player):
        return next((c for c in player.hand if c.evolution_stage == "たね"), None)

    p1_active = pick_basic(game.player1)
    p2_active = pick_basic(game.player2)
    place_initial_pokemon(game, "player1", p1_active, [])
    place_initial_pokemon(game, "player2", p2_active, [])
    start_game(game)
    print(f"\nゲームスタート！")
    print_status(game)

    # ゲームループ（最大20ターン）
    for _ in range(20):
        if game.is_game_over:
            break

        pid = game.current_player_id
        player = game.current_player
        opponent = game.opponent

        # ターン開始（ドロー）
        result = begin_turn(game)
        print(f"\n[{pid}] {result['message']}")
        if not result["success"]:
            break

        # エネルギーカードを手札から探して付与
        energy_card = next(
            (c for c in player.hand if c.evolution_stage == "エネルギー"), None
        )
        if energy_card and player.active_pokemon:
            r = attach_energy(game, pid, energy_card.id, "active")
            print(f"[{pid}] {r['message']}")

        # 攻撃できるか試みる
        if player.active_pokemon and opponent.active_pokemon and not game.is_first_turn:
            r = declare_attack(game, pid, attack_index=0)
            print(f"[{pid}] {r['message']}")

            # きぜつが発生し相手がベンチを持っていれば交代
            if r.get("fainted") and not game.is_game_over:
                if opponent.has_bench_pokemon:
                    rep = send_to_active_from_bench(game, opponent.player_id, 0)
                    print(f"[{opponent.player_id}] {rep['message']}")
                else:
                    print(f"[{opponent.player_id}] ベンチにポケモンがいないため交代不可")

        if game.is_game_over:
            break

        print_status(game)

        # ターン終了
        end_result = end_turn(game)
        if end_result["game_over"]:
            print(f"\n🏆 {end_result['message']}")
            break

    if game.is_game_over:
        print(f"\n🏆 ゲーム終了！勝者: {game.winner_id}")
    else:
        print("\n最大ターン数に達しました")

    print(f"\n--- ゲームログ（直近10件）---")
    for log in game.logs[-10:]:
        print(f"  T{log.turn} [{log.player_id}] {log.action}: {log.detail}")


if __name__ == "__main__":
    run()
FILEOF

# ---- backend/engine/demo_cpu.py ----
mkdir -p "backend/engine"
cat > 'backend/engine/demo_cpu.py' << 'FILEOF'
"""
タスク4-4: CPU対戦動作確認スクリプト
プレイヤー1（人間側を自動化）vs CPU（player2）で1試合を完走させる
実行方法: backend/ ディレクトリで python -m engine.demo_cpu
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.card import PokemonCard, Attack, Weakness
from engine.setup.game_setup import setup_game, place_initial_pokemon, start_game
from engine.turn.turn_manager import begin_turn, end_turn
from engine.actions.attach_energy import attach_energy
from engine.actions.attack import declare_attack, _check_energy_cost
from engine.actions.faint import send_to_active_from_bench
from cpu.cpu_ai import cpu_take_turn, cpu_choose_active_after_faint
from engine.models.game_enums import TurnPhase


def make_pikachu(card_id):
    return PokemonCard(
        id=card_id, name="ピカチュウ", hp=70, type="雷",
        evolution_stage="たね",
        attacks=[Attack(name="でんきショック", energy=["雷"], energy_count=1, damage=20, description="")],
        weakness=Weakness(type="闘", value="×2"),
        resistance=None, retreat_cost=1,
    )

def make_hitokage(card_id):
    return PokemonCard(
        id=card_id, name="ヒトカゲ", hp=60, type="炎",
        evolution_stage="たね",
        attacks=[Attack(name="ひっかく", energy=["無色"], energy_count=1, damage=10, description=""),
                 Attack(name="かえんほうしゃ", energy=["炎", "炎"], energy_count=2, damage=40, description="")],
        weakness=Weakness(type="水", value="×2"),
        resistance=None, retreat_cost=1,
    )

def make_energy(card_id, etype):
    return PokemonCard(
        id=card_id, name=f"{etype}エネルギー", hp=0, type=etype,
        evolution_stage="エネルギー", attacks=[], retreat_cost=0,
    )

def make_deck(base_id, pokemon_maker, etype):
    deck = []
    for i in range(4):
        deck.append(pokemon_maker(base_id + i))
    for i in range(56):
        deck.append(make_energy(base_id + 4 + i, etype))
    return deck


def player_auto_action(game_state):
    """プレイヤー1の行動を自動化（CPU同様の簡易ルールベース）"""
    pid = "player1"
    player = game_state.get_player(pid)

    # バトル場が空なら補充
    if not player.has_active and player.has_bench_pokemon:
        best = max(range(len(player.bench)), key=lambda i: player.bench[i].current_hp)
        send_to_active_from_bench(game_state, pid, best)

    # エネルギー付与
    if not player.energy_attached_this_turn and player.has_active:
        energy_card = next((c for c in player.hand if c.evolution_stage == "エネルギー"), None)
        if energy_card:
            attach_energy(game_state, pid, energy_card.id, "active")

    # 攻撃
    if not game_state.is_first_turn and player.has_active and game_state.opponent.has_active:
        active = player.active_pokemon
        for i, atk in enumerate(active.card.attacks):
            if _check_energy_cost(active.attached_energy, atk.energy)["ok"]:
                result = declare_attack(game_state, pid, i)
                if result["success"] and result.get("fainted") and not game_state.is_game_over:
                    # 相手（CPU）がきぜつ→CPU側が自動交代
                    opp = game_state.opponent
                    if not opp.has_active and opp.has_bench_pokemon:
                        cpu_choose_active_after_faint(game_state)
                break


def print_status(game_state):
    p1, p2 = game_state.player1, game_state.player2
    print(f"\n{'─'*60}")
    print(f"  ターン{game_state.current_turn}  現在: {game_state.current_player_id}")
    for label, ps in [("P1(人間)", p1), ("P2(CPU )", p2)]:
        act = ps.active_pokemon
        print(f"  {label} | バトル: {act.card.name if act else 'なし'}"
              f"  HP:{act.current_hp if act else '-'}"
              f"  エネ:{act.attached_energy if act else []}"
              f" | サイド残:{ps.prize_remaining}  山札:{ps.deck_count}")
    print(f"{'─'*60}")


def run():
    print("=" * 60)
    print("  フェーズ4 CPU対戦 動作確認")
    print("=" * 60)

    p1_deck = make_deck(1000, make_pikachu, "雷")
    p2_deck = make_deck(2000, make_hitokage, "炎")

    game = setup_game(p1_deck, p2_deck)
    print(f"先行: {game.first_player_id}")

    # 初期配置
    def pick_basic(player):
        return next(c for c in player.hand if c.evolution_stage == "たね")

    place_initial_pokemon(game, "player1", pick_basic(game.player1), [])
    place_initial_pokemon(game, "player2", pick_basic(game.player2), [])
    start_game(game)
    print("ゲームスタート！")
    print_status(game)

    MAX_TURNS = 40
    for turn_num in range(1, MAX_TURNS + 1):
        if game.is_game_over:
            break

        pid = game.current_player_id

        if pid == "player1":
            # プレイヤー1ターン（自動化）
            draw = begin_turn(game)
            print(f"\n[P1] {draw['message']}")
            if not draw["success"] or game.is_game_over:
                break

            player_auto_action(game)
            print_status(game)
            if game.is_game_over:
                break

            result = end_turn(game)
            if result["game_over"]:
                print(f"\n🏆 {result['message']}")
                break

        else:
            # CPUターン
            print(f"\n[CPU] ターン{game.current_turn} 開始")
            actions = cpu_take_turn(game)
            for a in actions:
                if a.get("message"):
                    print(f"  [CPU] {a['message']}")

            # CPUのポケモンがきぜつしていたら自動交代
            p2 = game.player2
            if not p2.has_active and p2.has_bench_pokemon and not game.is_game_over:
                rep = cpu_choose_active_after_faint(game)
                print(f"  [CPU] {rep['message']}")

            print_status(game)
            if game.is_game_over:
                break

    if game.is_game_over:
        print(f"\n🏆 ゲーム終了！ 勝者: {game.winner_id}")
    else:
        print(f"\n最大ターン数({MAX_TURNS})に到達。引き分け扱い。")

    print(f"\n--- 最終ログ（直近10件）---")
    for log in game.logs[-10:]:
        print(f"  T{log.turn} [{log.player_id}] {log.action}: {log.detail}")


if __name__ == "__main__":
    run()
FILEOF

# ---- backend/engine/models/game_enums.py ----
mkdir -p "backend/engine/models"
cat > 'backend/engine/models/game_enums.py' << 'FILEOF'
"""
ゲームエンジン共通Enum定義
"""
from enum import Enum


class EvolutionStage(str, Enum):
    """進化段階"""
    BASIC = "たね"
    STAGE1 = "1 進化"
    STAGE2 = "2 進化"


class GamePhase(str, Enum):
    """ゲームフェーズ"""
    SETUP = "setup"          # 対戦前準備
    PLAYER1_TURN = "player1_turn"
    PLAYER2_TURN = "player2_turn"
    GAME_OVER = "game_over"


class TurnPhase(str, Enum):
    """ターン内フェーズ"""
    DRAW = "draw"            # ドローフェーズ
    MAIN = "main"            # メインフェーズ（ポケモン配置・エネルギー・トレーナー等）
    ATTACK = "attack"        # 攻撃宣言済み
    END = "end"              # ターン終了


class SpecialCondition(str, Enum):
    """特殊状態（Phase 9以降で実装）"""
    NONE = "none"
    POISONED = "poisoned"        # どく
    BURNED = "burned"            # やけど
    CONFUSED = "confused"        # こんらん
    PARALYZED = "paralyzed"      # まひ
    ASLEEP = "asleep"            # ねむり
    CANT_RETREAT = "cant_retreat"  # 逃げられない


class Zone(str, Enum):
    """ポケモンのゾーン"""
    DECK = "deck"
    HAND = "hand"
    ACTIVE = "active"      # バトル場
    BENCH = "bench"        # ベンチ
    DISCARD = "discard"    # トラッシュ
    PRIZE = "prize"        # サイド


class DamageType(str, Enum):
    """攻撃のダメージ種別"""
    NORMAL = "normal"          # 通常ダメージ（弱点・抵抗力計算あり）
    COUNTER = "counter"        # ダメージカウンター型（計算なし）
FILEOF

# ---- backend/engine/models/game_state.py ----
mkdir -p "backend/engine/models"
cat > 'backend/engine/models/game_state.py' << 'FILEOF'
"""
ゲーム状態モデル
対戦全体の状態を管理する（メモリ上のみ、DBには保存しない）
"""
import uuid
from dataclasses import dataclass, field
from typing import Optional, List
from engine.models.player_state import PlayerState
from engine.models.game_enums import GamePhase, TurnPhase
from models.card import PokemonCard


@dataclass
class StadiumState:
    """場に出ているスタジアムカードの状態"""
    card: PokemonCard
    played_by: str  # "player1" or "player2"


@dataclass
class GameLog:
    """ゲームログの1エントリ"""
    turn: int
    player_id: str
    action: str
    detail: str = ""


@dataclass
class GameState:
    """
    ゲーム全体の状態を管理するクラス

    Attributes:
        game_id: ゲームの一意ID
        player1: プレイヤー1の状態
        player2: プレイヤー2の状態
        current_turn: 現在のターン数（1始まり）
        current_player_id: 現在のターンのプレイヤーID
        first_player_id: 先行プレイヤーのID
        game_phase: ゲーム全体のフェーズ
        turn_phase: ターン内のフェーズ
        winner_id: 勝者のプレイヤーID（ゲーム終了時にセット）
        stadium: 現在場に出ているスタジアムカード
        logs: ゲームログ
        attacked_this_turn: このターンに攻撃宣言したか
    """
    player1: PlayerState
    player2: PlayerState
    game_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    current_turn: int = 1
    current_player_id: str = "player1"
    first_player_id: str = "player1"
    game_phase: GamePhase = GamePhase.SETUP
    turn_phase: TurnPhase = TurnPhase.DRAW
    winner_id: Optional[str] = None
    stadium: Optional[StadiumState] = None
    logs: List[GameLog] = field(default_factory=list)
    attacked_this_turn: bool = False

    @property
    def current_player(self) -> PlayerState:
        """現在のターンのプレイヤー"""
        return self.player1 if self.current_player_id == "player1" else self.player2

    @property
    def opponent(self) -> PlayerState:
        """現在のターンの相手プレイヤー"""
        return self.player2 if self.current_player_id == "player1" else self.player1

    @property
    def is_game_over(self) -> bool:
        """ゲームが終了しているか"""
        return self.game_phase == GamePhase.GAME_OVER

    @property
    def is_first_turn(self) -> bool:
        """先行プレイヤーの最初のターンか（攻撃禁止判定用）"""
        return self.current_turn == 1 and self.current_player_id == self.first_player_id

    def get_player(self, player_id: str) -> PlayerState:
        """player_idでPlayerStateを取得"""
        if player_id == "player1":
            return self.player1
        elif player_id == "player2":
            return self.player2
        raise ValueError(f"不明なプレイヤーID: {player_id}")

    def get_opponent_of(self, player_id: str) -> PlayerState:
        """指定プレイヤーの相手を取得"""
        return self.player2 if player_id == "player1" else self.player1

    def add_log(self, action: str, detail: str = ""):
        """ゲームログを追加"""
        log = GameLog(
            turn=self.current_turn,
            player_id=self.current_player_id,
            action=action,
            detail=detail
        )
        self.logs.append(log)

    def switch_turn(self):
        """ターンを相手プレイヤーに移行"""
        # 現在のプレイヤーの場のポケモンのturns_in_playをインクリメント
        self.current_player.increment_turns_in_play()

        # プレイヤー切り替え
        self.current_player_id = (
            "player2" if self.current_player_id == "player1" else "player1"
        )
        self.current_turn += 1
        self.turn_phase = TurnPhase.DRAW
        self.attacked_this_turn = False

        # 次のプレイヤーのターンフラグをリセット
        self.current_player.reset_turn_flags()

    def to_dict(self) -> dict:
        """ゲーム状態をAPI応答用の辞書形式に変換"""
        def pokemon_to_dict(p):
            if p is None:
                return None
            return {
                "card_id": p.card.id,
                "name": p.card.name,
                "hp": p.card.hp,
                "current_hp": p.current_hp,
                "damage_counters": p.damage_counters,
                "attached_energy": p.attached_energy,
                "special_condition": p.special_condition.value,
                "turns_in_play": p.turns_in_play,
                "evolution_stage": p.card.evolution_stage,
                "type": p.card.type,
                "attacks": [
                    {
                        "name": a.name,
                        "energy": a.energy,
                        "energy_count": a.energy_count,
                        "damage": a.damage,
                        "description": a.description,
                    }
                    for a in p.card.attacks
                ],
                "retreat_cost": p.card.retreat_cost,
                "weakness": {"type": p.card.weakness.type, "value": p.card.weakness.value} if p.card.weakness else None,
                "resistance": {"type": p.card.resistance.type, "value": p.card.resistance.value} if p.card.resistance else None,
            }

        def player_to_dict(ps: PlayerState):
            return {
                "player_id": ps.player_id,
                "deck_count": ps.deck_count,
                "hand_count": len(ps.hand),
                "hand": [{"card_id": c.id, "name": c.name, "evolution_stage": c.evolution_stage, "type": c.type} for c in ps.hand],
                "active_pokemon": pokemon_to_dict(ps.active_pokemon),
                "bench": [pokemon_to_dict(b) for b in ps.bench],
                "prize_remaining": ps.prize_remaining,
                "discard_count": len(ps.discard_pile),
                "energy_attached_this_turn": ps.energy_attached_this_turn,
                "supporter_used_this_turn": ps.supporter_used_this_turn,
                "retreated_this_turn": ps.retreated_this_turn,
            }

        return {
            "game_id": self.game_id,
            "current_turn": self.current_turn,
            "current_player_id": self.current_player_id,
            "first_player_id": self.first_player_id,
            "game_phase": self.game_phase.value,
            "turn_phase": self.turn_phase.value,
            "winner_id": self.winner_id,
            "is_first_turn": self.is_first_turn,
            "attacked_this_turn": self.attacked_this_turn,
            "stadium": {
                "card_id": self.stadium.card.id,
                "name": self.stadium.card.name,
                "played_by": self.stadium.played_by,
            } if self.stadium else None,
            "player1": player_to_dict(self.player1),
            "player2": player_to_dict(self.player2),
            "logs": [
                {"turn": l.turn, "player_id": l.player_id, "action": l.action, "detail": l.detail}
                for l in self.logs[-20:]  # 直近20件のみ返す
            ],
        }
FILEOF

# ---- backend/engine/models/player_state.py ----
mkdir -p "backend/engine/models"
cat > 'backend/engine/models/player_state.py' << 'FILEOF'
"""
プレイヤー状態モデル
対戦中の各プレイヤーの状態を管理する
"""
from dataclasses import dataclass, field
from typing import List, Optional
from models.card import PokemonCard
from engine.models.game_enums import SpecialCondition


@dataclass
class ActivePokemon:
    """
    バトル場に出ているポケモンの状態
    カード情報に加え、ゲーム中の状態（HPダメージ、エネルギー、特殊状態）を持つ
    """
    card: PokemonCard
    damage_counters: int = 0          # 受けているダメージカウンター数（10ダメージ = 1カウンター）
    attached_energy: List[str] = field(default_factory=list)  # 付与されているエネルギータイプのリスト
    special_condition: SpecialCondition = SpecialCondition.NONE
    turns_in_play: int = 0            # 場に出てから経過したターン数（進化制限判定用）

    @property
    def current_hp(self) -> int:
        """現在のHP（最大HP - 受けたダメージ）"""
        base_hp = self.card.hp or 0
        return base_hp - (self.damage_counters * 10)

    @property
    def is_fainted(self) -> bool:
        """きぜつしているか"""
        return self.current_hp <= 0

    @property
    def energy_count(self) -> int:
        """付与されているエネルギーの総数"""
        return len(self.attached_energy)


@dataclass
class BenchPokemon:
    """
    ベンチに出ているポケモンの状態
    """
    card: PokemonCard
    damage_counters: int = 0
    attached_energy: List[str] = field(default_factory=list)
    special_condition: SpecialCondition = SpecialCondition.NONE
    turns_in_play: int = 0

    @property
    def current_hp(self) -> int:
        base_hp = self.card.hp or 0
        return base_hp - (self.damage_counters * 10)

    @property
    def is_fainted(self) -> bool:
        return self.current_hp <= 0

    @property
    def energy_count(self) -> int:
        return len(self.attached_energy)


@dataclass
class PlayerState:
    """
    プレイヤーの対戦状態全体を管理するクラス

    Attributes:
        player_id: プレイヤー識別子（"player1" or "player2"）
        deck: 山札（残りのカードリスト）
        hand: 手札
        active_pokemon: バトル場のポケモン（Noneの場合はバトル場が空）
        bench: ベンチのポケモンリスト（最大5枚）
        prize_cards: サイドカード（残り枚数）
        discard_pile: トラッシュ
        energy_attached_this_turn: このターンにエネルギーを付与したか
        supporter_used_this_turn: このターンにサポートを使用したか
        retreated_this_turn: このターンに逃げたか
        mulligans: このプレイヤーがマリガンした回数
    """
    player_id: str
    deck: List[PokemonCard] = field(default_factory=list)
    hand: List[PokemonCard] = field(default_factory=list)
    active_pokemon: Optional[ActivePokemon] = None
    bench: List[BenchPokemon] = field(default_factory=list)
    prize_cards: List[PokemonCard] = field(default_factory=list)
    discard_pile: List[PokemonCard] = field(default_factory=list)
    energy_attached_this_turn: bool = False
    supporter_used_this_turn: bool = False
    retreated_this_turn: bool = False
    mulligans: int = 0

    @property
    def has_active(self) -> bool:
        """バトル場にポケモンがいるか"""
        return self.active_pokemon is not None

    @property
    def bench_count(self) -> int:
        """ベンチのポケモン数"""
        return len(self.bench)

    @property
    def bench_is_full(self) -> bool:
        """ベンチが満員（5枚）か"""
        return self.bench_count >= 5

    @property
    def prize_remaining(self) -> int:
        """残りサイドカード枚数"""
        return len(self.prize_cards)

    @property
    def deck_count(self) -> int:
        """山札の残り枚数"""
        return len(self.deck)

    @property
    def has_basic_in_hand(self) -> bool:
        """手札にたねポケモンがあるか（マリガン判定用）"""
        return any(c.evolution_stage == "たね" for c in self.hand)

    @property
    def has_bench_pokemon(self) -> bool:
        """ベンチにポケモンがいるか"""
        return len(self.bench) > 0

    def reset_turn_flags(self):
        """ターン開始時にターン制限フラグをリセット"""
        self.energy_attached_this_turn = False
        self.supporter_used_this_turn = False
        self.retreated_this_turn = False

    def increment_turns_in_play(self):
        """場に出ている全ポケモンのturns_in_playをインクリメント（ターン終了時）"""
        if self.active_pokemon:
            self.active_pokemon.turns_in_play += 1
        for bench_mon in self.bench:
            bench_mon.turns_in_play += 1
FILEOF

# ---- backend/engine/setup/game_setup.py ----
mkdir -p "backend/engine/setup"
cat > 'backend/engine/setup/game_setup.py' << 'FILEOF'
"""
タスク3-2: ゲームセットアップ処理
対戦前の準備（シャッフル・初期手札・マリガン・サイドカード・先攻後攻決定）を行う
"""
import random
from typing import List, Tuple
from models.card import PokemonCard
from engine.models.player_state import PlayerState, ActivePokemon, BenchPokemon
from engine.models.game_state import GameState
from engine.models.game_enums import GamePhase, TurnPhase


def shuffle_deck(deck: List[PokemonCard]) -> List[PokemonCard]:
    """山札をシャッフルして返す"""
    shuffled = deck.copy()
    random.shuffle(shuffled)
    return shuffled


def draw_cards(player: PlayerState, count: int) -> List[PokemonCard]:
    """
    山札からcount枚引いて手札に加える。
    山札が足りない場合は引ける分だけ引く。
    Returns: 引いたカードリスト
    """
    drawn = player.deck[:count]
    player.deck = player.deck[count:]
    player.hand.extend(drawn)
    return drawn


def has_basic_pokemon(cards: List[PokemonCard]) -> bool:
    """カードリストにたねポケモンが含まれるか"""
    return any(c.evolution_stage == "たね" for c in cards)


def do_mulligan(player: PlayerState) -> int:
    """
    マリガン処理。
    手札をデッキに戻してシャッフルし、7枚引き直す。
    たねポケモンが引けるまで繰り返す。
    Returns: マリガンした回数
    """
    mulligan_count = 0
    while not has_basic_pokemon(player.hand):
        # 手札を山札に戻してシャッフル
        player.deck.extend(player.hand)
        player.hand = []
        player.deck = shuffle_deck(player.deck)
        draw_cards(player, 7)
        mulligan_count += 1

    player.mulligans = mulligan_count
    return mulligan_count


def set_prize_cards(player: PlayerState, count: int = 6):
    """山札からサイドカードをcount枚セットする"""
    prizes = player.deck[:count]
    player.deck = player.deck[count:]
    player.prize_cards = prizes


def decide_first_player(player1_id: str = "player1", player2_id: str = "player2") -> str:
    """コイントスで先行プレイヤーをランダムに決定"""
    return random.choice([player1_id, player2_id])


def setup_game(
    player1_deck: List[PokemonCard],
    player2_deck: List[PokemonCard],
) -> GameState:
    """
    対戦前の準備を一括して行いGameStateを返す。

    ルール順（game-rules.mdに準拠）:
    1. 先行・後攻決定（コイントス）
    2. 両プレイヤーの山札シャッフル・7枚ドロー
    3. マリガン処理（たねポケモンがいない場合）
    4. サイドカード6枚セット
    5. マリガン分の追加ドロー（サイドカードを置いた後）
    6. ゲームスタート待機状態に設定

    Args:
        player1_deck: プレイヤー1のデッキ（60枚）
        player2_deck: プレイヤー2のデッキ（60枚）

    Returns:
        初期化済みのGameState（game_phase=SETUP、表向きにする前の状態）
    """
    # PlayerState初期化
    player1 = PlayerState(player_id="player1")
    player2 = PlayerState(player_id="player2")

    # 手順1: 先行・後攻決定
    first_player_id = decide_first_player()

    # 手順2: 山札シャッフル・7枚ドロー
    player1.deck = shuffle_deck(player1_deck)
    player2.deck = shuffle_deck(player2_deck)
    draw_cards(player1, 7)
    draw_cards(player2, 7)

    # 手順3: マリガン処理
    p1_mulligans = do_mulligan(player1)
    p2_mulligans = do_mulligan(player2)

    # 手順4: サイドカードを6枚セット
    set_prize_cards(player1)
    set_prize_cards(player2)

    # 手順5: マリガン分の追加ドロー（サイドカードを置いた後）
    # ※ 実際に引くかどうかはプレイヤーの選択だが、CPU対戦では自動的に引く
    if p2_mulligans > 0:
        draw_cards(player1, p2_mulligans)
    if p1_mulligans > 0:
        draw_cards(player2, p1_mulligans)

    # GameState生成
    game_state = GameState(
        player1=player1,
        player2=player2,
        current_player_id=first_player_id,
        first_player_id=first_player_id,
        game_phase=GamePhase.SETUP,
        turn_phase=TurnPhase.DRAW,
    )

    game_state.add_log(
        "SETUP",
        f"先行: {first_player_id} / P1マリガン: {p1_mulligans}回 / P2マリガン: {p2_mulligans}回"
    )

    return game_state


def place_initial_pokemon(
    game_state: GameState,
    player_id: str,
    active_card: PokemonCard,
    bench_cards: List[PokemonCard],
) -> None:
    """
    初期ポケモンをバトル場・ベンチに配置する（セットアップフェーズ用）。
    配置するカードは手札から取り出す。

    Args:
        game_state: 現在のゲーム状態
        player_id: 配置するプレイヤーのID
        active_card: バトル場に出すたねポケモン
        bench_cards: ベンチに出すたねポケモンのリスト（0〜5枚）

    Raises:
        ValueError: たねポケモン以外を配置しようとした場合 / ベンチが5枚超の場合
    """
    player = game_state.get_player(player_id)

    # バリデーション
    if active_card.evolution_stage != "たね":
        raise ValueError(f"バトル場にはたねポケモンのみ出せます: {active_card.name}")
    if len(bench_cards) > 5:
        raise ValueError("ベンチは最大5枚です")
    for card in bench_cards:
        if card.evolution_stage != "たね":
            raise ValueError(f"ベンチにはたねポケモンのみ出せます: {card.name}")

    # バトル場に配置
    player.hand = [c for c in player.hand if c.id != active_card.id]
    player.active_pokemon = ActivePokemon(card=active_card, turns_in_play=0)

    # ベンチに配置
    bench_ids = {c.id for c in bench_cards}
    player.hand = [c for c in player.hand if c.id not in bench_ids]
    player.bench = [BenchPokemon(card=c, turns_in_play=0) for c in bench_cards]

    game_state.add_log(
        "PLACE_INITIAL",
        f"{player_id}: バトル場={active_card.name}, ベンチ={[c.name for c in bench_cards]}"
    )


def start_game(game_state: GameState) -> None:
    """
    両プレイヤーが初期配置を完了した後、ゲームを開始状態にする。
    (カードを表向きにする＝game_phaseをPLAYERターンに移行)

    Raises:
        ValueError: どちらかのプレイヤーのバトル場が空の場合
    """
    if not game_state.player1.has_active:
        raise ValueError("プレイヤー1のバトル場が空です")
    if not game_state.player2.has_active:
        raise ValueError("プレイヤー2のバトル場が空です")

    # 先行プレイヤーに合わせてフェーズを設定
    if game_state.first_player_id == "player1":
        game_state.game_phase = GamePhase.PLAYER1_TURN
    else:
        game_state.game_phase = GamePhase.PLAYER2_TURN

    game_state.turn_phase = TurnPhase.DRAW
    game_state.add_log("START", "ゲーム開始！カードを表向きにする")
FILEOF

# ---- backend/engine/turn/turn_manager.py ----
mkdir -p "backend/engine/turn"
cat > 'backend/engine/turn/turn_manager.py' << 'FILEOF'
"""
タスク3-3: ターン管理
ターン開始・終了・プレイヤー交代を管理する
"""
from engine.models.game_state import GameState
from engine.models.game_enums import TurnPhase, GamePhase
from engine.actions.draw import draw_card
from engine.victory import check_victory


def begin_turn(game_state: GameState) -> dict:
    """
    ターン開始処理。
    1. ターンフラグをリセット
    2. 山札から1枚ドロー（山札切れなら負け）
    3. turn_phaseをMAINに移行

    Returns:
        {"success": bool, "message": str, "drew_card": str | None}
    """
    player = game_state.current_player

    # ターンフラグリセット（switch_turnで既にリセット済みのケースもあるが念のため）
    player.reset_turn_flags()
    game_state.attacked_this_turn = False

    # 山札切れチェック（引く前に判定）
    if player.deck_count == 0:
        game_state.game_phase = GamePhase.GAME_OVER
        opponent = game_state.opponent
        game_state.winner_id = opponent.player_id
        game_state.add_log(
            "DECK_OUT",
            f"{player.player_id}の山札が0枚のためターン開始時にドローできず敗北"
        )
        return {
            "success": False,
            "message": f"{player.player_id}の山札が切れました。{opponent.player_id}の勝利です。",
            "drew_card": None,
        }

    # 1枚ドロー
    result = draw_card(game_state, player.player_id)

    # MAINフェーズへ
    game_state.turn_phase = TurnPhase.MAIN

    drew_name = result.get("card_name", "不明")
    game_state.add_log("TURN_START", f"ターン{game_state.current_turn} {player.player_id} ドロー: {drew_name}")

    return {
        "success": True,
        "message": f"ターン{game_state.current_turn}開始。{drew_name}を引いた。",
        "drew_card": drew_name,
    }


def end_turn(game_state: GameState) -> dict:
    """
    ターン終了処理。
    1. 勝利条件チェック
    2. 次プレイヤーへ交代

    Returns:
        {"success": bool, "message": str, "game_over": bool, "winner_id": str | None}
    """
    # 終了前に勝利条件チェック
    victory = check_victory(game_state)
    if victory["game_over"]:
        game_state.game_phase = GamePhase.GAME_OVER
        game_state.winner_id = victory["winner_id"]
        game_state.add_log("GAME_OVER", f"勝者: {victory['winner_id']} / 理由: {victory['reason']}")
        return {
            "success": True,
            "message": f"ゲーム終了。{victory['winner_id']}の勝利！（{victory['reason']}）",
            "game_over": True,
            "winner_id": victory["winner_id"],
        }

    current_id = game_state.current_player_id
    game_state.add_log("TURN_END", f"ターン{game_state.current_turn} 終了")

    # ターンを切り替え
    game_state.switch_turn()

    # game_phase更新
    if game_state.current_player_id == "player1":
        game_state.game_phase = GamePhase.PLAYER1_TURN
    else:
        game_state.game_phase = GamePhase.PLAYER2_TURN

    return {
        "success": True,
        "message": f"{current_id}のターン終了。{game_state.current_player_id}のターン開始。",
        "game_over": False,
        "winner_id": None,
    }
FILEOF

# ---- backend/engine/victory.py ----
mkdir -p "backend/engine"
cat > 'backend/engine/victory.py' << 'FILEOF'
"""
タスク3-12: 勝利条件チェック
3つの勝利条件をチェックする
"""
from engine.models.game_state import GameState


def check_victory(game_state: GameState) -> dict:
    """
    勝利条件をチェックして結果を返す。

    勝利条件:
    1. 自分のサイドカードを全て取得した
    2. 相手のバトル場が空かつベンチも空
    3. ターン開始時に相手の山札が0枚（begin_turn側でチェック）

    Returns:
        {"game_over": bool, "winner_id": str | None, "reason": str}
    """
    p1 = game_state.player1
    p2 = game_state.player2

    # 条件1: サイドカード全取得
    if p1.prize_remaining == 0:
        return {
            "game_over": True,
            "winner_id": "player1",
            "reason": "player1がサイドカードを全て取得"
        }
    if p2.prize_remaining == 0:
        return {
            "game_over": True,
            "winner_id": "player2",
            "reason": "player2がサイドカードを全て取得"
        }

    # 条件2: 相手のバトル場が空（きぜつ後にベンチも空）
    if not p1.has_active and not p1.has_bench_pokemon:
        return {
            "game_over": True,
            "winner_id": "player2",
            "reason": "player1のバトル場とベンチが空になった"
        }
    if not p2.has_active and not p2.has_bench_pokemon:
        return {
            "game_over": True,
            "winner_id": "player1",
            "reason": "player2のバトル場とベンチが空になった"
        }

    # 条件3: 山札切れはbegin_turn()側でチェックするためここでは判定しない
    return {
        "game_over": False,
        "winner_id": None,
        "reason": ""
    }
FILEOF

# ---- backend/models/card.py ----
mkdir -p "backend/models"
cat > 'backend/models/card.py' << 'FILEOF'
"""
データベースモデル定義
pydanticがある場合はBaseModel、なければdataclassにフォールバック
"""
from typing import Optional, List

try:
    from pydantic import BaseModel
    from datetime import datetime

    class Attack(BaseModel):
        name: str
        energy: List[str]
        energy_count: int
        damage: int
        description: str

    class Weakness(BaseModel):
        type: str
        value: str

    class Resistance(BaseModel):
        type: str
        value: str

    class PokemonCard(BaseModel):
        id: Optional[int] = None
        name: str
        image_url: Optional[str] = None
        list_index: Optional[int] = None
        hp: Optional[int] = None
        type: Optional[str] = None
        evolution_stage: Optional[str] = None
        attacks: List[Attack] = []
        weakness: Optional[Weakness] = None
        resistance: Optional[Resistance] = None
        retreat_cost: Optional[int] = None
        created_at: Optional[datetime] = None
        class Config:
            from_attributes = True

    class CardCreateRequest(BaseModel):
        name: str
        image_url: str
        hp: int
        type: str
        evolution_stage: str
        attacks: List[Attack]
        weakness: Optional[Weakness] = None
        resistance: Optional[Resistance] = None
        retreat_cost: int

    class CardUpdateRequest(BaseModel):
        name: Optional[str] = None
        image_url: Optional[str] = None
        hp: Optional[int] = None
        type: Optional[str] = None
        evolution_stage: Optional[str] = None
        attacks: Optional[List[Attack]] = None
        weakness: Optional[Weakness] = None
        resistance: Optional[Resistance] = None
        retreat_cost: Optional[int] = None

except ImportError:
    from dataclasses import dataclass, field

    @dataclass
    class Attack:
        name: str = ""
        energy: List = field(default_factory=list)
        energy_count: int = 0
        damage: int = 0
        description: str = ""

    @dataclass
    class Weakness:
        type: str = ""
        value: str = ""

    @dataclass
    class Resistance:
        type: str = ""
        value: str = ""

    @dataclass
    class PokemonCard:
        id: Optional[int] = None
        name: str = ""
        image_url: Optional[str] = None
        list_index: Optional[int] = None
        hp: Optional[int] = None
        type: Optional[str] = None
        evolution_stage: Optional[str] = None
        attacks: List = field(default_factory=list)
        weakness: Optional[object] = None
        resistance: Optional[object] = None
        retreat_cost: Optional[int] = None
        created_at: Optional[str] = None

    class CardCreateRequest:
        pass

    class CardUpdateRequest:
        pass
FILEOF

# ---- frontend/src/app/components/card-detail/card-detail.component.html ----
mkdir -p "frontend/src/app/components/card-detail"
cat > 'frontend/src/app/components/card-detail/card-detail.component.html' << 'FILEOF'
<div
  class="modal-overlay"
  *ngIf="isVisible && card"
  (click)="onOverlayClick($event)"
>
  <div class="modal-panel">

    <!-- ヘッダー -->
    <div class="modal-header" [style.background]="getTypeColor(card.type)">
      <div class="header-content">
        <span class="card-category">{{ getCategoryLabel(card.evolution_stage) }}</span>
        <h2 class="card-name">{{ card.name }}</h2>
        <span class="evolution-stage" *ngIf="card.evolution_stage">{{ card.evolution_stage }}</span>
      </div>
      <button class="close-btn" (click)="onClose()" aria-label="閉じる">×</button>
    </div>

    <!-- ボディ -->
    <div class="modal-body">
      <div class="detail-layout">

        <!-- 左カラム：画像 -->
        <div class="image-col">
          <img
            *ngIf="card.image_url"
            [src]="card.image_url"
            [alt]="card.name"
            class="card-image"
            (error)="$any($event.target).style.display='none'"
          />
          <div
            *ngIf="!card.image_url"
            class="image-placeholder"
            [style.background]="getTypeColor(card.type)"
          >
            <span>{{ card.name }}</span>
          </div>
        </div>

        <!-- 右カラム：詳細情報 -->
        <div class="info-col">

          <!-- 基本情報 -->
          <section class="info-section">
            <h3 class="section-title">基本情報</h3>
            <table class="info-table">
              <tr *ngIf="card.type">
                <th>タイプ</th>
                <td>
                  <span class="type-chip" [style.background]="getTypeColor(card.type)">
                    {{ card.type }}
                  </span>
                </td>
              </tr>
              <tr *ngIf="card.hp">
                <th>HP</th>
                <td><span class="hp-value">{{ card.hp }}</span></td>
              </tr>
              <tr *ngIf="card.retreat_cost !== null">
                <th>にげるコスト</th>
                <td>{{ card.retreat_cost }}エネルギー</td>
              </tr>
            </table>
          </section>

          <!-- 弱点・抵抗力 -->
          <section class="info-section" *ngIf="card.weakness || card.resistance">
            <h3 class="section-title">弱点・抵抗力</h3>
            <table class="info-table">
              <tr *ngIf="card.weakness">
                <th>弱点</th>
                <td>
                  <span class="type-chip" [style.background]="getTypeColor(card.weakness.type)">
                    {{ card.weakness.type }}
                  </span>
                  {{ card.weakness.value }}
                </td>
              </tr>
              <tr *ngIf="card.resistance">
                <th>抵抗力</th>
                <td>
                  <span class="type-chip" [style.background]="getTypeColor(card.resistance.type)">
                    {{ card.resistance.type }}
                  </span>
                  {{ card.resistance.value }}
                </td>
              </tr>
            </table>
          </section>

          <!-- ワザ -->
          <section class="info-section" *ngIf="card.attacks.length">
            <h3 class="section-title">ワザ</h3>
            <div class="attack-list">
              <div *ngFor="let attack of card.attacks" class="attack-item">
                <div class="attack-header">
                  <span class="attack-name">{{ attack.name }}</span>
                  <span class="attack-damage" *ngIf="attack.damage">{{ attack.damage }}ダメージ</span>
                </div>
                <div class="attack-cost" *ngIf="attack.energy.length">
                  コスト：{{ formatEnergyCost(attack.energy) }}
                </div>
                <p class="attack-desc" *ngIf="attack.description">{{ attack.description }}</p>
              </div>
            </div>
          </section>

        </div>
      </div>
    </div>

    <!-- フッター -->
    <div class="modal-footer">
      <button class="btn btn-secondary" (click)="onClose()">閉じる</button>
    </div>

  </div>
</div>
FILEOF

# ---- frontend/src/app/components/card-detail/card-detail.component.scss ----
mkdir -p "frontend/src/app/components/card-detail"
cat > 'frontend/src/app/components/card-detail/card-detail.component.scss' << 'FILEOF'
/* オーバーレイ */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 16px;
  animation: fadeIn 0.15s ease;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to   { opacity: 1; }
}

/* モーダルパネル */
.modal-panel {
  background: #fff;
  border-radius: 14px;
  overflow: hidden;
  width: 100%;
  max-width: 640px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  animation: slideUp 0.2s ease;
}

@keyframes slideUp {
  from { transform: translateY(20px); opacity: 0; }
  to   { transform: translateY(0);    opacity: 1; }
}

/* ヘッダー */
.modal-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding: 18px 20px;
  color: #fff;
}

.header-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.card-category {
  font-size: 11px;
  font-weight: 600;
  opacity: 0.85;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.card-name {
  font-size: 22px;
  font-weight: 800;
  margin: 0;
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.25);
}

.evolution-stage {
  font-size: 12px;
  opacity: 0.85;
}

.close-btn {
  background: rgba(255, 255, 255, 0.25);
  border: none;
  color: #fff;
  font-size: 20px;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
  transition: background 0.15s;
  flex-shrink: 0;

  &:hover {
    background: rgba(255, 255, 255, 0.4);
  }
}

/* ボディ */
.modal-body {
  overflow-y: auto;
  flex: 1;
  padding: 20px;
}

.detail-layout {
  display: flex;
  gap: 20px;
}

/* 左：画像 */
.image-col {
  flex-shrink: 0;
  width: 180px;
}

.card-image {
  width: 100%;
  border-radius: 8px;
  display: block;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.image-placeholder {
  width: 100%;
  aspect-ratio: 3 / 4;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-weight: 700;
  font-size: 14px;
  text-align: center;
  padding: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

/* 右：情報 */
.info-col {
  flex: 1;
  min-width: 0;
}

.info-section {
  margin-bottom: 20px;
}

.section-title {
  font-size: 12px;
  font-weight: 700;
  color: #999;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin: 0 0 8px;
  border-bottom: 1px solid #eee;
  padding-bottom: 4px;
}

.info-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;

  th {
    width: 110px;
    color: #888;
    font-weight: 500;
    text-align: left;
    padding: 4px 0;
  }

  td {
    color: #333;
    padding: 4px 0;
  }
}

.type-chip {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
}

.hp-value {
  font-size: 18px;
  font-weight: 800;
  color: #c0392b;
}

/* ワザ */
.attack-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.attack-item {
  background: #f8f8f8;
  border-radius: 8px;
  padding: 10px 12px;
  border-left: 3px solid #ddd;
}

.attack-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 4px;
}

.attack-name {
  font-weight: 700;
  font-size: 14px;
}

.attack-damage {
  font-size: 13px;
  font-weight: 700;
  color: #c0392b;
}

.attack-cost {
  font-size: 12px;
  color: #888;
  margin-bottom: 4px;
}

.attack-desc {
  font-size: 12px;
  color: #555;
  margin: 0;
  line-height: 1.5;
}

/* フッター */
.modal-footer {
  padding: 14px 20px;
  border-top: 1px solid #eee;
  display: flex;
  justify-content: flex-end;
}

.btn {
  padding: 8px 20px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: background 0.15s;
}

.btn-secondary {
  background: #f0f0f0;
  color: #333;

  &:hover {
    background: #e0e0e0;
  }
}

/* レスポンシブ */
@media (max-width: 480px) {
  .detail-layout {
    flex-direction: column;
  }

  .image-col {
    width: 140px;
    margin: 0 auto;
  }
}
FILEOF

# ---- frontend/src/app/components/card-detail/card-detail.component.ts ----
mkdir -p "frontend/src/app/components/card-detail"
cat > 'frontend/src/app/components/card-detail/card-detail.component.ts' << 'FILEOF'
import { Component, Input, Output, EventEmitter, OnChanges } from '@angular/core';
import { CommonModule } from '@angular/common';
import { PokemonCard, getTypeColor, getCardCategoryLabel } from '../../models/card.model';

@Component({
  selector: 'card-detail',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './card-detail.component.html',
  styleUrl: './card-detail.component.scss',
})
export class CardDetailComponent implements OnChanges {
  @Input() card: PokemonCard | null = null;
  @Output() close = new EventEmitter<void>();

  isVisible = false;

  ngOnChanges(): void {
    this.isVisible = !!this.card;
  }

  onClose(): void {
    this.close.emit();
  }

  /** オーバーレイクリックで閉じる */
  onOverlayClick(event: MouseEvent): void {
    if ((event.target as HTMLElement).classList.contains('modal-overlay')) {
      this.onClose();
    }
  }

  getTypeColor(type: string | null): string {
    return getTypeColor(type);
  }

  getCategoryLabel(stage: string | null): string {
    return getCardCategoryLabel(stage);
  }

  /** エネルギーコスト表示用（例: ["炎","炎","無色"] → "炎×2 無色×1"）*/
  formatEnergyCost(energy: string[]): string {
    if (!energy.length) return '0';
    const counts: Record<string, number> = {};
    energy.forEach((e) => { counts[e] = (counts[e] ?? 0) + 1; });
    return Object.entries(counts)
      .map(([type, count]) => (count > 1 ? `${type}×${count}` : type))
      .join(' ');
  }
}
FILEOF

# ---- frontend/src/app/components/card-list/card-list.component.html ----
mkdir -p "frontend/src/app/components/card-list"
cat > 'frontend/src/app/components/card-list/card-list.component.html' << 'FILEOF'
<div class="card-list-container">

  <!-- フィルターバー -->
  <div class="filter-bar">
    <div class="filter-row">
      <input
        type="text"
        class="search-input"
        placeholder="カード名で検索..."
        [(ngModel)]="searchName"
        (ngModelChange)="applyFilter()"
      />

      <select
        class="type-select"
        [(ngModel)]="filterType"
        (ngModelChange)="applyFilter()"
      >
        <option value="">タイプ：すべて</option>
        <option *ngFor="let t of cardTypes" [value]="t">{{ t }}</option>
      </select>

      <button
        *ngIf="searchName || filterType"
        class="btn btn-secondary btn-sm"
        (click)="clearFilters()"
      >
        リセット
      </button>

      <button class="btn btn-secondary btn-sm" (click)="loadCards()">
        再読み込み
      </button>
    </div>

    <p class="result-count" *ngIf="!isLoading">
      {{ filteredCards.length }} 件 / 全 {{ cards.length }} 件
    </p>
  </div>

  <!-- ローディング -->
  <div class="loading" *ngIf="isLoading">
    <p>読み込み中...</p>
  </div>

  <!-- エラー -->
  <div class="error-message" *ngIf="errorMessage && !isLoading">
    <p>{{ errorMessage }}</p>
    <button class="btn btn-secondary btn-sm" (click)="loadCards()">再試行</button>
  </div>

  <!-- カードグリッド -->
  <div class="card-grid" *ngIf="!isLoading && !errorMessage">

    <div
      *ngFor="let card of filteredCards"
      class="card-item"
      (click)="selectCard(card)"
    >
      <!-- カード画像 or プレースホルダー -->
      <div class="card-image-wrap">
        <img
          *ngIf="card.image_url"
          [src]="card.image_url"
          [alt]="card.name"
          class="card-image"
          (error)="$any($event.target).style.display='none'"
        />
        <div
          *ngIf="!card.image_url"
          class="card-image-placeholder"
          [style.background]="getTypeColor(card.type)"
        >
          <span class="placeholder-name">{{ card.name }}</span>
        </div>

        <!-- タイプバッジ -->
        <span
          class="type-badge"
          [style.background]="getTypeColor(card.type)"
        >{{ card.type ?? '—' }}</span>
      </div>

      <!-- カード情報 -->
      <div class="card-info">
        <p class="card-name">{{ card.name }}</p>
        <div class="card-meta">
          <span class="meta-category">{{ getCategoryLabel(card.evolution_stage) }}</span>
          <span class="meta-stage" *ngIf="card.evolution_stage">{{ card.evolution_stage }}</span>
        </div>
        <div class="card-stats" *ngIf="card.hp">
          <span class="hp-label">HP</span>
          <span class="hp-value">{{ card.hp }}</span>
        </div>
        <p class="attacks-label" *ngIf="card.attacks.length">
          {{ getAttackNames(card) }}
        </p>
      </div>
    </div>

    <!-- データなし -->
    <div class="no-data" *ngIf="filteredCards.length === 0">
      <p>カードが見つかりません</p>
    </div>

  </div>
</div>
FILEOF

# ---- frontend/src/app/components/card-list/card-list.component.scss ----
mkdir -p "frontend/src/app/components/card-list"
cat > 'frontend/src/app/components/card-list/card-list.component.scss' << 'FILEOF'
.card-list-container {
  padding: 16px;
}

/* フィルターバー */
.filter-bar {
  margin-bottom: 20px;
}

.filter-row {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: 8px;
}

.search-input {
  flex: 1;
  min-width: 200px;
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 14px;
  outline: none;
  transition: border-color 0.2s;

  &:focus {
    border-color: #666;
  }
}

.type-select {
  padding: 8px 10px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 14px;
  background: #fff;
  cursor: pointer;
  outline: none;

  &:focus {
    border-color: #666;
  }
}

.result-count {
  font-size: 13px;
  color: #888;
  margin: 0;
}

/* ローディング・エラー */
.loading,
.error-message {
  text-align: center;
  padding: 48px;
  color: #888;
}

.error-message {
  color: #c0392b;
}

/* カードグリッド */
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 16px;
}

.card-item {
  border: 1px solid #e0e0e0;
  border-radius: 10px;
  overflow: hidden;
  cursor: pointer;
  background: #fff;
  transition: transform 0.15s, box-shadow 0.15s;

  &:hover {
    transform: translateY(-3px);
    box-shadow: 0 6px 18px rgba(0, 0, 0, 0.12);
  }
}

/* カード画像エリア */
.card-image-wrap {
  position: relative;
  aspect-ratio: 3 / 4;
  background: #f5f5f5;
  overflow: hidden;
}

.card-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.card-image-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 8px;
}

.placeholder-name {
  color: #fff;
  font-weight: 700;
  font-size: 13px;
  text-align: center;
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.4);
  word-break: break-all;
}

.type-badge {
  position: absolute;
  top: 6px;
  right: 6px;
  padding: 2px 8px;
  border-radius: 12px;
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
}

/* カード情報 */
.card-info {
  padding: 8px 10px;
}

.card-name {
  font-size: 14px;
  font-weight: 700;
  margin: 0 0 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.card-meta {
  display: flex;
  gap: 6px;
  margin-bottom: 4px;
  flex-wrap: wrap;
}

.meta-category {
  font-size: 11px;
  color: #fff;
  background: #888;
  padding: 1px 6px;
  border-radius: 10px;
}

.meta-stage {
  font-size: 11px;
  color: #666;
}

.card-stats {
  display: flex;
  align-items: baseline;
  gap: 4px;
  margin-bottom: 3px;
}

.hp-label {
  font-size: 10px;
  color: #999;
  font-weight: 600;
}

.hp-value {
  font-size: 14px;
  font-weight: 700;
  color: #c0392b;
}

.attacks-label {
  font-size: 11px;
  color: #888;
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* データなし */
.no-data {
  grid-column: 1 / -1;
  text-align: center;
  padding: 48px;
  color: #aaa;
}

/* ボタン */
.btn {
  padding: 8px 16px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: background 0.15s;
}

.btn-secondary {
  background: #f0f0f0;
  color: #333;

  &:hover {
    background: #e0e0e0;
  }
}

.btn-sm {
  padding: 6px 12px;
  font-size: 13px;
}
FILEOF

# ---- frontend/src/app/components/card-list/card-list.component.ts ----
mkdir -p "frontend/src/app/components/card-list"
cat > 'frontend/src/app/components/card-list/card-list.component.ts' << 'FILEOF'
import { Component, OnInit, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { CardService } from '../../services/card.service';
import { PokemonCard, getTypeColor, getCardCategoryLabel } from '../../models/card.model';

const CARD_TYPES = ['草', '炎', '水', '雷', '超', '闘', '悪', '鋼', 'ドラゴン', 'フェアリー', '無色'];

@Component({
  selector: 'card-list',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './card-list.component.html',
  styleUrl: './card-list.component.scss',
})
export class CardListComponent implements OnInit {
  @Output() cardSelected = new EventEmitter<PokemonCard>();

  cards: PokemonCard[] = [];
  filteredCards: PokemonCard[] = [];
  isLoading = false;
  errorMessage = '';

  searchName = '';
  filterType = '';

  readonly cardTypes = CARD_TYPES;

  constructor(private cardService: CardService) {}

  ngOnInit(): void {
    this.loadCards();
  }

  loadCards(): void {
    this.isLoading = true;
    this.errorMessage = '';
    this.cardService.getAllCards().subscribe({
      next: (cards) => {
        this.cards = cards;
        this.applyFilter();
        this.isLoading = false;
      },
      error: () => {
        this.errorMessage = 'カードの取得に失敗しました。バックエンドが起動しているか確認してください。';
        this.isLoading = false;
      },
    });
  }

  applyFilter(): void {
    let result = [...this.cards];
    if (this.searchName.trim()) {
      const q = this.searchName.trim().toLowerCase();
      result = result.filter((c) => c.name.toLowerCase().includes(q));
    }
    if (this.filterType) {
      result = result.filter((c) => c.type === this.filterType);
    }
    this.filteredCards = result;
  }

  clearFilters(): void {
    this.searchName = '';
    this.filterType = '';
    this.applyFilter();
  }

  selectCard(card: PokemonCard): void {
    this.cardSelected.emit(card);
  }

  getTypeColor(type: string | null): string {
    return getTypeColor(type);
  }

  getCategoryLabel(stage: string | null): string {
    return getCardCategoryLabel(stage);
  }

  getAttackNames(card: PokemonCard): string {
    if (!card.attacks.length) return '—';
    return card.attacks.map((a) => a.name).join(' / ');
  }
}
FILEOF

# ---- frontend/src/app/components/deck-builder/deck-builder.component.html ----
mkdir -p "frontend/src/app/components/deck-builder"
cat > 'frontend/src/app/components/deck-builder/deck-builder.component.html' << 'FILEOF'
<div class="deck-builder-container">
  <div class="header">
    <h1>デッキ作成</h1>
  </div>

  <!-- エラーメッセージ -->
  @if (errorMessage) {
    <div class="error-banner">{{ errorMessage }}</div>
  }

  <!-- ===== デッキ一覧 ===== -->
  @if (!currentDeck && !isCreatingNewDeck) {
    <div class="deck-list-view">
      <div class="header-actions">
        <h2>保存済みデッキ ({{ savedDecks.length }}個)</h2>
        <button class="btn btn-primary" (click)="startNewDeck()">新しいデッキを作成</button>
      </div>

      @if (savedDecks.length === 0) {
        <div class="empty-message">デッキがまだ作成されていません</div>
      }

      <div class="decks-grid">
        @for (deck of savedDecks; track deck.id) {
          <div class="deck-card">
            <div class="deck-header">
              <h3>{{ deck.name }}</h3>
              <span class="deck-count">{{ deck.total_count }}枚</span>
            </div>
            @if (deck.description) {
              <p class="deck-description">{{ deck.description }}</p>
            }
            <div class="deck-stats">
              <span>ポケモン: {{ getDeckCounts(deck).pokemon }}枚</span>
              <span>トレーナー: {{ getDeckCounts(deck).trainer }}枚</span>
              <span>エネルギー: {{ getDeckCounts(deck).energy }}枚</span>
            </div>
            <div class="deck-actions">
              <button class="btn btn-primary" (click)="editDeck(deck)">編集</button>
              <button class="btn btn-delete" (click)="deleteDeck(deck.id)">削除</button>
            </div>
          </div>
        }
      </div>
    </div>
  }

  <!-- ===== 新規デッキ作成フォーム ===== -->
  @if (isCreatingNewDeck) {
    <div class="new-deck-form">
      <h2>新しいデッキを作成</h2>

      <div class="form-group">
        <label>デッキ名 *</label>
        <input
          type="text"
          class="form-input"
          [(ngModel)]="newDeckName"
          placeholder="例: 電撃デッキ"
        />
      </div>

      <div class="form-group">
        <label>説明（任意）</label>
        <textarea
          class="form-textarea"
          [(ngModel)]="newDeckDescription"
          placeholder="デッキの説明を入力"
          rows="3"
        ></textarea>
      </div>

      <div class="form-actions">
        <button class="btn btn-primary" (click)="createNewDeck()" [disabled]="!newDeckName.trim()">
          作成
        </button>
        <button class="btn btn-secondary" (click)="cancelNewDeck()">キャンセル</button>
      </div>
    </div>
  }

  <!-- ===== デッキ編集画面 ===== -->
  @if (currentDeck) {
    <div class="deck-editor">

      <!-- エディターヘッダー -->
      <div class="editor-header">
        <div class="deck-info">
          <h2>{{ currentDeck.name }}</h2>
          @if (currentDeck.description) {
            <p>{{ currentDeck.description }}</p>
          }
        </div>
        <div class="deck-count-display">
          <span class="count" [class.complete]="getTotalCount() === CONSTRAINTS.TOTAL_CARDS">
            {{ getTotalCount() }} / {{ CONSTRAINTS.TOTAL_CARDS }}枚
          </span>
        </div>
      </div>

      <!-- バリデーションメッセージ -->
      @if (validationMessages.length > 0) {
        <div class="validation-messages">
          <div *ngFor="let msg of validationMessages" class="validation-message">
            ⚠️ {{ msg }}
          </div>
        </div>
      }

      <!-- メインレイアウト -->
      <div class="editor-layout">

        <!-- 左：カードプール（APIから取得） -->
        <div class="card-pool">
          <h3>
            利用可能なカード
            @if (isLoading) { <span class="loading-inline">読み込み中...</span> }
            @else { <span class="pool-count">({{ filteredCards.length }}件)</span> }
          </h3>

          <!-- フィルター -->
          <div class="filters">
            <div class="filter-buttons">
              <button class="filter-btn" [class.active]="filterType === 'ALL'"     (click)="filterType = 'ALL'">すべて</button>
              <button class="filter-btn" [class.active]="filterType === 'POKEMON'" (click)="filterType = 'POKEMON'">ポケモン</button>
              <button class="filter-btn" [class.active]="filterType === 'TRAINER'" (click)="filterType = 'TRAINER'">トレーナー</button>
              <button class="filter-btn" [class.active]="filterType === 'ENERGY'"  (click)="filterType = 'ENERGY'">エネルギー</button>
            </div>
            <input
              type="text"
              class="search-input"
              [(ngModel)]="searchQuery"
              placeholder="カード名で検索"
            />
          </div>

          <!-- カードリスト -->
          <div class="cards-list">
            @for (card of filteredCards; track card.id) {
              <div class="card-item">
                <div class="card-info">
                  <span class="card-name">{{ card.name }}</span>
                  <span class="card-type-badge">{{ getCategoryLabel(card.evolution_stage) }}</span>
                  @if (card.hp) {
                    <span class="card-hp">HP{{ card.hp }}</span>
                  }
                </div>
                <div class="card-actions">
                  <span class="card-count-in-deck">
                    @if (getCardCount(card.id) > 0) { {{ getCardCount(card.id) }}枚 }
                  </span>
                  <button
                    class="btn-icon btn-add"
                    (click)="addCard(card)"
                    [disabled]="
                      getTotalCount() >= CONSTRAINTS.TOTAL_CARDS ||
                      (!isBasicEnergy(card) && getCardCount(card.id) >= CONSTRAINTS.MAX_SAME_CARD)
                    "
                  >+</button>
                </div>
              </div>
            }

            @if (!isLoading && filteredCards.length === 0) {
              <div class="empty-pool">カードが見つかりません</div>
            }
          </div>

          <!-- 基本エネルギー（固定表示） -->
          @if (filterType === 'ALL' || filterType === 'ENERGY') {
            <div class="basic-energy-section">
              <h4 class="basic-energy-title">基本エネルギー（枚数制限なし）</h4>
              <div class="basic-energy-list">
                @for (energy of basicEnergies; track energy.id) {
                  <div class="energy-item">
                    <div class="energy-info">
                      <span class="energy-icon" [style.color]="getTypeColor(energy.type)">●</span>
                      <span class="card-name">{{ energy.name }}</span>
                    </div>
                    <div class="card-actions">
                      <span class="card-count-in-deck">
                        @if (getCardCount(energy.id) > 0) { {{ getCardCount(energy.id) }}枚 }
                      </span>
                      <button
                        class="btn-icon btn-add"
                        (click)="addCard(energy)"
                        [disabled]="getTotalCount() >= CONSTRAINTS.TOTAL_CARDS"
                      >+</button>
                    </div>
                  </div>
                }
              </div>
            </div>
          }
        </div>

        <!-- 右：現在のデッキ -->
        <div class="current-deck">
          <h3>現在のデッキ ({{ getTotalCount() }}枚)</h3>

          @if (currentDeckEntries.length === 0) {
            <div class="empty-deck">左側からカードを追加してください</div>
          }

          <div class="deck-cards-list">
            @for (entry of currentDeckEntries; track entry.card.id) {
              <div class="deck-card-item">
                <div class="deck-card-info">
                  <span class="deck-card-name">{{ entry.card.name }}</span>
                  <span class="deck-card-type">{{ getCategoryLabel(entry.card.evolution_stage) }}</span>
                </div>
                <div class="deck-card-actions">
                  <button class="btn-icon btn-remove" (click)="removeCard(entry.card.id)">-</button>
                  <span class="deck-card-count">{{ entry.count }}枚</span>
                  <button
                    class="btn-icon btn-add"
                    (click)="addCard(entry.card)"
                    [disabled]="
                      getTotalCount() >= CONSTRAINTS.TOTAL_CARDS ||
                      (!isBasicEnergy(entry.card) && entry.count >= CONSTRAINTS.MAX_SAME_CARD)
                    "
                  >+</button>
                </div>
              </div>
            }
          </div>
        </div>
      </div>

      <!-- アクションボタン -->
      <div class="editor-actions">
        <button class="btn btn-primary btn-large" (click)="saveDeck()" [disabled]="!canSaveDeck">
          @if (isSaving) { 保存中... }
          @else { デッキを保存 ({{ getTotalCount() }}/{{ CONSTRAINTS.TOTAL_CARDS }}枚) }
        </button>
        <button class="btn btn-secondary" (click)="cancelEdit()">キャンセル</button>
      </div>
    </div>
  }
</div>
FILEOF

# ---- frontend/src/app/components/deck-builder/deck-builder.component.scss ----
mkdir -p "frontend/src/app/components/deck-builder"
cat > 'frontend/src/app/components/deck-builder/deck-builder.component.scss' << 'FILEOF'
.deck-builder-container {
  background: url('https://i0.wp.com/tcg-fun.net/wp-content/uploads/2023/06/image-969.webp?fit=1130,639&ssl=1')
    center / cover no-repeat;
  padding: 20px;
  min-height: 100vh;

  h2 {
    color: #2c3e50;
    margin: 0 0 20px 0;
    font-size: 24px;
  }

  h3 {
    color: #34495e;
    margin: 0 0 15px 0;
    font-size: 18px;
  }
}

// ボタン
.btn {
  padding: 10px 20px;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: bold;
  cursor: pointer;
  transition: all 0.3s;

  &:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}

.btn-primary {
  background: #3498db;
  color: white;

  &:hover:not(:disabled) {
    background: #2980b9;
  }
}

.btn-secondary {
  background: #95a5a6;
  color: white;

  &:hover {
    background: #7f8c8d;
  }
}

.btn-delete {
  background: #e74c3c;
  color: white;

  &:hover {
    background: #c0392b;
  }
}

.btn-large {
  padding: 15px 30px;
  font-size: 16px;
}

.btn-icon {
  width: 32px;
  height: 32px;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  border-radius: 4px;
  font-weight: bold;
}

.btn-add {
  background: #2ecc71;
  color: white;

  &:hover:not(:disabled) {
    background: #27ae60;
  }
}

.btn-remove {
  background: #e74c3c;
  color: white;

  &:hover {
    background: #c0392b;
  }
}

// デッキ一覧画面
.deck-list-view {
  background: white;
  padding: 30px;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.header-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 30px;
}

.empty-message {
  text-align: center;
  padding: 60px 20px;
  color: #7f8c8d;
  font-size: 16px;
}

.decks-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
}

.deck-card {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 20px;
  border-radius: 10px;
  color: white;
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
  transition: transform 0.3s;

  &:hover {
    transform: translateY(-5px);
  }

  .deck-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;

    h3 {
      margin: 0;
      color: white;
      font-size: 20px;
    }

    .deck-count {
      background: rgba(255, 255, 255, 0.3);
      padding: 4px 12px;
      border-radius: 12px;
      font-size: 14px;
      font-weight: bold;
    }
  }

  .deck-description {
    margin: 10px 0;
    font-size: 14px;
    opacity: 0.9;
  }

  .deck-stats {
    display: flex;
    gap: 15px;
    margin: 15px 0;
    font-size: 13px;
    opacity: 0.9;
  }

  .deck-actions {
    display: flex;
    gap: 10px;
    margin-top: 15px;
    padding-top: 15px;
    border-top: 1px solid rgba(255, 255, 255, 0.3);
  }
}

// 新規デッキフォーム
.new-deck-form {
  background: white;
  padding: 30px;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  max-width: 600px;
  margin: 0 auto;
}

.form-group {
  margin-bottom: 20px;

  label {
    display: block;
    font-weight: bold;
    margin-bottom: 8px;
    color: #34495e;
  }

  .form-input,
  .form-textarea {
    width: 100%;
    padding: 10px 15px;
    border: 2px solid #ddd;
    border-radius: 6px;
    font-size: 14px;

    &:focus {
      outline: none;
      border-color: #3498db;
    }
  }

  .form-textarea {
    resize: vertical;
    font-family: inherit;
  }
}

.form-actions {
  display: flex;
  gap: 10px;
  margin-top: 30px;
}

// デッキ編集画面
.deck-editor {
  background: white;
  padding: 30px;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.editor-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
  padding-bottom: 20px;
  border-bottom: 2px solid #ecf0f1;

  .deck-info {
    h2 {
      margin: 0 0 10px 0;
    }

    p {
      margin: 0;
      color: #7f8c8d;
    }
  }

  .deck-count-display {
    .count {
      font-size: 32px;
      font-weight: bold;
      color: #e74c3c;

      &.complete {
        color: #2ecc71;
      }
    }
  }
}

.validation-messages {
  background: #fff3cd;
  border: 1px solid #ffc107;
  border-radius: 6px;
  padding: 15px;
  margin-bottom: 20px;

  .validation-message {
    margin: 5px 0;
    color: #856404;
  }
}

.editor-layout {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 30px;
  margin-bottom: 30px;

  @media (max-width: 1024px) {
    grid-template-columns: 1fr;
  }
}

// カードプール
.card-pool {
  background: #f8f9fa;
  padding: 20px;
  border-radius: 8px;
}

.filters {
  margin-bottom: 20px;

  .filter-buttons {
    display: flex;
    gap: 10px;
    margin-bottom: 15px;

    .filter-btn {
      padding: 8px 16px;
      background: white;
      border: 2px solid #ddd;
      border-radius: 6px;
      cursor: pointer;
      transition: all 0.3s;
      font-size: 14px;

      &:hover {
        border-color: #3498db;
      }

      &.active {
        background: #3498db;
        color: white;
        border-color: #3498db;
      }
    }
  }

  .search-input {
    width: 100%;
    padding: 10px 15px;
    border: 2px solid #ddd;
    border-radius: 6px;
    font-size: 14px;

    &:focus {
      outline: none;
      border-color: #3498db;
    }
  }
}

.cards-list {
  max-height: 600px;
  overflow-y: auto;
}

.card-item {
  background: white;
  padding: 15px;
  margin-bottom: 10px;
  border-radius: 6px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  transition: all 0.2s;

  &:hover {
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  }

  .card-info {
    display: flex;
    align-items: center;
    gap: 10px;

    .card-name {
      font-weight: bold;
      color: #2c3e50;
    }

    .card-type-badge {
      padding: 4px 8px;
      border-radius: 4px;
      font-size: 12px;
      background: #ecf0f1;
      color: #7f8c8d;

      &.pokemon {
        background: #e74c3c;
        color: white;
      }
    }
  }

  .card-actions {
    display: flex;
    align-items: center;
    gap: 10px;

    .card-count-in-deck {
      font-size: 14px;
      color: #7f8c8d;
      min-width: 40px;
      text-align: right;
    }
  }
}

// 現在のデッキ
.current-deck {
  background: #f8f9fa;
  padding: 20px;
  border-radius: 8px;
}

.empty-deck {
  text-align: center;
  padding: 60px 20px;
  color: #7f8c8d;
  font-size: 14px;
}

.deck-cards-list {
  max-height: 600px;
  overflow-y: auto;
}

.deck-card-item {
  background: white;
  padding: 15px;
  margin-bottom: 10px;
  border-radius: 6px;
  display: flex;
  justify-content: space-between;
  align-items: center;

  .deck-card-info {
    display: flex;
    flex-direction: column;
    gap: 5px;

    .deck-card-name {
      font-weight: bold;
      color: #2c3e50;
    }

    .deck-card-type {
      font-size: 12px;
      color: #7f8c8d;
    }
  }

  .deck-card-actions {
    display: flex;
    align-items: center;
    gap: 10px;

    .deck-card-count {
      font-size: 16px;
      font-weight: bold;
      color: #2c3e50;
      min-width: 50px;
      text-align: center;
    }
  }
}

// エディターアクション
.editor-actions {
  display: flex;
  gap: 15px;
  padding-top: 30px;
  border-top: 2px solid #ecf0f1;
}
// ===== フェーズ6追加スタイル =====

.error-banner {
  background: #fdecea;
  color: #c0392b;
  border: 1px solid #e74c3c;
  border-radius: 6px;
  padding: 12px 16px;
  margin-bottom: 16px;
}

.loading-inline {
  font-size: 13px;
  font-weight: normal;
  color: #7f8c8d;
  margin-left: 8px;
}

.pool-count {
  font-size: 13px;
  font-weight: normal;
  color: #7f8c8d;
  margin-left: 8px;
}

.card-hp {
  font-size: 12px;
  color: #e74c3c;
  font-weight: 600;
}

.empty-pool {
  text-align: center;
  padding: 40px 20px;
  color: #7f8c8d;
  font-size: 14px;
}

// ===== 基本エネルギーセクション =====

.basic-energy-section {
  margin-top: 20px;
  border-top: 2px dashed #ddd;
  padding-top: 16px;
}

.basic-energy-title {
  font-size: 14px;
  font-weight: bold;
  color: #7f8c8d;
  margin: 0 0 12px 0;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.basic-energy-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.energy-item {
  background: white;
  padding: 10px 15px;
  border-radius: 6px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  transition: all 0.2s;

  &:hover {
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  }
}

.energy-info {
  display: flex;
  align-items: center;
  gap: 10px;
}

.energy-icon {
  font-size: 18px;
  line-height: 1;
}
FILEOF

# ---- frontend/src/app/components/deck-builder/deck-builder.component.ts ----
mkdir -p "frontend/src/app/components/deck-builder"
cat > 'frontend/src/app/components/deck-builder/deck-builder.component.ts' << 'FILEOF'
import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { CardService } from '../../game/services/card.service';
import { BASIC_ENERGIES } from '../../game/data/basic-energies.data';
import { DeckService } from '../../game/services/deck.service';
import { DeckBuilderService } from '../../game/services/deck-builder.service';
import { PokemonCard, getCardCategoryLabel, getTypeColor } from '../../models/card.model';
import {
  Deck, EditingDeck, DECK_CONSTRAINTS,
  newEditingDeck, toEditingDeck, toSaveRequest, getCardFilterCategory, isBasicEnergy,
} from '../../game/types/deck.types';

type FilterType = 'ALL' | 'POKEMON' | 'TRAINER' | 'ENERGY';

@Component({
  selector: 'deck-builder',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './deck-builder.component.html',
  styleUrl: './deck-builder.component.scss',
})
export class DeckBuilderComponent implements OnInit {
  readonly CONSTRAINTS = DECK_CONSTRAINTS;

  // 状態
  allCards: PokemonCard[] = [];
  readonly basicEnergies: PokemonCard[] = BASIC_ENERGIES;
  savedDecks: Deck[] = [];
  currentDeck: EditingDeck | null = null;
  isCreatingNewDeck = false;
  isLoading = false;
  isSaving = false;
  errorMessage = '';

  // 新規作成フォーム
  newDeckName = '';
  newDeckDescription = '';

  // フィルター
  filterType: FilterType = 'ALL';
  searchQuery = '';

  constructor(
    private cardService: CardService,
    private deckService: DeckService,
    protected deckBuilderService: DeckBuilderService,
  ) {}

  ngOnInit(): void {
    this.loadDecks();
    this.loadCards();
  }

  // ==================== データ読み込み ====================

  loadDecks(): void {
    this.deckService.getDecks().subscribe({
      next: (decks) => { this.savedDecks = decks; },
      error: () => { this.errorMessage = 'デッキの取得に失敗しました'; },
    });
  }

  loadCards(): void {
    this.isLoading = true;
    this.cardService.getCards().subscribe({
      next: (cards) => {
        this.allCards = cards;
        this.isLoading = false;
      },
      error: () => {
        this.errorMessage = 'カードの取得に失敗しました';
        this.isLoading = false;
      },
    });
  }

  // ==================== 画面遷移 ====================

  startNewDeck(): void {
    this.isCreatingNewDeck = true;
    this.newDeckName = '';
    this.newDeckDescription = '';
  }

  createNewDeck(): void {
    if (!this.newDeckName.trim()) return;
    this.currentDeck = newEditingDeck();
    this.currentDeck.name = this.newDeckName.trim();
    this.currentDeck.description = this.newDeckDescription;
    this.isCreatingNewDeck = false;
  }

  cancelNewDeck(): void {
    this.isCreatingNewDeck = false;
  }

  editDeck(deck: Deck): void {
    this.currentDeck = toEditingDeck(deck, this.allCards, this.basicEnergies);
  }

  cancelEdit(): void {
    if (confirm('編集内容を破棄しますか？')) {
      this.currentDeck = null;
    }
  }

  // ==================== デッキ操作 ====================

  addCard(card: PokemonCard): void {
    if (!this.currentDeck) return;
    const ok = this.deckBuilderService.addCard(this.currentDeck, card);
    if (!ok) {
      const total = this.deckBuilderService.getTotalCount(this.currentDeck);
      if (total >= DECK_CONSTRAINTS.TOTAL_CARDS) {
        alert(`デッキは${DECK_CONSTRAINTS.TOTAL_CARDS}枚までです`);
      } else {
        alert(`このカードは${DECK_CONSTRAINTS.MAX_SAME_CARD}枚までです`);
      }
    }
  }

  removeCard(cardId: number): void {
    if (!this.currentDeck) return;
    this.deckBuilderService.removeCard(this.currentDeck, cardId);
  }

  // ==================== 保存・削除 ====================

  saveDeck(): void {
    if (!this.currentDeck) return;
    this.isSaving = true;
    const req = toSaveRequest(this.currentDeck);

    const obs = this.currentDeck.id != null
      ? this.deckService.updateDeck(this.currentDeck.id, req)
      : this.deckService.createDeck(req as any);

    obs.subscribe({
      next: () => {
        this.isSaving = false;
        this.currentDeck = null;
        this.loadDecks();
      },
      error: (err) => {
        this.isSaving = false;
        const detail = err.error?.detail;
        if (Array.isArray(detail?.errors)) {
          alert(`保存に失敗しました:\n${detail.errors.join('\n')}`);
        } else {
          alert('保存に失敗しました');
        }
      },
    });
  }

  deleteDeck(id: number): void {
    if (!confirm('このデッキを削除しますか？')) return;
    this.deckService.deleteDeck(id).subscribe({
      next: () => { this.loadDecks(); },
      error: () => { alert('削除に失敗しました'); },
    });
  }

  // ==================== テンプレート用ヘルパー ====================

  get filteredCards(): PokemonCard[] {
    let cards = this.allCards;
    if (this.filterType !== 'ALL') {
      cards = cards.filter(
        (c) => getCardFilterCategory(c.evolution_stage) === this.filterType,
      );
    }
    if (this.searchQuery.trim()) {
      const q = this.searchQuery.toLowerCase();
      cards = cards.filter((c) => c.name.toLowerCase().includes(q));
    }
    return cards;
  }

  /** 現在のデッキの合計枚数 */
  getTotalCount(): number {
    if (!this.currentDeck) return 0;
    return this.deckBuilderService.getTotalCount(this.currentDeck);
  }

  /** デッキ内の特定カードの枚数 */
  getCardCount(cardId: number): number {
    if (!this.currentDeck) return 0;
    return this.deckBuilderService.getCardCount(this.currentDeck, cardId);
  }

  /** 現在のデッキのバリデーション */
  get validation() {
    if (!this.currentDeck) return { valid: false, errors: [], warnings: [] };
    return this.deckBuilderService.validate(this.currentDeck);
  }

  get canSaveDeck(): boolean {
    return this.validation.valid && !this.isSaving;
  }

  get validationMessages(): string[] {
    return [...this.validation.errors, ...this.validation.warnings];
  }

  /** デッキカード一覧（表示用・枚数順） */
  get currentDeckEntries(): { card: PokemonCard; count: number }[] {
    if (!this.currentDeck) return [];
    const entries: { card: PokemonCard; count: number }[] = [];
    this.currentDeck.cardCounts.forEach((count, cardId) => {
      const card = this.currentDeck!.cardMap.get(cardId);
      if (card) entries.push({ card, count });
    });
    return entries.sort((a, b) => {
      const catOrder = { 'POKEMON': 0, 'TRAINER': 1, 'ENERGY': 2, 'OTHER': 3 };
      const oa = catOrder[getCardFilterCategory(a.card.evolution_stage)];
      const ob = catOrder[getCardFilterCategory(b.card.evolution_stage)];
      return oa - ob || a.card.name.localeCompare(b.card.name, 'ja');
    });
  }

  /** savedDecks用カウント */
  getDeckCounts(deck: Deck) {
    const energyTotal = Object.values(deck.energies).reduce((s, n) => s + n, 0);
    const counts = this.deckBuilderService.getCategoryCounts(deck.cards);
    return { ...counts, energy: energyTotal };
  }

  getCategoryLabel(stage: string | null): string {
    return getCardCategoryLabel(stage);
  }

  getTypeColor(type: string | null): string {
    return getTypeColor(type);
  }

  /** テンプレートで使用する基本エネルギー判定 */
  isBasicEnergy(card: PokemonCard): boolean {
    return isBasicEnergy(card);
  }
}
FILEOF

# ---- frontend/src/app/game/data/basic-energies.data.ts ----
mkdir -p "frontend/src/app/game/data"
cat > 'frontend/src/app/game/data/basic-energies.data.ts' << 'FILEOF'
/**
 * 基本エネルギーの定数データ
 *
 * スクレイピングで取得せず、フロントエンドのデータとして管理する。
 * id は負数の固定値（DBのカードと衝突しないようにするため）。
 * evolution_stage = 'エネルギー' で基本エネルギーと判定される。
 */
import { PokemonCard } from '../../models/card.model';

export const BASIC_ENERGIES: PokemonCard[] = [
  {
    id: -1,
    name: '草エネルギー',
    type: '草',
    evolution_stage: 'エネルギー',
    hp: null,
    image_url: 'https://archives.bulbagarden.net/media/upload/thumb/2/2c/Grass-Energy.jpg/170px-Grass-Energy.jpg',
    attacks: [],
    weakness: null,
    resistance: null,
    retreat_cost: null,
    list_index: null,
    created_at: null,
  },
  {
    id: -2,
    name: '炎エネルギー',
    type: '炎',
    evolution_stage: 'エネルギー',
    hp: null,
    image_url: 'https://archives.bulbagarden.net/media/upload/thumb/d/de/Fire-Energy.jpg/170px-Fire-Energy.jpg',
    attacks: [],
    weakness: null,
    resistance: null,
    retreat_cost: null,
    list_index: null,
    created_at: null,
  },
  {
    id: -3,
    name: '水エネルギー',
    type: '水',
    evolution_stage: 'エネルギー',
    hp: null,
    image_url: 'https://archives.bulbagarden.net/media/upload/thumb/a/a0/Water-Energy.jpg/170px-Water-Energy.jpg',
    attacks: [],
    weakness: null,
    resistance: null,
    retreat_cost: null,
    list_index: null,
    created_at: null,
  },
  {
    id: -4,
    name: '雷エネルギー',
    type: '雷',
    evolution_stage: 'エネルギー',
    hp: null,
    image_url: 'https://archives.bulbagarden.net/media/upload/thumb/b/b6/Lightning-Energy.jpg/170px-Lightning-Energy.jpg',
    attacks: [],
    weakness: null,
    resistance: null,
    retreat_cost: null,
    list_index: null,
    created_at: null,
  },
  {
    id: -5,
    name: '超エネルギー',
    type: '超',
    evolution_stage: 'エネルギー',
    hp: null,
    image_url: 'https://archives.bulbagarden.net/media/upload/thumb/1/17/Psychic-Energy.jpg/170px-Psychic-Energy.jpg',
    attacks: [],
    weakness: null,
    resistance: null,
    retreat_cost: null,
    list_index: null,
    created_at: null,
  },
  {
    id: -6,
    name: '闘エネルギー',
    type: '闘',
    evolution_stage: 'エネルギー',
    hp: null,
    image_url: 'https://archives.bulbagarden.net/media/upload/thumb/7/7e/Fighting-Energy.jpg/170px-Fighting-Energy.jpg',
    attacks: [],
    weakness: null,
    resistance: null,
    retreat_cost: null,
    list_index: null,
    created_at: null,
  },
  {
    id: -7,
    name: '悪エネルギー',
    type: '悪',
    evolution_stage: 'エネルギー',
    hp: null,
    image_url: 'https://archives.bulbagarden.net/media/upload/thumb/0/0c/Darkness-Energy.jpg/170px-Darkness-Energy.jpg',
    attacks: [],
    weakness: null,
    resistance: null,
    retreat_cost: null,
    list_index: null,
    created_at: null,
  },
  {
    id: -8,
    name: '鋼エネルギー',
    type: '鋼',
    evolution_stage: 'エネルギー',
    hp: null,
    image_url: 'https://archives.bulbagarden.net/media/upload/thumb/0/09/Metal-Energy.jpg/170px-Metal-Energy.jpg',
    attacks: [],
    weakness: null,
    resistance: null,
    retreat_cost: null,
    list_index: null,
    created_at: null,
  },
  {
    id: -9,
    name: '無色エネルギー',
    type: '無色',
    evolution_stage: 'エネルギー',
    hp: null,
    image_url: 'https://archives.bulbagarden.net/media/upload/thumb/9/94/Colorless-Energy.jpg/170px-Colorless-Energy.jpg',
    attacks: [],
    weakness: null,
    resistance: null,
    retreat_cost: null,
    list_index: null,
    created_at: null,
  },
];
FILEOF

# ---- frontend/src/app/game/services/card.service.ts ----
mkdir -p "frontend/src/app/game/services"
cat > 'frontend/src/app/game/services/card.service.ts' << 'FILEOF'
import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { PokemonCard } from '../../models/card.model';

const API_BASE = 'http://localhost:8000/api';

@Injectable({ providedIn: 'root' })
export class CardService {
  constructor(private http: HttpClient) {}

  /** 全カード一覧を取得 */
  getCards(): Observable<PokemonCard[]> {
    return this.http.get<PokemonCard[]>(`${API_BASE}/cards`);
  }

  /** IDでカードを取得 */
  getCardById(id: number): Observable<PokemonCard> {
    return this.http.get<PokemonCard>(`${API_BASE}/cards/${id}`);
  }
}
FILEOF

# ---- frontend/src/app/game/services/deck-builder.service.ts ----
mkdir -p "frontend/src/app/game/services"
cat > 'frontend/src/app/game/services/deck-builder.service.ts' << 'FILEOF'
import { Injectable } from '@angular/core';
import { PokemonCard } from '../../models/card.model';
import {
  EditingDeck, DECK_CONSTRAINTS, getTotalCount, getCardFilterCategory, isBasicEnergy,
} from '../types/deck.types';

@Injectable({ providedIn: 'root' })
export class DeckBuilderService {

  /** カードをデッキに1枚追加。成功したら true を返す */
  addCard(deck: EditingDeck, card: PokemonCard): boolean {
    const current = deck.cardCounts.get(card.id) ?? 0;
    const total = getTotalCount(deck);

    if (total >= DECK_CONSTRAINTS.TOTAL_CARDS) return false;
    // 基本エネルギーは枚数制限なし
    if (!isBasicEnergy(card) && current >= DECK_CONSTRAINTS.MAX_SAME_CARD) return false;

    deck.cardCounts.set(card.id, current + 1);
    deck.cardMap.set(card.id, card);
    return true;
  }

  /** カードをデッキから1枚削除。0になったらエントリを削除 */
  removeCard(deck: EditingDeck, cardId: number): void {
    const current = deck.cardCounts.get(cardId) ?? 0;
    if (current <= 1) {
      deck.cardCounts.delete(cardId);
      deck.cardMap.delete(cardId);
    } else {
      deck.cardCounts.set(cardId, current - 1);
    }
  }

  /** デッキ内の合計枚数 */
  getTotalCount(deck: EditingDeck): number {
    return getTotalCount(deck);
  }

  /** デッキ内の特定カードの枚数（0なら未投入） */
  getCardCount(deck: EditingDeck, cardId: number): number {
    return deck.cardCounts.get(cardId) ?? 0;
  }

  /** バリデーション結果を返す */
  validate(deck: EditingDeck): { valid: boolean; errors: string[]; warnings: string[] } {
    const errors: string[] = [];
    const warnings: string[] = [];

    if (!deck.name.trim()) errors.push('デッキ名を入力してください');

    const total = getTotalCount(deck);
    if (total > DECK_CONSTRAINTS.TOTAL_CARDS) {
      errors.push(`デッキは${DECK_CONSTRAINTS.TOTAL_CARDS}枚以内にしてください（現在: ${total}枚）`);
    }
    if (total < DECK_CONSTRAINTS.TOTAL_CARDS) {
      warnings.push(`あと${DECK_CONSTRAINTS.TOTAL_CARDS - total}枚追加できます`);
    }

    // たねポケモンが1枚以上必要
    let hasBasic = false;
    deck.cardMap.forEach((card) => {
      if (card.evolution_stage === 'たね') hasBasic = true;
    });
    if (!hasBasic && total > 0) {
      errors.push('たねポケモンが1枚も入っていません');
    }

    return { valid: errors.length === 0 && total === DECK_CONSTRAINTS.TOTAL_CARDS, errors, warnings };
  }

  /** デッキのカード種別カウント（一覧表示用） */
  getCategoryCounts(cards: { evolution_stage: string | null; count: number }[]): {
    pokemon: number; trainer: number; energy: number;
  } {
    let pokemon = 0, trainer = 0, energy = 0;
    cards.forEach(({ evolution_stage, count }) => {
      const cat = getCardFilterCategory(evolution_stage);
      if (cat === 'POKEMON') pokemon += count;
      else if (cat === 'TRAINER') trainer += count;
      else if (cat === 'ENERGY') energy += count;
    });
    return { pokemon, trainer, energy };
  }
}
FILEOF

# ---- frontend/src/app/game/services/deck.service.ts ----
mkdir -p "frontend/src/app/game/services"
cat > 'frontend/src/app/game/services/deck.service.ts' << 'FILEOF'
import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { Deck, DeckCreateRequest, DeckUpdateRequest } from '../types/deck.types';

@Injectable({ providedIn: 'root' })
export class DeckService {
  private http = inject(HttpClient);
  private baseUrl = `${environment.apiUrl.replace('/api/cards', '')}/api/decks`;

  /** 全デッキ一覧を取得 */
  getDecks(): Observable<Deck[]> {
    return this.http.get<Deck[]>(this.baseUrl);
  }

  /** デッキを新規作成 */
  createDeck(req: DeckCreateRequest): Observable<Deck> {
    return this.http.post<Deck>(this.baseUrl, req);
  }

  /** デッキを更新 */
  updateDeck(id: number, req: DeckUpdateRequest): Observable<Deck> {
    return this.http.put<Deck>(`${this.baseUrl}/${id}`, req);
  }

  /** デッキを削除 */
  deleteDeck(id: number): Observable<void> {
    return this.http.delete<void>(`${this.baseUrl}/${id}`);
  }
}
FILEOF

# ---- frontend/src/app/game/types/deck.types.ts ----
mkdir -p "frontend/src/app/game/types"
cat > 'frontend/src/app/game/types/deck.types.ts' << 'FILEOF'
/**
 * デッキ関連の型定義
 * backend/api/deck.py のレスポンスと整合性を取る
 */
import { PokemonCard } from '../../models/card.model';

/** デッキ内のカードエントリ（APIレスポンス用） */
export interface DeckCardEntry {
  card_id: number;
  count: number;
  name: string;
  hp: number | null;
  type: string | null;
  evolution_stage: string | null;
  image_url: string | null;
}

/** デッキ（APIレスポンス用） */
export interface Deck {
  id: number;
  name: string;
  description: string;
  energies: Record<string, number>;  // {"草": 10, "炎": 6}
  created_at: string;
  total_count: number;
  cards: DeckCardEntry[];
}

/** デッキ作成リクエスト */
export interface DeckCreateRequest {
  name: string;
  description?: string;
  cards: { card_id: number; count: number }[];
  energies: Record<string, number>;
}

/** デッキ更新リクエスト */
export interface DeckUpdateRequest {
  name?: string;
  description?: string;
  cards?: { card_id: number; count: number }[];
  energies?: Record<string, number>;
}

/** UI上で編集中のデッキ状態 */
export interface EditingDeck {
  id: number | null;
  name: string;
  description: string;
  /** card_id → count（通常カード用。id が負数の場合は基本エネルギー） */
  cardCounts: Map<number, number>;
  /** card_id → PokemonCard（表示用） */
  cardMap: Map<number, PokemonCard>;
}

/** デッキ制約 */
export const DECK_CONSTRAINTS = {
  TOTAL_CARDS: 60,
  MAX_SAME_CARD: 4,
} as const;

/** 基本エネルギーかどうかを判定（id が負数 = フロントエンドの固定データ） */
export function isBasicEnergy(card: PokemonCard): boolean {
  return card.evolution_stage === 'エネルギー';
}

/** evolution_stage からフィルター用カテゴリを返す */
export function getCardFilterCategory(
  stage: string | null
): 'POKEMON' | 'TRAINER' | 'ENERGY' | 'OTHER' {
  if (!stage) return 'OTHER';
  if (['たね', '1 進化', '2 進化'].includes(stage)) return 'POKEMON';
  if (['サポート', 'グッズ', 'スタジアム'].includes(stage)) return 'TRAINER';
  if (stage === 'エネルギー') return 'ENERGY';
  return 'OTHER';
}

/** EditingDeck の合計枚数を返す */
export function getTotalCount(deck: EditingDeck): number {
  let total = 0;
  deck.cardCounts.forEach((count) => { total += count; });
  return total;
}

/**
 * EditingDeck をAPIリクエスト形式に変換。
 * id が負数（基本エネルギー）は energies に集約し、通常カードは cards に含める。
 */
export function toSaveRequest(deck: EditingDeck): DeckCreateRequest {
  const cards: { card_id: number; count: number }[] = [];
  const energies: Record<string, number> = {};

  deck.cardCounts.forEach((count, card_id) => {
    if (count <= 0) return;
    const card = deck.cardMap.get(card_id);
    if (isBasicEnergy(card!)) {
      // 基本エネルギー → energies に集約
      if (card!.type) energies[card!.type] = count;
    } else {
      cards.push({ card_id, count });
    }
  });

  return { name: deck.name, description: deck.description, cards, energies };
}

/** Deck（APIレスポンス）から EditingDeck を生成 */
export function toEditingDeck(
  deck: Deck,
  allCards: PokemonCard[],
  basicEnergies: PokemonCard[]
): EditingDeck {
  const apiCardMap = new Map<number, PokemonCard>();
  allCards.forEach((c) => apiCardMap.set(c.id, c));

  const energyByType = new Map<string, PokemonCard>();
  basicEnergies.forEach((e) => { if (e.type) energyByType.set(e.type, e); });

  const cardCounts = new Map<number, number>();
  const cardMap = new Map<number, PokemonCard>();

  // 通常カード
  deck.cards.forEach((entry) => {
    const card = apiCardMap.get(entry.card_id);
    if (card) {
      cardCounts.set(entry.card_id, entry.count);
      cardMap.set(entry.card_id, card);
    }
  });

  // 基本エネルギー（energiesフィールドから復元）
  Object.entries(deck.energies).forEach(([type, count]) => {
    const energy = energyByType.get(type);
    if (energy && count > 0) {
      cardCounts.set(energy.id, count);
      cardMap.set(energy.id, energy);
    }
  });

  return { id: deck.id, name: deck.name, description: deck.description, cardCounts, cardMap };
}

/** 空の新規デッキを生成 */
export function newEditingDeck(): EditingDeck {
  return {
    id: null,
    name: '',
    description: '',
    cardCounts: new Map(),
    cardMap: new Map(),
  };
}
FILEOF

# ---- frontend/src/app/models/card.model.ts ----
mkdir -p "frontend/src/app/models"
cat > 'frontend/src/app/models/card.model.ts' << 'FILEOF'
/**
 * カードモデル型定義
 * backend/models/card.py の PokemonCard と整合性を取る
 *
 * NOTE: game-board が使う既存の型（FieldPokemon等）とは別ファイル。
 * カード管理UI（card-viewer / card-list / card-detail）専用の型定義。
 */

/** ワザ情報 */
export interface Attack {
  name: string;
  energy: string[];        // タイプ文字列の配列（例: ["炎", "無色"]）
  energy_count: number;
  damage: number;
  description: string;
}

/** 弱点情報 */
export interface Weakness {
  type: string;   // 例: "水"
  value: string;  // 例: "×2"
}

/** 抵抗力情報 */
export interface Resistance {
  type: string;   // 例: "炎"
  value: string;  // 例: "-30"
}

/** APIから返ってくるポケモンカードの完全な型 */
export interface PokemonCard {
  id: number;
  name: string;
  image_url: string | null;
  list_index: number | null;
  hp: number | null;
  type: string | null;
  evolution_stage: string | null;
  attacks: Attack[];
  weakness: Weakness | null;
  resistance: Resistance | null;
  retreat_cost: number | null;
  created_at: string | null;
}

/** タイプ文字列からCSSカラーを返す */
export const TYPE_COLOR_MAP: Record<string, string> = {
  '草':       '#5db85d',
  '炎':       '#e8652a',
  '水':       '#4a90d9',
  '雷':       '#d4b800',
  '超':       '#9b59b6',
  '闘':       '#c0392b',
  '悪':       '#5d4e37',
  '鋼':       '#7f8c8d',
  'ドラゴン': '#6c3483',
  'フェアリー':'#e91e8c',
  '無色':     '#888888',
};

export function getTypeColor(type: string | null): string {
  if (!type) return '#aaaaaa';
  return TYPE_COLOR_MAP[type] ?? '#aaaaaa';
}

/** evolution_stage からカード種別ラベルを返す */
export function getCardCategoryLabel(stage: string | null): string {
  if (!stage) return '不明';
  if (['たね', '1 進化', '2 進化'].includes(stage)) return 'ポケモン';
  if (['サポート', 'グッズ', 'スタジアム'].includes(stage)) return 'トレーナー';
  if (stage === 'エネルギー') return 'エネルギー';
  return stage;
}
FILEOF

echo "セットアップ完了！"
echo "バックエンド: cd backend && uvicorn main:app --reload"
echo "フロントエンド: cd frontend && npm install && ng serve"