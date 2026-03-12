"""
CPU対戦 FastAPI エンドポイント

エンドポイント一覧:
  POST /api/game/cpu/start                   ゲーム開始
  GET  /api/game/cpu/{game_id}               ゲーム状態取得
  POST /api/game/cpu/{game_id}/place_initial  初期ポケモン配置
  POST /api/game/cpu/{game_id}/action         プレイヤーのアクション実行
  POST /api/game/cpu/{game_id}/end_turn       ターン終了（CPUが自動実行）
  POST /api/game/cpu/{game_id}/replace_active きぜつ後のバトル場交代
  DELETE /api/game/cpu/{game_id}              セッション削除
"""
import json
from copy import deepcopy
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from models.card import PokemonCard

from engine.setup.game_setup import setup_game, place_initial_pokemon, start_game
from engine.turn.turn_manager import begin_turn, end_turn
from engine.actions.place_pokemon import place_to_active, place_to_bench
from engine.actions.evolve import evolve_active, evolve_bench
from engine.actions.attach_energy import attach_energy
from engine.actions.retreat import retreat
from engine.actions.trainer import use_supporter, use_goods, use_stadium
from engine.actions.attack import declare_attack
from engine.actions.faint import send_to_active_from_bench
from engine.deck_validator import validate_deck
from cpu.cpu_runtime import CpuRuntime
from cpu.game_session import create_session, get_session, delete_session
from database.connection import get_db_connection
from repositories.card_repository import CardRepository

router = APIRouter(prefix="/api/game/cpu", tags=["CPU対戦"])

_cpu_runtime = CpuRuntime(player_id="player2")


# ==================== リクエストモデル ====================

class StartGameRequest(BaseModel):
    player_deck_id: int
    cpu_deck_id: Optional[int] = None


class PlaceInitialRequest(BaseModel):
    active_card_id: int  # uid of the card
    bench_card_ids: List[int] = []  # uids of the cards


class ActionRequest(BaseModel):
    action_type: str
    card_id: Optional[int] = None  # uid of the card (unique instance id)
    attack_index: Optional[int] = None
    bench_index: Optional[int] = None
    energy_indices: Optional[List[int]] = None
    target: Optional[str] = None


class ReplaceActiveRequest(BaseModel):
    bench_index: int


# ==================== ヘルパー ====================

def _load_deck_from_db(conn, deck_id: int) -> list:
    """DBからデッキを読み込んでPokemonCardリストを返す（エネルギー含む）"""
    repo = CardRepository(conn)

    deck_row = conn.execute(
        "SELECT id, name, energies FROM decks WHERE id = ?", (deck_id,)
    ).fetchone()
    if not deck_row:
        raise HTTPException(status_code=404, detail=f"デッキID={deck_id}が見つかりません")

    rows = conn.execute(
        "SELECT card_id, count FROM deck_cards WHERE deck_id = ?", (deck_id,)
    ).fetchall()

    deck = []

    # 通常カードを展開
    for row in rows:
        card = repo.get_card_by_id(row["card_id"])
        if card is None:
            raise HTTPException(status_code=400, detail=f"カードID={row['card_id']}が見つかりません")
        for _ in range(row["count"]):
            deck.append(deepcopy(card))

    # 基本エネルギーを展開（energies JSON: {"草": 22, "雷": 0} など）
    energy_counter = -1001  # 負のIDで通常カードと衝突しないようにする
    energies: dict = json.loads(deck_row["energies"] or "{}")
    for energy_type, count in energies.items():
        for _ in range(count):
            deck.append(PokemonCard(
                id=energy_counter,
                name=f"{energy_type}エネルギー",
                card_type="energy",
                energy_type="basic",
                type=energy_type,
            ))
            energy_counter -= 1

    return deck


def _get_cpu_deck(conn) -> list:
    """CPUデッキを自動選択（player_deck_idとは別のデッキを優先）"""
    row = conn.execute("SELECT id FROM decks ORDER BY id LIMIT 1 OFFSET 1").fetchone()
    if not row:
        row = conn.execute("SELECT id FROM decks ORDER BY id LIMIT 1").fetchone()
    if not row:
        raise HTTPException(status_code=400, detail="DBにデッキがありません。先にデッキを作成してください")
    return _load_deck_from_db(conn, row["id"])


def _run_cpu_turn(game_state) -> list:
    """CPUターンを実行する共通入口。

    実行戦略はCpuRuntimeが管理し、将来のCPU差し替えを容易にする。
    """
    return _cpu_runtime.play_turn(game_state)


# ==================== エンドポイント ====================

