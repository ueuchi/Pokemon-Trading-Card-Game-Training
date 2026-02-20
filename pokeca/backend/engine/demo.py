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
