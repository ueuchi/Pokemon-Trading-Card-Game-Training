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
