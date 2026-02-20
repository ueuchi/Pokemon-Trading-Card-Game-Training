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
