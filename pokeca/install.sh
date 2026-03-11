#!/bin/bash
# ============================================================
# install.sh - ファイルを直接生成するスクリプト
# 使い方: bash install.sh /path/to/pokeca
# 例:     bash install.sh .  （pokecaディレクトリ内から実行）
# ============================================================
set -e

if [ -z "$1" ]; then
  echo "❌ プロジェクトのパスを指定してください"
  echo "   使い方: bash install.sh /path/to/pokeca"
  exit 1
fi

P="$1"
echo "============================================"
echo "📦 install.sh - ファイル生成開始"
echo "   対象: $P"
echo "============================================"

mkdir -p "$P/backend/engine/models"
mkdir -p "$P/backend/engine/actions"
mkdir -p "$P/backend/engine"
mkdir -p "$P/backend/models"
mkdir -p "$P/backend/repositories"
mkdir -p "$P/backend/scripts"
mkdir -p "$P/backend/api"
mkdir -p "$P/src/app/game/services"
mkdir -p "$P/src/app/components/game-board"

echo ""
echo "📝 ファイルを生成しています..."

# ============================================================
# backend/engine/deck_validator.py
# ============================================================
cat > "$P/backend/engine/deck_validator.py" << 'EOF'
"""
デッキバリデーション
- 60枚制限
- 同名カード4枚制限（基本エネルギーを除く）
- ACE SPECはデッキに1枚のみ
"""
from typing import List, Tuple
from models.card import PokemonCard


def validate_deck(deck: List[PokemonCard]) -> Tuple[bool, List[str]]:
    """
    デッキが正しいか検証する。

    Returns:
        (is_valid, errors): エラーがなければ is_valid=True、errors=[]
    """
    errors = []

    # 60枚チェック
    if len(deck) != 60:
        errors.append(f"デッキは60枚必要です（現在{len(deck)}枚）")

    # 同名カード枚数チェック
    name_count: dict[str, int] = {}
    ace_spec_count = 0

    for card in deck:
        name_count[card.name] = name_count.get(card.name, 0) + 1

        # ACE SPECカウント
        if card.card_type == "trainer" and card.is_ace_spec:
            ace_spec_count += 1

    for name, count in name_count.items():
        # 基本エネルギーは枚数制限なし
        card = next((c for c in deck if c.name == name), None)
        if card and card.card_type == "energy" and card.energy_type == "basic":
            continue
        if count > 4:
            errors.append(f"「{name}」は4枚までです（現在{count}枚）")

    # ACE SPEC 1枚制限
    if ace_spec_count > 1:
        ace_cards = [c.name for c in deck if c.card_type == "trainer" and c.is_ace_spec]
        errors.append(f"ACE SPECはデッキに1枚までです（現在{ace_spec_count}枚: {ace_cards}）")

    return len(errors) == 0, errors
EOF
echo "  ✅ backend/engine/deck_validator.py"

# ============================================================
# backend/scripts/migrate_cards.py
# ============================================================
cat > "$P/backend/scripts/migrate_cards.py" << 'EOF'
"""
カードテーブルマイグレーション
新しいデータモデルに合わせてcardsテーブルを更新する

実行方法: backend/ ディレクトリで
  python scripts/migrate_cards.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import get_db_connection


def migrate():
    with get_db_connection() as conn:
        cursor = conn.execute("PRAGMA table_info(cards)")
        existing_cols = {row["name"] for row in cursor.fetchall()}
        print(f"既存カラム: {existing_cols}")

        migrations = [
            ("pokemon_type",       "TEXT DEFAULT NULL"),
            ("card_rule",          "TEXT DEFAULT NULL"),
            ("ability",            "TEXT DEFAULT NULL"),
            ("image_url",          "TEXT DEFAULT NULL"),
            ("energy_type",        "TEXT DEFAULT NULL"),
            ("trainer_type",       "TEXT DEFAULT NULL"),
            ("is_ace_spec",        "INTEGER DEFAULT 0"),
            ("effect_description", "TEXT DEFAULT NULL"),
        ]

        added = 0
        for col_name, col_def in migrations:
            if col_name not in existing_cols:
                conn.execute(f"ALTER TABLE cards ADD COLUMN {col_name} {col_def}")
                print(f"  ✅ カラム追加: {col_name}")
                added += 1
            else:
                print(f"  ⚠️  スキップ (既存): {col_name}")

        conn.execute("""
            UPDATE cards SET pokemon_type = 'normal'
            WHERE card_type = 'pokemon' AND pokemon_type IS NULL
        """)
        conn.execute("""
            UPDATE cards SET energy_type = 'basic'
            WHERE card_type = 'energy' AND energy_type IS NULL
        """)
        conn.commit()
        print(f"\n✅ マイグレーション完了 ({added} カラム追加)")


if __name__ == "__main__":
    migrate()
EOF
echo "  ✅ backend/scripts/migrate_cards.py"

# ============================================================
# backend/scripts/create_initial_deck.py
# ============================================================
cat > "$P/backend/scripts/create_initial_deck.py" << 'EOF'
"""
初期デッキ作成スクリプト

実行方法: backend/ ディレクトリで
  python scripts/create_initial_deck.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import get_db_connection
from repositories.card_repository import CardRepository

CARDS = [
    {
        "name": "ピカチュウ", "card_type": "pokemon", "pokemon_type": "normal",
        "card_rule": None, "evolution_stage": "たね", "evolves_from": None,
        "hp": 70, "type": "雷",
        "attacks": [
            {"name": "でんきショック", "energy": ["雷"], "energy_count": 1, "damage": 20,
             "description": "コインを1回投げオモテなら、相手のバトルポケモンをマヒにする。"},
            {"name": "かみなり", "energy": ["雷", "雷", "無色"], "energy_count": 3, "damage": 60,
             "description": "コインを1回投げウラなら、このポケモンにも30ダメージ。"},
        ],
        "ability": None, "weakness": {"type": "闘", "value": 2},
        "resistance": None, "retreat_cost": 1, "image_url": None,
    },
    {
        "name": "ライチュウ", "card_type": "pokemon", "pokemon_type": "normal",
        "card_rule": None, "evolution_stage": "1進化", "evolves_from": "ピカチュウ",
        "hp": 100, "type": "雷",
        "attacks": [
            {"name": "エレクトロバーン", "energy": ["雷", "無色", "無色"], "energy_count": 3, "damage": 80, "description": ""},
            {"name": "サンダーボルト", "energy": ["雷", "雷", "無色", "無色"], "energy_count": 4, "damage": 120,
             "description": "このポケモンについているエネルギーをすべてトラッシュする。"},
        ],
        "ability": None, "weakness": {"type": "闘", "value": 2},
        "resistance": None, "retreat_cost": 2, "image_url": None,
    },
    {
        "name": "雷エネルギー", "card_type": "energy", "pokemon_type": None,
        "card_rule": None, "evolution_stage": None, "evolves_from": None,
        "hp": None, "type": "雷", "attacks": [], "ability": None,
        "weakness": None, "resistance": None, "retreat_cost": 0,
        "energy_type": "basic", "image_url": None,
    },
    {
        "name": "ヒトカゲ", "card_type": "pokemon", "pokemon_type": "normal",
        "card_rule": None, "evolution_stage": "たね", "evolves_from": None,
        "hp": 60, "type": "炎",
        "attacks": [
            {"name": "ひっかく", "energy": ["無色"], "energy_count": 1, "damage": 10, "description": ""},
            {"name": "かえんほうしゃ", "energy": ["炎", "炎"], "energy_count": 2, "damage": 40, "description": ""},
        ],
        "ability": None, "weakness": {"type": "水", "value": 2},
        "resistance": None, "retreat_cost": 1, "image_url": None,
    },
    {
        "name": "リザード", "card_type": "pokemon", "pokemon_type": "normal",
        "card_rule": None, "evolution_stage": "1進化", "evolves_from": "ヒトカゲ",
        "hp": 90, "type": "炎",
        "attacks": [
            {"name": "ほのおのうず", "energy": ["炎", "無色"], "energy_count": 2, "damage": 30, "description": ""},
            {"name": "フレイムテール", "energy": ["炎", "炎", "無色"], "energy_count": 3, "damage": 60, "description": ""},
        ],
        "ability": None, "weakness": {"type": "水", "value": 2},
        "resistance": None, "retreat_cost": 2, "image_url": None,
    },
    {
        "name": "リザードン", "card_type": "pokemon", "pokemon_type": "normal",
        "card_rule": None, "evolution_stage": "2進化", "evolves_from": "リザード",
        "hp": 160, "type": "炎",
        "attacks": [
            {"name": "ほのおのつばさ", "energy": ["炎", "炎", "無色"], "energy_count": 3, "damage": 90, "description": ""},
            {"name": "ごうかのうず", "energy": ["炎", "炎", "炎", "無色"], "energy_count": 4, "damage": 150,
             "description": "このポケモンについている炎エネルギーを2枚トラッシュする。"},
        ],
        "ability": {"name": "かえんのよろい", "description": "このポケモンが受けるダメージを-20する。（Phase 11で実装）"},
        "weakness": {"type": "水", "value": 2},
        "resistance": None, "retreat_cost": 3, "image_url": None,
    },
    {
        "name": "炎エネルギー", "card_type": "energy", "pokemon_type": None,
        "card_rule": None, "evolution_stage": None, "evolves_from": None,
        "hp": None, "type": "炎", "attacks": [], "ability": None,
        "weakness": None, "resistance": None, "retreat_cost": 0,
        "energy_type": "basic", "image_url": None,
    },
]

