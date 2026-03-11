from __future__ import annotations

import argparse
from dataclasses import dataclass

from cpu.battle_env import ensure_active_if_missing
from cpu.cpu_ai import CpuAI, CpuDifficulty
from cpu.game_integration import CPUPlayer
from engine.actions.faint import send_to_active_from_bench
from engine.models.game_state import GameState
from engine.setup.game_setup import place_initial_pokemon, setup_game, start_game
from engine.turn.turn_manager import end_turn
from models.card import Attack, PokemonCard


@dataclass
class EvalResult:
    total_games: int
    ppo_wins: int
    heuristic_wins: int
    draws: int


def build_demo_deck(base_id: int, element: str) -> list[PokemonCard]:
    if element == "fire":
        ptype = "炎"
        atk1 = Attack(name="ひっかく", energy=["無色"], energy_count=1, damage=10, description="")
        atk2 = Attack(name="かえん", energy=["炎", "炎"], energy_count=2, damage=40, description="")
    else:
        ptype = "雷"
        atk1 = Attack(name="でんき", energy=["雷"], energy_count=1, damage=20, description="")
        atk2 = Attack(name="スパーク", energy=["雷", "無色"], energy_count=2, damage=30, description="")

    deck: list[PokemonCard] = []
    for i in range(4):
        deck.append(
            PokemonCard(
                id=base_id + i,
                name=f"{element}_basic_{i}",
                card_type="pokemon",
                evolution_stage="たね",
                hp=70,
                type=ptype,
                attacks=[atk1, atk2],
                retreat_cost=1,
            )
        )

    for i in range(56):
        deck.append(
            PokemonCard(
                id=base_id + 100 + i,
                name=f"{ptype}エネルギー",
                card_type="energy",
                evolution_stage="エネルギー",
                type=ptype,
                attacks=[],
                retreat_cost=0,
            )
        )
    return deck


def setup_eval_game() -> GameState:
    p1_deck = build_demo_deck(1000, "lightning")
    p2_deck = build_demo_deck(2000, "fire")
    game_state = setup_game(p1_deck, p2_deck)

    for pid in ("player1", "player2"):
        player = game_state.get_player(pid)
        basics = [c for c in player.hand if c.evolution_stage == "たね"]
        active = max(basics, key=lambda c: c.hp or 0)
        bench = [c for c in basics if c.uid != active.uid][:5]
        place_initial_pokemon(game_state, pid, active, bench)

    start_game(game_state)
    return game_state


def force_replace_if_needed(game_state: GameState, player_id: str) -> None:
    player = game_state.get_player(player_id)
    if player.has_active:
        return
    if not player.has_bench_pokemon:
        return
    best = max(range(len(player.bench)), key=lambda i: player.bench[i].current_hp)
    send_to_active_from_bench(game_state, player_id, best)


def run_single_match(model_path: str, ppo_side: str = "player2", max_turns: int = 80) -> str | None:
    game_state = setup_eval_game()

    ppo_player = CPUPlayer(model_path=model_path, player_id=ppo_side)
    h_side = "player2" if ppo_side == "player1" else "player1"
    heuristic_player = CpuAI(CpuDifficulty.NORMAL, player_id=h_side)

    for _ in range(max_turns):
        if game_state.is_game_over:
            break

        current_pid = game_state.current_player_id
        before_turn = game_state.current_turn

        force_replace_if_needed(game_state, "player1")
        force_replace_if_needed(game_state, "player2")

        if current_pid == ppo_side:
            ppo_player.play_turn(game_state)
        else:
            heuristic_player.take_turn(game_state)

        force_replace_if_needed(game_state, "player1")
        force_replace_if_needed(game_state, "player2")

        if not game_state.is_game_over:
            stuck = (
                game_state.current_player_id == current_pid
                and game_state.current_turn == before_turn
            )
            if stuck:
                end_turn(game_state)

    return game_state.winner_id


def evaluate(model_path: str, games: int = 20, ppo_side: str = "player2", max_turns: int = 80) -> EvalResult:
    ppo_wins = 0
    heuristic_wins = 0
    draws = 0

    h_side = "player2" if ppo_side == "player1" else "player1"

    for _ in range(games):
        winner = run_single_match(model_path=model_path, ppo_side=ppo_side, max_turns=max_turns)
        if winner == ppo_side:
            ppo_wins += 1
        elif winner == h_side:
            heuristic_wins += 1
        else:
            draws += 1

    return EvalResult(
        total_games=games,
        ppo_wins=ppo_wins,
        heuristic_wins=heuristic_wins,
        draws=draws,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate PPO CPU against heuristic CPU")
    parser.add_argument("--model-path", required=True, help="Path to trained PPO .zip model")
    parser.add_argument("--games", type=int, default=20, help="Number of matches")
    parser.add_argument("--ppo-side", choices=["player1", "player2"], default="player2")
    parser.add_argument("--max-turns", type=int, default=80)
    args = parser.parse_args()

    result = evaluate(
        model_path=args.model_path,
        games=args.games,
        ppo_side=args.ppo_side,
        max_turns=args.max_turns,
    )

    ppo_wr = (result.ppo_wins / result.total_games) * 100.0 if result.total_games else 0.0
    h_wr = (result.heuristic_wins / result.total_games) * 100.0 if result.total_games else 0.0

    print("=== PPO Evaluation Result ===")
    print(f"games: {result.total_games}")
    print(f"ppo wins: {result.ppo_wins} ({ppo_wr:.1f}%)")
    print(f"heuristic wins: {result.heuristic_wins} ({h_wr:.1f}%)")
    print(f"draws: {result.draws}")


if __name__ == "__main__":
    main()