@router.post("/start")
async def start_cpu_game(request: StartGameRequest):
    """CPU対戦を開始する。DBからデッキを読み込み、バリデーション後にゲームを初期化する。"""
    try:
        with get_db_connection() as conn:
            p1_deck = _load_deck_from_db(conn, request.player_deck_id)
            if request.cpu_deck_id:
                p2_deck = _load_deck_from_db(conn, request.cpu_deck_id)
            else:
                p2_deck = _get_cpu_deck(conn)

        # デッキバリデーション
        p1_valid, p1_errors = validate_deck(p1_deck)
        if not p1_valid:
            raise HTTPException(status_code=400, detail=f"プレイヤーデッキエラー: {'; '.join(p1_errors)}")

        p2_valid, p2_errors = validate_deck(p2_deck)
        if not p2_valid:
            raise HTTPException(status_code=400, detail=f"CPUデッキエラー: {'; '.join(p2_errors)}")

        # ゲーム初期化（コイントス・マリガン・サイドカードセット）
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
    game_state = get_session(game_id)
    if not game_state:
        raise HTTPException(status_code=404, detail=f"ゲームセッションが見つかりません: {game_id}")
    return game_state.to_dict()


@router.post("/{game_id}/place_initial")
async def place_initial(game_id: str, request: PlaceInitialRequest):
    """プレイヤーの初期ポケモンを配置し、CPUも自動配置してゲームを開始する。"""
    game_state = get_session(game_id)
    if not game_state:
        raise HTTPException(status_code=404, detail="ゲームセッションが見つかりません")

    try:
        p1 = game_state.player1
        active_card = next((c for c in p1.hand if c.uid == request.active_card_id), None)
        if not active_card:
            raise HTTPException(status_code=400, detail="指定のカードが手札にありません")
        if getattr(active_card, "evolution_stage", None) != "たね":
            raise HTTPException(status_code=400, detail="バトル場にはたねポケモンしか出せません")

        bench_card_uid_set = set(request.bench_card_ids)
        bench_cards = [
            c for c in p1.hand
            if c.uid in bench_card_uid_set and getattr(c, "evolution_stage", None) == "たね"
        ][:5]
        place_initial_pokemon(game_state, "player1", active_card, bench_cards)

        # CPU自動配置
        p2 = game_state.player2
        basics = [c for c in p2.hand if getattr(c, "evolution_stage", None) == "たね"]
        if not basics:
            raise HTTPException(status_code=500, detail="CPUの手札にたねポケモンがありません")

        cpu_active = max(basics, key=lambda c: c.hp or 0)
        cpu_bench = [c for c in basics if c.uid != cpu_active.uid][:5]
        place_initial_pokemon(game_state, "player2", cpu_active, cpu_bench)

        start_game(game_state)

        # 先行がCPUなら即ターン実行
        cpu_actions = []
        if game_state.current_player_id == "player2":
            cpu_actions = _run_cpu_turn(game_state)

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
    game_state = get_session(game_id)
    if not game_state:
        raise HTTPException(status_code=404, detail="ゲームセッションが見つかりません")
    if game_state.is_game_over:
        raise HTTPException(status_code=400, detail="ゲームはすでに終了しています")
    if game_state.current_player_id != "player1":
        raise HTTPException(status_code=400, detail="プレイヤー1のターンではありません")

    from engine.models.game_enums import TurnPhase
    draw_result = None
    if game_state.turn_phase == TurnPhase.DRAW:
        draw_result = begin_turn(game_state)
        if not draw_result["success"] or game_state.is_game_over:
            return {"draw_result": draw_result, "state": game_state.to_dict()}

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
    game_state = get_session(game_id)
    if not game_state:
        raise HTTPException(status_code=404, detail="ゲームセッションが見つかりません")
    if game_state.is_game_over:
        raise HTTPException(status_code=400, detail="ゲームはすでに終了しています")
    if game_state.current_player_id != "player1":
        raise HTTPException(status_code=400, detail="プレイヤー1のターンではありません")

    from engine.models.game_enums import TurnPhase
    if game_state.turn_phase == TurnPhase.DRAW:
        begin_turn(game_state)

    end_result = end_turn(game_state)

    cpu_actions = []
    if not game_state.is_game_over:
        cpu_actions = _run_cpu_turn(game_state)

    return {
        "end_result": end_result,
        "cpu_actions": cpu_actions,
        "state": game_state.to_dict(),
    }


@router.post("/{game_id}/replace_active")
async def replace_active(game_id: str, request: ReplaceActiveRequest):
    game_state = get_session(game_id)
    if not game_state:
        raise HTTPException(status_code=404, detail="ゲームセッションが見つかりません")

    p1 = game_state.player1
    if p1.has_active:
        raise HTTPException(status_code=400, detail="バトル場にすでにポケモンがいます")

    result = send_to_active_from_bench(game_state, "player1", request.bench_index)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])

    return {"result": result, "state": game_state.to_dict()}


@router.delete("/{game_id}")
async def delete_game(game_id: str):
    deleted = delete_session(game_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="ゲームセッションが見つかりません")
    return {"message": f"セッション {game_id} を削除しました"}