DECK_PIKACHU = {"ピカチュウ": 4, "ライチュウ": 2, "雷エネルギー": 54}
DECK_HITOKAGE = {"ヒトカゲ": 4, "リザード": 2, "リザードン": 2, "炎エネルギー": 52}


def run():
    with get_db_connection() as conn:
        repo = CardRepository(conn)
        print("============================================")
        print("🃏 初期デッキ作成スクリプト")
        print("============================================")

        card_id_map = {}
        created = skipped = 0

        for card_data in CARDS:
            existing = [c for c in repo.get_cards_by_name(card_data["name"]) if c.name == card_data["name"]]
            if existing:
                card_id_map[card_data["name"]] = existing[0].id
                print(f"  ⚠️  スキップ (既存): {card_data['name']} (ID: {existing[0].id})")
                skipped += 1
            else:
                card_id = repo.create_card(card_data)
                card_id_map[card_data["name"]] = card_id
                print(f"  ✅ 作成: {card_data['name']} (ID: {card_id})")
                created += 1

        print(f"\n📦 カード: 作成 {created} 枚 / スキップ {skipped} 枚")
        _create_deck(conn, "ピカチュウデッキ（雷）", DECK_PIKACHU, card_id_map)
        _create_deck(conn, "リザードンデッキ（炎）", DECK_HITOKAGE, card_id_map)
        print("\n============================================")
        print("✅ 完了！デッキが作成されました")
        print("============================================")


def _create_deck(conn, deck_name, deck_config, card_id_map):
    if conn.execute("SELECT id FROM decks WHERE name = ?", (deck_name,)).fetchone():
        print(f"\n  ⚠️  デッキ既存: {deck_name} (スキップ)")
        return
    cursor = conn.execute("INSERT INTO decks (name) VALUES (?)", (deck_name,))
    deck_id = cursor.lastrowid
    conn.commit()
    for card_name, quantity in deck_config.items():
        card_id = card_id_map.get(card_name)
        if card_id:
            conn.execute(
                "INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (?, ?, ?)",
                (deck_id, card_id, quantity)
            )
    conn.commit()
    total = sum(deck_config.values())
    print(f"\n  ✅ デッキ作成: {deck_name} ({total}枚) ID: {deck_id}")
    for n, q in deck_config.items():
        print(f"     {n} × {q}")


if __name__ == "__main__":
    run()
EOF
echo "  ✅ backend/scripts/create_initial_deck.py"

# ============================================================
# frontend (src/app/game/services/game-api.service.ts)
# ============================================================
cat > "$P/src/app/game/services/game-api.service.ts" << 'EOF'
/**
 * Game API Service（新フロー対応版）
 */
import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { BehaviorSubject, Observable, firstValueFrom } from 'rxjs';
import { environment } from '../../../environments/environment';

export interface AttackInfo { name: string; energy: string[]; energy_count: number; damage: number; description: string; }
export interface AbilityInfo { name: string; description: string; }
export interface WeaknessInfo { type: string; value: number; }

export interface ActivePokemon {
  card_id: number; name: string; hp: number; current_hp: number; damage_counters: number;
  attached_energy: string[]; special_condition: string; turns_in_play: number;
  evolution_stage: string; type: string; pokemon_type: string; card_rule: string | null;
  attacks: AttackInfo[]; ability: AbilityInfo | null; retreat_cost: number;
  weakness: WeaknessInfo | null; resistance: WeaknessInfo | null; image_url: string | null;
}

export interface HandCard {
  card_id: number; name: string; card_type: string; evolution_stage: string | null;
  evolves_from: string | null; type: string | null; energy_type: string | null;
  trainer_type: string | null; is_ace_spec: boolean; pokemon_type: string | null; image_url: string | null;
}

export interface PlayerState {
  player_id: string; deck_count: number; hand_count: number; hand: HandCard[];
  active_pokemon: ActivePokemon | null; bench: ActivePokemon[]; prize_remaining: number;
  discard_count: number; energy_attached_this_turn: boolean;
  supporter_used_this_turn: boolean; retreated_this_turn: boolean;
}

export interface GameStateResponse {
  game_id: string; current_turn: number; current_player_id: string; first_player_id: string;
  game_phase: string; turn_phase: string; winner_id: string | null; is_first_turn: boolean;
  attacked_this_turn: boolean; coin_toss_result: string | null;
  mulligan_info: { player1_mulligans: number; player2_mulligans: number } | null;
  stadium: { card_id: number; name: string; played_by: string } | null;
  player1: PlayerState; player2: PlayerState;
  logs: { turn: number; player_id: string; action: string; detail: string }[];
}

export type GameScreen = 'deck-select' | 'coin-toss' | 'place-initial' | 'battle' | 'game-over';

export interface GameUiState {
  screen: GameScreen; gameState: GameStateResponse | null; gameId: string | null;
  isLoading: boolean; error: string | null; selectedCardId: number | null;
  selectedAttackIndex: number | null; selectedBenchIndex: number | null;
  initialActiveId: number | null; initialBenchIds: number[]; isCpuThinking: boolean; logs: string[];
}

@Injectable({ providedIn: 'root' })
export class GameApiService {
  private readonly baseUrl = `${environment.apiUrl}/api/game/cpu`;
  private uiState$ = new BehaviorSubject<GameUiState>(this._initialState());
  state$: Observable<GameUiState> = this.uiState$.asObservable();

  constructor(private http: HttpClient) {}

  private _initialState(): GameUiState {
    return {
      screen: 'deck-select', gameState: null, gameId: null, isLoading: false, error: null,
      selectedCardId: null, selectedAttackIndex: null, selectedBenchIndex: null,
      initialActiveId: null, initialBenchIds: [], isCpuThinking: false, logs: [],
    };
  }

  get state(): GameUiState { return this.uiState$.value; }
  private patch(p: Partial<GameUiState>): void { this.uiState$.next({ ...this.state, ...p }); }
  private addLog(msg: string): void { this.patch({ logs: [...this.state.logs, msg].slice(-100) }); }

  async startGame(playerDeckId: number, cpuDeckId?: number): Promise<void> {
    this.patch({ isLoading: true, error: null });
    try {
      const res: any = await firstValueFrom(this.http.post(`${this.baseUrl}/start`, {
        player_deck_id: playerDeckId, cpu_deck_id: cpuDeckId ?? null,
      }));
      const gs: GameStateResponse = res.state;
      const first = gs.first_player_id === 'player1' ? 'あなた' : 'CPU';
      this.patch({ gameId: res.game_id, gameState: gs, screen: 'coin-toss', isLoading: false,
        logs: [`🪙 コイントス結果: ${first}が先行！`] });
    } catch (e: any) {
      this.patch({ isLoading: false, error: e?.error?.detail ?? 'ゲーム開始に失敗しました' });
    }
  }

  proceedToPlaceInitial(): void {
    const mulligan = this.state.gameState?.mulligan_info;
    const logs = [...this.state.logs];
    if (mulligan?.player1_mulligans) logs.push(`🔄 あなたは${mulligan.player1_mulligans}回マリガンしました`);
    if (mulligan?.player2_mulligans) logs.push(`🔄 CPUは${mulligan.player2_mulligans}回マリガンしました`);
    logs.push('🃏 バトル場とベンチにポケモンを配置してください');
    this.patch({ screen: 'place-initial', logs });
  }

