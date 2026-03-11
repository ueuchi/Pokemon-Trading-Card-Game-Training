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


def _assign_uids(deck: List[PokemonCard], start: int = 1) -> List[PokemonCard]:
    """デッキの各カードにユニークなuidを振る（同名カードを区別するため）"""
    for i, card in enumerate(deck):
        card.uid = start + i
    return deck


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
    # 各カードにユニークIDを振る（同名カード区別用）
    _assign_uids(player1_deck, start=1)
    _assign_uids(player2_deck, start=1001)

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

    # バトル場に配置（uidで特定の1枚を除去）
    player.hand = [c for c in player.hand if c.uid != active_card.uid]
    player.active_pokemon = ActivePokemon(card=active_card, turns_in_play=0)

    # ベンチに配置（uidで特定のカードを除去）
    bench_uids = {c.uid for c in bench_cards}
    player.hand = [c for c in player.hand if c.uid not in bench_uids]
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
