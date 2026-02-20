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