  toggleInitialActive(cardId: number): void {
    this.patch({ initialActiveId: this.state.initialActiveId === cardId ? null : cardId,
      initialBenchIds: this.state.initialBenchIds.filter(id => id !== cardId), error: null });
  }

  toggleInitialBench(cardId: number): void {
    if (this.state.initialActiveId === cardId) return;
    const ids = [...this.state.initialBenchIds];
    const idx = ids.indexOf(cardId);
    if (idx >= 0) ids.splice(idx, 1); else if (ids.length < 5) ids.push(cardId);
    this.patch({ initialBenchIds: ids, error: null });
  }

  async confirmInitialPlacement(): Promise<void> {
    const { initialActiveId, initialBenchIds, gameId } = this.state;
    if (!initialActiveId || !gameId) return;
    this.patch({ isLoading: true, error: null });
    try {
      const res: any = await firstValueFrom(this.http.post(`${this.baseUrl}/${gameId}/place_initial`, {
        active_card_id: initialActiveId, bench_card_ids: initialBenchIds,
      }));
      this.patch({ gameState: res.state, screen: 'battle', isLoading: false,
        initialActiveId: null, initialBenchIds: [] });
      this.addLog('⚔️ ゲーム開始！');
      this._syncLogsFromState(res.state);
    } catch (e: any) {
      this.patch({ isLoading: false, error: e?.error?.detail ?? '初期配置に失敗しました' });
    }
  }

  async sendAction(actionType: string, opts: {
    cardId?: number; attackIndex?: number; benchIndex?: number; energyIndices?: number[]; target?: string;
  } = {}): Promise<void> {
    if (!this.state.gameId) return;
    this.patch({ isLoading: true, error: null });
    try {
      const res: any = await firstValueFrom(this.http.post(`${this.baseUrl}/${this.state.gameId}/action`, {
        action_type: actionType, card_id: opts.cardId ?? null, attack_index: opts.attackIndex ?? null,
        bench_index: opts.benchIndex ?? null, energy_indices: opts.energyIndices ?? null, target: opts.target ?? null,
      }));
      this.patch({ gameState: res.state, isLoading: false,
        selectedCardId: null, selectedAttackIndex: null, selectedBenchIndex: null });
      this._syncLogsFromState(res.state);
      this._checkGameOver(res.state);
    } catch (e: any) {
      this.patch({ isLoading: false, error: e?.error?.detail ?? 'アクションに失敗しました' });
    }
  }

  async endTurn(): Promise<void> {
    if (!this.state.gameId) return;
    this.patch({ isLoading: true, error: null, isCpuThinking: true });
    try {
      const res: any = await firstValueFrom(this.http.post(`${this.baseUrl}/${this.state.gameId}/end_turn`, {}));
      this.patch({ gameState: res.state, isLoading: false, isCpuThinking: false,
        selectedCardId: null, selectedAttackIndex: null, selectedBenchIndex: null });
      this._syncLogsFromState(res.state);
      this._checkGameOver(res.state);
    } catch (e: any) {
      this.patch({ isLoading: false, isCpuThinking: false, error: e?.error?.detail ?? 'ターン終了に失敗しました' });
    }
  }

  async replaceActive(benchIndex: number): Promise<void> {
    if (!this.state.gameId) return;
    this.patch({ isLoading: true, error: null });
    try {
      const res: any = await firstValueFrom(this.http.post(`${this.baseUrl}/${this.state.gameId}/replace_active`, { bench_index: benchIndex }));
      this.patch({ gameState: res.state, isLoading: false });
      this._syncLogsFromState(res.state);
    } catch (e: any) {
      this.patch({ isLoading: false, error: e?.error?.detail ?? '交代に失敗しました' });
    }
  }

  selectCard(cardId: number): void {
    this.patch({ selectedCardId: this.state.selectedCardId === cardId ? null : cardId,
      selectedAttackIndex: null, selectedBenchIndex: null, error: null });
  }
  selectAttack(index: number): void {
    this.patch({ selectedAttackIndex: this.state.selectedAttackIndex === index ? null : index, selectedCardId: null });
  }
  selectBench(index: number): void {
    this.patch({ selectedBenchIndex: this.state.selectedBenchIndex === index ? null : index });
  }
  clearSelections(): void {
    this.patch({ selectedCardId: null, selectedAttackIndex: null, selectedBenchIndex: null, error: null });
  }
  resetGame(): void { this.uiState$.next(this._initialState()); }

  get player1(): PlayerState | null { return this.state.gameState?.player1 ?? null; }
  get player2(): PlayerState | null { return this.state.gameState?.player2 ?? null; }
  get isPlayerTurn(): boolean { return this.state.gameState?.current_player_id === 'player1'; }
  get needsReplacement(): boolean { const p1 = this.player1; return !!p1 && !p1.active_pokemon && p1.bench.length > 0; }
  get canAttack(): boolean {
    const gs = this.state.gameState;
    return this.isPlayerTurn && !!gs && !gs.attacked_this_turn && !gs.is_first_turn && !!this.player1?.active_pokemon;
  }
  get basicPokemonInHand(): HandCard[] {
    return (this.player1?.hand ?? []).filter(c => c.card_type === 'pokemon' && c.evolution_stage === 'たね');
  }

  private _syncLogsFromState(state: GameStateResponse): void {
    if (!state?.logs) return;
    const existing = new Set(this.state.logs);
    state.logs.forEach(l => {
      const msg = `[T${l.turn}] ${l.player_id === 'player1' ? '🧑' : '🤖'} ${l.action}${l.detail ? ': ' + l.detail : ''}`;
      if (!existing.has(msg)) { this.addLog(msg); existing.add(msg); }
    });
  }
  private _checkGameOver(state: GameStateResponse): void {
    if (state?.game_phase === 'game_over') this.patch({ screen: 'game-over' });
  }
}
EOF
echo "  ✅ src/app/game/services/game-api.service.ts"

# ============================================================
# frontend (game-board.component.ts)
# ============================================================
cat > "$P/src/app/components/game-board/game-board.component.ts" << 'EOF'
import { Component, OnInit, OnDestroy, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Subject, takeUntil } from 'rxjs';
import { GameApiService, GameUiState, ActivePokemon, HandCard } from '../../game/services/game-api.service';
import { DeckService } from '../../game/services/deck.service';

@Component({
  selector: 'game-board',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './game-board.component.html',
  styleUrl: './game-board.component.scss',
})
export class GameBoardComponent implements OnInit, OnDestroy {
  state: GameUiState | null = null;
  decks: any[] = [];
  selectedDeckId: number | null = null;
  private destroy$ = new Subject<void>();

  constructor(public gameApi: GameApiService, private deckService: DeckService, private cdr: ChangeDetectorRef) {}

  ngOnInit(): void {
    this.gameApi.state$.pipe(takeUntil(this.destroy$)).subscribe(state => {
      this.state = state; this.cdr.detectChanges(); this._scrollLogs();
    });
    this.loadDecks();
  }
  ngOnDestroy(): void { this.destroy$.next(); this.destroy$.complete(); }
  loadDecks(): void { this.deckService.getAllDecks().subscribe({ next: d => this.decks = d, error: () => this.decks = [] }); }

  async startGame(): Promise<void> { if (!this.selectedDeckId) return; await this.gameApi.startGame(this.selectedDeckId); }
  get firstPlayerLabel(): string { return this.state?.gameState?.first_player_id === 'player1' ? 'あなた' : 'CPU'; }
  get isPlayerFirst(): boolean { return this.state?.gameState?.first_player_id === 'player1'; }
  proceedToPlaceInitial(): void { this.gameApi.proceedToPlaceInitial(); }
  get basicPokemonInHand(): HandCard[] { return this.gameApi.basicPokemonInHand; }
  isInitialActive(cardId: number): boolean { return this.state?.initialActiveId === cardId; }
  isInitialBench(cardId: number): boolean { return this.state?.initialBenchIds.includes(cardId) ?? false; }
  toggleInitialActive(cardId: number): void { this.gameApi.toggleInitialActive(cardId); }
  toggleInitialBench(cardId: number): void {
    if (this.state?.initialActiveId === cardId) this.gameApi.toggleInitialActive(cardId);
    else this.gameApi.toggleInitialBench(cardId);
  }
  get canConfirmInitial(): boolean { return !!this.state?.initialActiveId && !this.state?.isLoading; }
  async confirmInitialPlacement(): Promise<void> { await this.gameApi.confirmInitialPlacement(); }
  selectHandCard(cardId: number): void { if (!this.gameApi.isPlayerTurn) return; this.gameApi.selectCard(cardId); }
  isHandCardSelected(cardId: number): boolean { return this.state?.selectedCardId === cardId; }
  get selectedHandCard(): HandCard | null {
    if (!this.state?.selectedCardId) return null;
    return this.gameApi.player1?.hand.find(c => c.card_id === this.state!.selectedCardId) ?? null;
  }
  get canPlaceActive(): boolean {
    const c = this.selectedHandCard;
    return !!c && c.card_type === 'pokemon' && c.evolution_stage === 'たね' && !this.gameApi.player1?.active_pokemon;
  }
  get canPlaceBench(): boolean {
    const c = this.selectedHandCard;
    return !!c && c.card_type === 'pokemon' && c.evolution_stage === 'たね' && (this.gameApi.player1?.bench ?? []).length < 5;
  }
  get canAttachEnergy(): boolean {
    const c = this.selectedHandCard; const p1 = this.gameApi.player1;
    if (!c || !p1 || p1.energy_attached_this_turn) return false;
    return c.card_type === 'energy' && (!!p1.active_pokemon || p1.bench.length > 0);
  }
  get canEvolveActive(): boolean {
    const c = this.selectedHandCard; const active = this.gameApi.player1?.active_pokemon;
    if (!c || !active || c.card_type !== 'pokemon') return false;
    return (c.evolution_stage === '1進化' || c.evolution_stage === '2進化') && c.evolves_from === active.name;
  }
  get canRetreat(): boolean {
    const p1 = this.gameApi.player1;
    if (!p1 || !this.gameApi.isPlayerTurn || p1.retreated_this_turn) return false;
    return !!p1.active_pokemon && p1.bench.length > 0;
  }
  async placeToActive(): Promise<void> { if (!this.state?.selectedCardId) return; await this.gameApi.sendAction('place_active', { cardId: this.state.selectedCardId }); }
  async placeToBench(): Promise<void> { if (!this.state?.selectedCardId) return; await this.gameApi.sendAction('place_bench', { cardId: this.state.selectedCardId }); }
  async attachEnergyToActive(): Promise<void> { if (!this.state?.selectedCardId) return; await this.gameApi.sendAction('attach_energy', { cardId: this.state.selectedCardId, target: 'active' }); }
  async attachEnergyToBench(benchIndex: number): Promise<void> { if (!this.state?.selectedCardId) return; await this.gameApi.sendAction('attach_energy', { cardId: this.state.selectedCardId, target: 'bench', benchIndex }); }
  async evolveActive(): Promise<void> { if (!this.state?.selectedCardId) return; await this.gameApi.sendAction('evolve_active', { cardId: this.state.selectedCardId }); }
  selectAttack(index: number): void { if (!this.gameApi.isPlayerTurn || !this.gameApi.canAttack) return; this.gameApi.selectAttack(index); }
  async executeAttack(): Promise<void> { if (this.state?.selectedAttackIndex == null) return; await this.gameApi.sendAction('attack', { attackIndex: this.state.selectedAttackIndex }); }
  async replaceFainted(benchIndex: number): Promise<void> { await this.gameApi.replaceActive(benchIndex); }
  async endTurn(): Promise<void> { await this.gameApi.endTurn(); }
  resetGame(): void { this.gameApi.resetGame(); this.selectedDeckId = null; }
  toggleBenchForEnergy(index: number): void { if (!this.gameApi.isPlayerTurn) return; this.gameApi.selectBench(index); }
  isBenchSelectedForEnergy(index: number): boolean { return this.state?.selectedBenchIndex === index; }

  getTypeColor(type: string | null): string {
    if (!type) return '#9E9E9E';
    const colors: Record<string, string> = { 草: '#4CAF50', 炎: '#FF5722', 水: '#2196F3', 雷: '#FFC107', 超: '#9C27B0', 闘: '#FF8F00', 悪: '#424242', 鋼: '#78909C', ドラゴン: '#1565C0', フェアリー: '#EC407A', 無色: '#9E9E9E' };
    return colors[type] ?? '#9E9E9E';
  }
  getTypeEmoji(type: string | null): string {
    if (!type) return '⭕';
    const emojis: Record<string, string> = { 草: '🌿', 炎: '🔥', 水: '💧', 雷: '⚡', 超: '🔮', 闘: '👊', 悪: '🌑', 鋼: '⚙️', ドラゴン: '🐉', フェアリー: '✨', 無色: '⭕' };
    return emojis[type] ?? '⭕';
  }
  getCardRuleLabel(rule: string | null): string { if (rule === 'ex') return 'EX'; if (rule === 'mega_ex') return 'MEGA EX'; return ''; }
  getPokemonTypeLabel(pt: string | null): string { return pt === 'trainer_pokemon' ? 'トレーナーポケモン' : ''; }
  hpPercent(pokemon: ActivePokemon): number { if (!pokemon.hp) return 100; return Math.max(0, Math.min(100, (pokemon.current_hp / pokemon.hp) * 100)); }
  hpBarClass(pokemon: ActivePokemon): string { const p = this.hpPercent(pokemon); return p > 50 ? 'hp-high' : p > 25 ? 'hp-mid' : 'hp-low'; }
  get turnLabel(): string { if (!this.state?.gameState) return ''; return this.gameApi.isPlayerTurn ? 'あなたのターン' : (this.state.isCpuThinking ? 'CPUが考え中…' : 'CPUのターン'); }
  get phaseLabel(): string { const p = this.state?.gameState?.turn_phase; const m: Record<string, string> = { draw: 'ドロー', main: 'メイン', attack: '攻撃後', end: '終了' }; return p ? (m[p] ?? p) : ''; }
  get needsReplacement(): boolean { return this.gameApi.needsReplacement; }
  private _scrollLogs(): void { setTimeout(() => { const el = document.getElementById('game-logs'); if (el) el.scrollTop = el.scrollHeight; }, 50); }
}
EOF
echo "  ✅ src/app/components/game-board/game-board.component.ts"

# ============================================================
# frontend (game-board.component.html) - 別ファイルから読み込む方式
# ============================================================
cat > "$P/src/app/components/game-board/game-board.component.html" << 'HTMLEOF'
<div class="game-wrapper">
  @if (state?.screen === 'deck-select') {
    <div class="screen deck-select-screen">
      <div class="title-area">
        <div class="pokeball-deco"></div>
        <h1 class="game-title">POKÉMON TCG</h1>
        <p class="game-subtitle">CPU バトル</p>
      </div>
      <div class="deck-select-card">
        <h2 class="section-title">デッキを選択</h2>
        @if (decks.length === 0) { <p class="no-deck-msg">デッキが見つかりません。<br>先にデッキを作成してください。</p> }
        <div class="deck-list">
          @for (deck of decks; track deck.id) {
            <div class="deck-item" [class.selected]="selectedDeckId === deck.id" (click)="selectedDeckId = deck.id">
              <span class="deck-icon">🃏</span>
              <div class="deck-info"><span class="deck-name">{{ deck.name }}</span><span class="deck-count">{{ deck.card_count ?? '?' }} 枚</span></div>
              @if (selectedDeckId === deck.id) { <span class="check-mark">✓</span> }
            </div>
          }
        </div>
        @if (state?.error) { <p class="error-msg">⚠️ {{ state!.error }}</p> }
        <button class="btn-start" [disabled]="!selectedDeckId || state?.isLoading" (click)="startGame()">
          @if (state?.isLoading) { 準備中… } @else { バトル開始！ }
        </button>
      </div>
    </div>
  }

  @if (state?.screen === 'coin-toss') {
    <div class="screen coin-toss-screen">
      <div class="coin-toss-card">
        <div class="coin-icon">🪙</div>
        <h2 class="coin-result-title">コイントス結果</h2>
        <div class="coin-result-badge" [class.player-first]="isPlayerFirst" [class.cpu-first]="!isPlayerFirst">{{ firstPlayerLabel }}が先行！</div>
        @if (state?.gameState?.mulligan_info; as m) {
          @if (m.player1_mulligans > 0 || m.player2_mulligans > 0) {
            <div class="mulligan-info">
              <p class="mulligan-title">マリガン情報</p>
              @if (m.player1_mulligans > 0) { <p>🔄 あなた: {{ m.player1_mulligans }}回マリガン</p> }
              @if (m.player2_mulligans > 0) { <p>🔄 CPU: {{ m.player2_mulligans }}回マリガン</p><p class="mulligan-bonus">✨ あなたは{{ m.player2_mulligans }}枚追加ドロー済み</p> }
            </div>
          }
        }
        <p class="coin-sub">手札からたねポケモンを選んで配置してください</p>
        <button class="btn-start" (click)="proceedToPlaceInitial()">ポケモンを配置する →</button>
      </div>
    </div>
  }

  @if (state?.screen === 'place-initial') {
    <div class="screen place-initial-screen">
      <h2 class="section-title">初期ポケモンを選択</h2>
      <div class="place-guide">
        <div class="guide-step" [class.done]="!!state?.initialActiveId">
          <span class="guide-num">1</span><span>バトル場に出すポケモンを選択（必須）</span>
          @if (state?.initialActiveId) { <span class="guide-check">✓</span> }
        </div>
        <div class="guide-step">
          <span class="guide-num">2</span><span>ベンチに出すポケモンを選択（任意・最大5体）</span>
          <span class="guide-count">{{ state?.initialBenchIds?.length ?? 0 }}/5</span>
        </div>
      </div>
      <div class="initial-hand">
        @for (card of basicPokemonInHand; track card.card_id) {
          <div class="init-card" [class.active-selected]="isInitialActive(card.card_id)" [class.bench-selected]="isInitialBench(card.card_id)"
            (click)="isInitialActive(card.card_id) ? toggleInitialActive(card.card_id) : (state?.initialActiveId ? toggleInitialBench(card.card_id) : toggleInitialActive(card.card_id))">
            @if (card.image_url) { <img class="init-card-img" [src]="card.image_url" [alt]="card.name" /> }
            @else { <div class="init-card-type-bar" [style.background]="getTypeColor(card.type)"></div><span class="init-card-emoji">{{ getTypeEmoji(card.type) }}</span> }
            <span class="init-card-name">{{ card.name }}</span>
            @if (getPokemonTypeLabel(card.pokemon_type)) { <span class="trainer-badge">{{ getPokemonTypeLabel(card.pokemon_type) }}</span> }
            @if (isInitialActive(card.card_id)) { <span class="badge badge-active">バトル場</span> }
            @else if (isInitialBench(card.card_id)) { <span class="badge badge-bench">ベンチ</span> }
          </div>
        }
        @if (basicPokemonInHand.length === 0) { <p class="no-basic-msg">たねポケモンが手札にありません</p> }
      </div>
      @if (state?.error) { <p class="error-msg">⚠️ {{ state!.error }}</p> }
      <button class="btn-start" [disabled]="!canConfirmInitial" (click)="confirmInitialPlacement()">
        @if (state?.isLoading) { 配置中… } @else { 配置を確定する }
      </button>
    </div>
  }

  @if (state?.screen === 'battle' && state?.gameState) {
    <div class="screen battle-screen">
      <div class="top-bar">
        <div class="turn-badge" [class.player-turn]="gameApi.isPlayerTurn" [class.cpu-turn]="!gameApi.isPlayerTurn">
          <span class="turn-label">{{ turnLabel }}</span><span class="turn-count">ターン {{ state!.gameState!.current_turn }}</span>
        </div>
        <div class="phase-badge">{{ phaseLabel }}</div>
        @if (state!.gameState!.is_first_turn) { <div class="first-turn-badge">先攻1ターン目は攻撃不可</div> }
        <button class="btn-reset-sm" (click)="resetGame()">終了</button>
      </div>
      @if (state?.isCpuThinking) { <div class="cpu-thinking-overlay"><div class="thinking-spinner"></div><span>CPUが考え中…</span></div> }
      @if (needsReplacement) {
        <div class="replacement-banner">
          <p>⚠️ バトルポケモンがきぜつ！ベンチから選んでください</p>
          <div class="bench-replace-list">
            @for (b of gameApi.player1!.bench; track $index) {
              <button class="btn-bench-replace" (click)="replaceFainted($index)">{{ b.name }} (HP {{ b.current_hp }}/{{ b.hp }})</button>
            }
          </div>
        </div>
      }
      <div class="field">
        <div class="field-half cpu-half">
          <div class="half-label cpu-label">CPU</div>
          <div class="player-info-row">
            <span class="info-chip">🃏 {{ gameApi.player2?.deck_count }}枚</span>
            <span class="info-chip">🤚 {{ gameApi.player2?.hand_count }}枚</span>
            <span class="info-chip prize-chip">⭐ {{ gameApi.player2?.prize_remaining }}枚</span>
          </div>
          <div class="bench-row cpu-bench">
            @for (b of gameApi.player2?.bench; track $index) {
              <div class="bench-card">
                <div class="bench-type-dot" [style.background]="getTypeColor(b.type)"></div>
                <span class="bench-name">{{ b.name }}</span>
                @if (b.card_rule) { <span class="rule-pip">{{ getCardRuleLabel(b.card_rule) }}</span> }
                <div class="bench-hp-bar"><div class="bench-hp-fill" [class]="hpBarClass(b)" [style.width.%]="hpPercent(b)"></div></div>
                <span class="bench-hp-text">{{ b.current_hp }}/{{ b.hp }}</span>
                <span class="bench-energy">⚡{{ b.attached_energy.length }}</span>
              </div>
            }
            @if (!gameApi.player2?.bench?.length) { <div class="empty-bench">ベンチなし</div> }
          </div>
          <div class="active-zone">
            @if (gameApi.player2?.active_pokemon; as ap) {
              <div class="active-card" [style.border-color]="getTypeColor(ap.type)">
                @if (ap.image_url) { <img class="active-img" [src]="ap.image_url" [alt]="ap.name" /> }
                <div class="active-type-bar" [style.background]="getTypeColor(ap.type)">
                  <span>{{ getTypeEmoji(ap.type) }} {{ ap.type }}</span>
                  @if (ap.card_rule) { <span class="rule-badge">{{ getCardRuleLabel(ap.card_rule) }}</span> }
                  @if (ap.pokemon_type === 'trainer_pokemon') { <span class="trainer-pip">T</span> }
                </div>
                <div class="active-name">{{ ap.name }}</div>
                <div class="active-stage">{{ ap.evolution_stage }}</div>
                <div class="hp-section">
                  <div class="hp-numbers">{{ ap.current_hp }} / {{ ap.hp }} HP</div>
                  <div class="hp-bar-bg"><div class="hp-bar-fill" [class]="hpBarClass(ap)" [style.width.%]="hpPercent(ap)"></div></div>
                </div>
                <div class="energy-row">
                  @for (e of ap.attached_energy; track $index) { <span class="energy-dot">⚡</span> }
                  @if (!ap.attached_energy.length) { <span class="no-energy">エネルギーなし</span> }
                </div>
              </div>
            } @else { <div class="empty-active">バトル場空</div> }
          </div>
        </div>
        <div class="vs-divider"><span class="vs-text">VS</span></div>
        <div class="field-half player-half">
          <div class="half-label player-label">あなた</div>
          <div class="player-info-row">
            <span class="info-chip">🃏 {{ gameApi.player1?.deck_count }}枚</span>
            <span class="info-chip prize-chip">⭐ {{ gameApi.player1?.prize_remaining }}枚</span>
          </div>
          <div class="active-zone">
            @if (gameApi.player1?.active_pokemon; as ap) {
              <div class="active-card player-active" [style.border-color]="getTypeColor(ap.type)">
                @if (ap.image_url) { <img class="active-img" [src]="ap.image_url" [alt]="ap.name" /> }
                <div class="active-type-bar" [style.background]="getTypeColor(ap.type)">
                  <span>{{ getTypeEmoji(ap.type) }} {{ ap.type }}</span>
                  @if (ap.card_rule) { <span class="rule-badge">{{ getCardRuleLabel(ap.card_rule) }}</span> }
                  @if (ap.pokemon_type === 'trainer_pokemon') { <span class="trainer-pip">T</span> }
                </div>
                <div class="active-name">{{ ap.name }}</div>
                <div class="active-stage">{{ ap.evolution_stage }}</div>
                <div class="hp-section">
                  <div class="hp-numbers">{{ ap.current_hp }} / {{ ap.hp }} HP</div>
                  <div class="hp-bar-bg"><div class="hp-bar-fill" [class]="hpBarClass(ap)" [style.width.%]="hpPercent(ap)"></div></div>
                </div>
                <div class="energy-row">
                  @for (e of ap.attached_energy; track $index) { <span class="energy-dot">⚡</span> }
                  @if (!ap.attached_energy.length) { <span class="no-energy">エネルギーなし</span> }
                </div>
                @if (ap.ability) { <div class="ability-row"><span class="ability-label">特性</span><span class="ability-name">{{ ap.ability.name }}</span></div> }
                @if (gameApi.isPlayerTurn && gameApi.canAttack) {
                  <div class="attacks-list">
                    @for (atk of ap.attacks; track $index) {
                      <div class="attack-row" [class.selected-attack]="state!.selectedAttackIndex === $index" (click)="selectAttack($index)">
                        <div class="atk-cost">@for (e of atk.energy; track $index) { <span class="atk-pip">⚡</span> }</div>
                        <span class="atk-name">{{ atk.name }}</span>
                        <span class="atk-dmg">{{ atk.damage > 0 ? atk.damage + '点' : '効果' }}</span>
                      </div>
                    }
                  </div>
                }
              </div>
            } @else {
              <div class="empty-active player-empty"><span>バトル場空</span><span class="hint-sm">手札からたねポケモンを出してください</span></div>
            }
          </div>
          <div class="bench-row player-bench">
            @for (b of gameApi.player1?.bench; track $index) {
              <div class="bench-card player-bench-card" [class.bench-energy-target]="isBenchSelectedForEnergy($index)" (click)="toggleBenchForEnergy($index)">
                <div class="bench-type-dot" [style.background]="getTypeColor(b.type)"></div>
                <span class="bench-name">{{ b.name }}</span>
                @if (b.card_rule) { <span class="rule-pip">{{ getCardRuleLabel(b.card_rule) }}</span> }
                <div class="bench-hp-bar"><div class="bench-hp-fill" [class]="hpBarClass(b)" [style.width.%]="hpPercent(b)"></div></div>
                <span class="bench-hp-text">{{ b.current_hp }}/{{ b.hp }}</span>
                <span class="bench-energy">⚡{{ b.attached_energy.length }}</span>
              </div>
            }
            @if (!gameApi.player1?.bench?.length) { <div class="empty-bench">ベンチなし</div> }
          </div>
        </div>
      </div>
      <div class="hand-area">
        <div class="hand-header">
          <h3 class="hand-title">手札（{{ gameApi.player1?.hand?.length ?? 0 }}枚）</h3>
          @if (state?.selectedCardId) { <button class="btn-clear" (click)="gameApi.clearSelections()">選択解除</button> }
        </div>
        <div class="hand-cards">
          @for (card of gameApi.player1?.hand; track card.card_id) {
            <div class="hand-card" [class.selected]="isHandCardSelected(card.card_id)" [class.energy-card]="card.card_type === 'energy'" [class.trainer-card]="card.card_type === 'trainer'" [style.--card-color]="getTypeColor(card.type)" (click)="selectHandCard(card.card_id)">
              <div class="hand-card-bar" [style.background]="getTypeColor(card.type)"></div>
              @if (card.image_url) { <img class="hand-card-img" [src]="card.image_url" [alt]="card.name" /> }
              @else { <span class="hand-card-emoji">{{ getTypeEmoji(card.type) }}</span> }
              <span class="hand-card-name">{{ card.name }}</span>
              @if (card.card_type === 'pokemon' && card.evolution_stage) { <span class="hand-card-stage">{{ card.evolution_stage }}</span> }
              @if (card.card_type === 'energy') { <span class="hand-card-stage">{{ card.energy_type === 'basic' ? '基本' : '特殊' }}エネ</span> }
              @if (card.card_type === 'trainer') { <span class="hand-card-stage">{{ card.trainer_type }}{{ card.is_ace_spec ? ' ★' : '' }}</span> }
            </div>
          }
        </div>
      </div>
      @if (gameApi.isPlayerTurn && !state?.isCpuThinking) {
        <div class="action-panel">
          @if (state?.error) { <div class="action-error">⚠️ {{ state!.error }}</div> }
          <div class="action-buttons">
            @if (canPlaceActive) { <button class="btn-action btn-place" (click)="placeToActive()">🏟️ バトル場に出す</button> }
            @if (canPlaceBench) { <button class="btn-action btn-bench" (click)="placeToBench()">🪑 ベンチに出す</button> }
            @if (canAttachEnergy) {
              @if (gameApi.player1?.active_pokemon && state?.selectedBenchIndex == null) { <button class="btn-action btn-energy" (click)="attachEnergyToActive()">⚡ アクティブに付ける</button> }
              @if (state?.selectedBenchIndex != null) { <button class="btn-action btn-energy" (click)="attachEnergyToBench(state!.selectedBenchIndex!)">⚡ ベンチ{{ state!.selectedBenchIndex! + 1 }}に付ける</button> }
            }
            @if (canEvolveActive) { <button class="btn-action btn-evolve" (click)="evolveActive()">🌟 進化する</button> }
            @if (state?.selectedAttackIndex != null) { <button class="btn-action btn-attack" (click)="executeAttack()">⚔️ ワザを使う！</button> }
            <button class="btn-end-turn" (click)="endTurn()">ターン終了 →</button>
          </div>
        </div>
      }
      <div class="log-panel" id="game-logs">
        <div class="log-header">バトルログ</div>
        <div class="log-body">
          @for (log of state?.logs; track $index) { <p class="log-entry">{{ log }}</p> }
        </div>
      </div>
    </div>
  }

  @if (state?.screen === 'game-over') {
    <div class="screen game-over-screen">
      <div class="game-over-card">
        <div class="game-over-icon">{{ state!.gameState?.winner_id === 'player1' ? '🏆' : '💀' }}</div>
        <h2 class="game-over-title">{{ state!.gameState?.winner_id === 'player1' ? 'あなたの勝利！' : 'CPUの勝利…' }}</h2>
        <p class="game-over-sub">{{ state!.gameState?.current_turn }} ターンのバトル</p>
        <div class="game-over-logs">
          @for (log of state?.logs?.slice(-5); track $index) { <p class="game-over-log">{{ log }}</p> }
        </div>
        <button class="btn-start" (click)="resetGame()">もう一度プレイ</button>
      </div>
    </div>
  }
</div>
HTMLEOF
echo "  ✅ src/app/components/game-board/game-board.component.html"

# ============================================================
# frontend (game-board.component.scss)
# ============================================================
cat > "$P/src/app/components/game-board/game-board.component.scss" << 'SCSSEOF'
@import url('https://fonts.googleapis.com/css2?family=Bangers&family=M+PLUS+Rounded+1c:wght@400;700;800&display=swap');
:host { --bg:#0d1117;--surface:#161b22;--surface2:#21262d;--border:#30363d;--text:#e6edf3;--muted:#8b949e;--accent:#f9c613;--accent2:#e25c1a;--player:#2563eb;--cpu:#dc2626;--hp-high:#22c55e;--hp-mid:#f59e0b;--hp-low:#ef4444;--energy:#a78bfa;--radius:12px;--radius-sm:6px;font-family:'M PLUS Rounded 1c',sans-serif;color:var(--text); }
.game-wrapper { min-height:100vh;background:var(--bg);position:relative; &::before { content:'';position:fixed;inset:0;background:radial-gradient(ellipse at 20% 20%,rgba(37,99,235,.08) 0%,transparent 60%),radial-gradient(ellipse at 80% 80%,rgba(220,38,38,.08) 0%,transparent 60%);pointer-events:none;z-index:0; } }
.screen { position:relative;z-index:1;min-height:100vh;padding:24px;box-sizing:border-box; }
.deck-select-screen { display:flex;flex-direction:column;align-items:center;justify-content:center;gap:40px; }
.title-area { text-align:center; }
.pokeball-deco { width:80px;height:80px;border-radius:50%;background:linear-gradient(180deg,var(--accent2) 50%,#fff 50%);border:4px solid var(--border);margin:0 auto 16px;position:relative;box-shadow:0 0 40px rgba(249,198,19,.3);animation:spin 3s linear infinite; &::after { content:'';position:absolute;width:20px;height:20px;border-radius:50%;background:#fff;border:4px solid var(--border);top:50%;left:50%;transform:translate(-50%,-50%); } }
@keyframes spin { to { transform:rotate(360deg); } }
@keyframes bounce { 0%,100% { transform:translateY(0); } 50% { transform:translateY(-16px); } }
@keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:.5; } }
.game-title { font-family:'Bangers',cursive;font-size:56px;letter-spacing:4px;color:var(--accent);text-shadow:4px 4px 0 var(--accent2),8px 8px 0 rgba(0,0,0,.5);margin:0; }
.game-subtitle { font-size:18px;color:var(--muted);margin:8px 0 0;letter-spacing:6px;text-transform:uppercase; }
.deck-select-card { background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:32px;width:100%;max-width:480px; }
.section-title { font-size:20px;font-weight:800;margin:0 0 20px; }
.deck-list { display:flex;flex-direction:column;gap:10px;margin-bottom:24px; }
.deck-item { display:flex;align-items:center;gap:12px;padding:14px 16px;border-radius:var(--radius-sm);border:2px solid var(--border);background:var(--surface2);cursor:pointer;transition:all .2s; &:hover { border-color:var(--accent); } &.selected { border-color:var(--accent);background:rgba(249,198,19,.1); } }
.deck-icon { font-size:24px; } .deck-info { flex:1;display:flex;flex-direction:column; } .deck-name { font-weight:700; } .deck-count { font-size:12px;color:var(--muted); } .check-mark { color:var(--accent);font-weight:700;font-size:20px; }
.no-deck-msg { color:var(--muted);text-align:center;margin-bottom:20px;line-height:1.6; }
.btn-start { width:100%;padding:16px;border-radius:var(--radius);border:none;background:linear-gradient(135deg,var(--accent),var(--accent2));color:#000;font-family:inherit;font-size:18px;font-weight:800;cursor:pointer;transition:all .2s;box-shadow:0 4px 20px rgba(249,198,19,.3); &:hover:not(:disabled) { transform:translateY(-2px);box-shadow:0 8px 30px rgba(249,198,19,.5); } &:disabled { opacity:.4;cursor:not-allowed; } }
.coin-toss-screen { display:flex;align-items:center;justify-content:center; }
.coin-toss-card { background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:48px 40px;max-width:440px;width:100%;text-align:center; }
.coin-icon { font-size:72px;margin-bottom:16px;animation:bounce .6s ease-in-out 3; }
.coin-result-title { font-size:18px;color:var(--muted);margin:0 0 16px; }
.coin-result-badge { font-family:'Bangers',cursive;font-size:40px;letter-spacing:2px;padding:12px 24px;border-radius:var(--radius);margin-bottom:24px; &.player-first { background:rgba(37,99,235,.2);border:2px solid var(--player);color:#60a5fa; } &.cpu-first { background:rgba(220,38,38,.2);border:2px solid var(--cpu);color:#f87171; } }
.mulligan-info { background:var(--surface2);border:1px solid var(--border);border-radius:var(--radius-sm);padding:12px 16px;margin-bottom:20px;text-align:left;font-size:13px; }
.mulligan-title { font-weight:700;margin-bottom:6px;color:var(--accent); } .mulligan-bonus { color:#4ade80;font-weight:700; } .coin-sub { color:var(--muted);font-size:14px;margin-bottom:24px; }
.place-initial-screen { max-width:860px;margin:0 auto; }
.place-guide { display:flex;flex-direction:column;gap:8px;margin-bottom:24px; }
.guide-step { display:flex;align-items:center;gap:10px;font-size:14px;padding:10px 16px;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-sm); &.done { border-color:#22c55e;background:rgba(34,197,94,.05); } }
.guide-num { width:24px;height:24px;border-radius:50%;background:var(--accent);color:#000;font-weight:800;display:flex;align-items:center;justify-content:center;font-size:13px;flex-shrink:0; }
.guide-check { color:#4ade80;font-weight:700;margin-left:auto; } .guide-count { margin-left:auto;color:var(--muted);font-size:13px; }
.initial-hand { display:flex;flex-wrap:wrap;gap:12px;margin-bottom:20px; }
.init-card { width:120px;padding:10px;border-radius:var(--radius);border:2px solid var(--border);background:var(--surface);cursor:pointer;display:flex;flex-direction:column;align-items:center;gap:6px;transition:all .2s; &.active-selected { border-color:var(--player);background:rgba(37,99,235,.15);box-shadow:0 0 20px rgba(37,99,235,.3); } &.bench-selected { border-color:#22c55e;background:rgba(34,197,94,.1); } }
.init-card-img { width:100%;border-radius:6px; } .init-card-type-bar { width:100%;height:4px;border-radius:2px; } .init-card-emoji { font-size:28px;margin-top:4px; } .init-card-name { font-size:12px;font-weight:700;text-align:center; }
.trainer-badge { font-size:9px;padding:2px 6px;border-radius:999px;background:rgba(249,198,19,.2);color:var(--accent);border:1px solid rgba(249,198,19,.4); }
.badge { font-size:10px;padding:2px 8px;border-radius:999px;font-weight:700; &.badge-active { background:var(--player);color:#fff; } &.badge-bench { background:#22c55e;color:#000; } }
.no-basic-msg { color:var(--muted);padding:20px; }
.battle-screen { display:flex;flex-direction:column;gap:12px;padding:16px; }
.top-bar { display:flex;align-items:center;gap:10px;padding:10px 16px;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius); }
.turn-badge { display:flex;align-items:center;gap:8px;padding:6px 14px;border-radius:999px;font-weight:700;font-size:13px; &.player-turn { background:rgba(37,99,235,.2);border:1px solid var(--player);color:#60a5fa; } &.cpu-turn { background:rgba(220,38,38,.2);border:1px solid var(--cpu);color:#f87171; } }
.turn-count { font-size:11px;opacity:.7; } .phase-badge { font-size:12px;color:var(--muted); }
.first-turn-badge { font-size:11px;padding:4px 10px;border-radius:999px;background:rgba(249,198,19,.15);border:1px solid rgba(249,198,19,.4);color:var(--accent); }
.btn-reset-sm { margin-left:auto;padding:6px 14px;border-radius:var(--radius-sm);border:1px solid var(--border);background:transparent;color:var(--muted);cursor:pointer;font-size:12px; &:hover { border-color:#ef4444;color:#ef4444; } }
.cpu-thinking-overlay { display:flex;align-items:center;gap:10px;padding:10px 16px;background:rgba(220,38,38,.1);border:1px solid rgba(220,38,38,.3);border-radius:var(--radius);color:#f87171;font-weight:700;animation:pulse 1.5s ease-in-out infinite; }
.thinking-spinner { width:18px;height:18px;border:3px solid rgba(220,38,38,.3);border-top-color:var(--cpu);border-radius:50%;animation:spin .8s linear infinite; }
.replacement-banner { padding:14px 16px;background:rgba(249,198,19,.1);border:2px solid var(--accent);border-radius:var(--radius);text-align:center;font-weight:700;color:var(--accent); }
.bench-replace-list { display:flex;gap:8px;justify-content:center;flex-wrap:wrap;margin-top:10px; }
.btn-bench-replace { padding:8px 14px;border-radius:var(--radius-sm);border:1px solid var(--accent);background:rgba(249,198,19,.15);color:var(--accent);font-family:inherit;font-weight:700;cursor:pointer;font-size:13px; &:hover { background:rgba(249,198,19,.3); } }
.field { display:grid;grid-template-columns:1fr auto 1fr;gap:16px;align-items:center; }
.field-half { display:flex;flex-direction:column;gap:10px; } .cpu-half { flex-direction:column-reverse; }
.half-label { font-size:12px;font-weight:800;letter-spacing:2px;text-transform:uppercase;opacity:.7; } .cpu-label { color:var(--cpu); } .player-label { color:var(--player); }
.player-info-row { display:flex;gap:6px;flex-wrap:wrap; }
.info-chip { font-size:11px;padding:3px 8px;border-radius:999px;background:var(--surface2);border:1px solid var(--border);color:var(--muted); } .prize-chip { color:var(--accent);border-color:rgba(249,198,19,.3); }
.vs-divider { display:flex;align-items:center;justify-content:center; } .vs-text { font-family:'Bangers',cursive;font-size:40px;color:var(--accent);text-shadow:2px 2px 0 var(--accent2); }
.active-zone { min-height:180px; }
.active-card { border:3px solid;border-radius:var(--radius);background:var(--surface);overflow:hidden; }
.active-img { width:100%;max-height:100px;object-fit:contain;background:var(--surface2); }
.active-type-bar { display:flex;align-items:center;gap:6px;padding:6px 10px;font-size:12px;font-weight:700;color:#fff;text-shadow:0 1px 3px rgba(0,0,0,.5); }
.rule-badge { font-size:10px;padding:1px 6px;border-radius:4px;background:rgba(0,0,0,.4);margin-left:auto; }
.trainer-pip { font-size:10px;padding:1px 5px;border-radius:4px;background:rgba(249,198,19,.3);color:var(--accent); }
.active-name { font-size:18px;font-weight:800;padding:8px 10px 2px; } .active-stage { font-size:11px;color:var(--muted);padding:0 10px 6px; }
.hp-section { padding:4px 10px 8px; } .hp-numbers { font-size:13px;font-weight:700;margin-bottom:4px; }
.hp-bar-bg { height:7px;background:var(--surface2);border-radius:4px;overflow:hidden; }
.hp-bar-fill { height:100%;border-radius:4px;transition:width .5s ease; &.hp-high { background:var(--hp-high); } &.hp-mid { background:var(--hp-mid); } &.hp-low { background:var(--hp-low);animation:pulse 1s infinite; } }
.energy-row { display:flex;flex-wrap:wrap;gap:3px;padding:0 10px 8px; } .energy-dot { font-size:14px; } .no-energy { font-size:11px;color:var(--muted); }
.ability-row { display:flex;align-items:center;gap:6px;padding:4px 10px 6px;border-top:1px solid var(--border); }
.ability-label { font-size:10px;padding:2px 6px;border-radius:4px;background:rgba(34,197,94,.2);color:#4ade80;border:1px solid rgba(34,197,94,.4);font-weight:700; } .ability-name { font-size:12px;font-weight:700; }
.attacks-list { border-top:1px solid var(--border); }
.attack-row { display:flex;align-items:center;gap:6px;padding:8px 10px;cursor:pointer;transition:background .15s; &:hover { background:rgba(244,63,94,.1); } &.selected-attack { background:rgba(244,63,94,.2);border-left:3px solid #f43f5e; } }
.atk-cost { display:flex;gap:2px;min-width:24px; } .atk-pip { font-size:11px; } .atk-name { flex:1;font-weight:700;font-size:13px; } .atk-dmg { font-size:13px;color:#f43f5e;font-weight:700; }
.empty-active { border:2px dashed var(--border);border-radius:var(--radius);display:flex;flex-direction:column;align-items:center;justify-content:center;gap:6px;min-height:140px;color:var(--muted);font-size:13px; }
.player-empty { border-color:rgba(37,99,235,.3);color:rgba(37,99,235,.7); } .hint-sm { font-size:11px;opacity:.7; }
.bench-row { display:flex;gap:6px;flex-wrap:wrap; }
.bench-card { flex:1;min-width:70px;max-width:100px;padding:7px;border-radius:var(--radius-sm);background:var(--surface2);border:1px solid var(--border);display:flex;flex-direction:column;gap:3px;font-size:11px; }
.player-bench-card { cursor:pointer;transition:border-color .15s; &:hover { border-color:var(--muted); } &.bench-energy-target { border-color:var(--energy);background:rgba(167,139,250,.1); } }
.bench-type-dot { width:8px;height:8px;border-radius:50%; } .bench-name { font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis; }
.rule-pip { font-size:9px;padding:1px 4px;border-radius:3px;background:rgba(249,198,19,.2);color:var(--accent);width:fit-content; }
.bench-hp-bar { height:3px;background:var(--surface);border-radius:2px;overflow:hidden; }
.bench-hp-fill { height:100%;border-radius:2px; &.hp-high { background:var(--hp-high); } &.hp-mid { background:var(--hp-mid); } &.hp-low { background:var(--hp-low); } }
.bench-hp-text { font-size:10px;color:var(--muted); } .bench-energy { font-size:10px;color:var(--energy); } .empty-bench { font-size:11px;color:var(--muted);padding:6px; }
.hand-area { background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:12px; }
.hand-header { display:flex;align-items:center;justify-content:space-between;margin-bottom:10px; } .hand-title { font-size:13px;font-weight:700;margin:0; }
.btn-clear { font-size:12px;padding:4px 10px;border-radius:var(--radius-sm);border:1px solid var(--border);background:transparent;color:var(--muted);cursor:pointer; &:hover { color:var(--text); } }
.hand-cards { display:flex;gap:6px;overflow-x:auto;padding-bottom:4px; &::-webkit-scrollbar { height:3px; } &::-webkit-scrollbar-thumb { background:var(--border);border-radius:2px; } }
.hand-card { min-width:80px;padding:8px 6px;border-radius:var(--radius-sm);border:2px solid var(--border);background:var(--surface2);cursor:pointer;display:flex;flex-direction:column;align-items:center;gap:4px;transition:all .2s;flex-shrink:0;position:relative;overflow:hidden; &:hover { border-color:var(--muted);transform:translateY(-4px); } &.selected { border-color:var(--accent);background:rgba(249,198,19,.1);transform:translateY(-8px);box-shadow:0 8px 20px rgba(249,198,19,.2); } &.energy-card { border-style:dashed; } &.trainer-card { border-color:rgba(167,139,250,.4); } }
.hand-card-bar { position:absolute;top:0;left:0;right:0;height:3px; } .hand-card-img { width:100%;border-radius:4px;margin-top:4px; } .hand-card-emoji { font-size:20px;margin-top:6px; }
.hand-card-name { font-size:10px;font-weight:700;text-align:center;line-height:1.3; } .hand-card-stage { font-size:9px;color:var(--muted); }
.action-panel { background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:12px; }
.action-error { font-size:12px;color:#f87171;background:rgba(239,68,68,.1);border:1px solid rgba(239,68,68,.3);border-radius:var(--radius-sm);padding:6px 10px;margin-bottom:8px; }
.action-buttons { display:flex;flex-wrap:wrap;gap:6px;align-items:center; }
.btn-action { padding:7px 14px;border-radius:var(--radius-sm);border:1px solid;font-family:inherit;font-size:12px;font-weight:700;cursor:pointer;transition:all .15s; &:hover { transform:translateY(-1px); } &.btn-place { background:rgba(37,99,235,.15);border-color:var(--player);color:#60a5fa; } &.btn-bench { background:rgba(34,197,94,.15);border-color:#22c55e;color:#4ade80; } &.btn-energy { background:rgba(167,139,250,.15);border-color:var(--energy);color:#c4b5fd; } &.btn-evolve { background:rgba(249,198,19,.15);border-color:var(--accent);color:var(--accent); } &.btn-attack { background:rgba(244,63,94,.2);border-color:#f43f5e;color:#fb7185;animation:pulse 1s infinite; } }
.btn-end-turn { margin-left:auto;padding:7px 18px;border-radius:var(--radius-sm);border:1px solid var(--border);background:var(--surface2);color:var(--text);font-family:inherit;font-size:12px;font-weight:700;cursor:pointer; &:hover { border-color:var(--accent);color:var(--accent); } }
.log-panel { background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);max-height:140px;display:flex;flex-direction:column;overflow:hidden; }
.log-header { font-size:11px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:var(--muted);padding:6px 12px;border-bottom:1px solid var(--border);background:var(--surface2); }
.log-body { overflow-y:auto;padding:6px 12px;flex:1; &::-webkit-scrollbar { width:3px; } &::-webkit-scrollbar-thumb { background:var(--border);border-radius:2px; } }
.log-entry { font-size:11px;color:var(--muted);margin:0 0 3px;line-height:1.4; &:last-child { color:var(--text); } }
.game-over-screen { display:flex;align-items:center;justify-content:center; }
.game-over-card { text-align:center;padding:48px 40px;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);max-width:400px;width:100%; }
.game-over-icon { font-size:72px;margin-bottom:12px;animation:bounce .6s ease-in-out; }
.game-over-title { font-family:'Bangers',cursive;font-size:44px;letter-spacing:3px;color:var(--accent);text-shadow:3px 3px 0 var(--accent2);margin:0 0 6px; }
.game-over-sub { color:var(--muted);margin-bottom:16px; }
.game-over-logs { background:var(--surface2);border-radius:var(--radius-sm);padding:10px 14px;margin-bottom:24px;text-align:left; } .game-over-log { font-size:11px;color:var(--muted);margin:0 0 3px; }
.error-msg { font-size:12px;color:#f87171;margin-bottom:10px; }
SCSSEOF
echo "  ✅ src/app/components/game-board/game-board.component.scss"

echo ""
echo "============================================"
echo "✅ 全ファイルの生成が完了しました！"
echo "============================================"
echo ""
echo "📋 次のステップ:"
echo "   1. マイグレーション実行:"
echo "      cd $P/backend && python scripts/migrate_cards.py"
echo "   2. 初期デッキ作成:"
echo "      cd $P/backend && python scripts/create_initial_deck.py"
echo "   3. バックエンド再起動:"
echo "      cd $P/backend && uvicorn main:app --reload"
echo "   4. フロントエンド確認:"
echo "      cd $P && ng serve"
echo "============================================"
