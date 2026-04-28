/**
 * Game API Service（新フロー対応版）
 * バックエンドの /api/game/cpu/* エンドポイントと通信する
 *
 * 画面フロー:
 *   deck-select → coin-toss → place-initial → battle → game-over
 */
import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { BehaviorSubject, Observable, firstValueFrom } from 'rxjs';
import { environment } from '../../../environments/environment';

// ==================== API型定義 ====================

export interface AttackInfo {
  name: string;
  energy: string[];
  energy_count: number;
  damage: number;
  description: string;
}

export interface AbilityInfo {
  name: string;
  description: string;
}

export interface WeaknessInfo {
  type: string;
  value: number;
}

export interface ActivePokemon {
  card_id: number;
  name: string;
  hp: number;
  current_hp: number;
  damage_counters: number;
  attached_energy: string[];
  special_condition: string;
  turns_in_play: number;
  evolution_stage: string;
  type: string;
  pokemon_type: string;
  card_rule: string | null;
  attacks: AttackInfo[];
  ability: AbilityInfo | null;
  retreat_cost: number;
  weakness: WeaknessInfo | null;
  resistance: WeaknessInfo | null;
  image_url: string | null;
}

export interface HandCard {
  card_id: number;
  uid: number;
  name: string;
  card_type: string;
  evolution_stage: string | null;
  evolves_from: string | null;
  type: string | null;
  energy_type: string | null;
  trainer_type: string | null;
  is_ace_spec: boolean;
  pokemon_type: string | null;
  image_url: string | null;
}

export interface PlayerState {
  player_id: string;
  deck_count: number;
  hand_count: number;
  hand: HandCard[];
  active_pokemon: ActivePokemon | null;
  bench: ActivePokemon[];
  prize_remaining: number;
  discard_count: number;
  energy_attached_this_turn: boolean;
  supporter_used_this_turn: boolean;
  retreated_this_turn: boolean;
}

export interface GameStateResponse {
  game_id: string;
  current_turn: number;
  current_player_id: string;
  first_player_id: string;
  game_phase: string;
  turn_phase: string;
  winner_id: string | null;
  is_first_turn: boolean;
  attacked_this_turn: boolean;
  coin_toss_result: string | null;
  mulligan_info: { player1_mulligans: number; player2_mulligans: number } | null;
  stadium: { card_id: number; name: string; played_by: string } | null;
  player1: PlayerState;
  player2: PlayerState;
  logs: { turn: number; player_id: string; action: string; detail: string }[];
}

// ==================== UI状態 ====================

export type GameScreen = 'deck-select' | 'coin-toss' | 'place-initial' | 'battle' | 'game-over';

export interface GameUiState {
  screen: GameScreen;
  gameState: GameStateResponse | null;
  gameId: string | null;
  isLoading: boolean;
  error: string | null;
  selectedCardId: number | null;
  selectedAttackIndex: number | null;
  selectedBenchIndex: number | null;
  initialActiveId: number | null;
  initialBenchIds: number[];
  isCpuThinking: boolean;
  logs: string[];
}

@Injectable({ providedIn: 'root' })
export class GameApiService {
  private readonly baseUrl = `${environment.apiUrl.replace('/api/cards', '')}/api/game/cpu`;

  private uiState$ = new BehaviorSubject<GameUiState>(this._initialState());
  state$: Observable<GameUiState> = this.uiState$.asObservable();

  constructor(private http: HttpClient) {}

  private _initialState(): GameUiState {
    return {
      screen: 'deck-select',
      gameState: null,
      gameId: null,
      isLoading: false,
      error: null,
      selectedCardId: null,
      selectedAttackIndex: null,
      selectedBenchIndex: null,
      initialActiveId: null,
      initialBenchIds: [],
      isCpuThinking: false,
      logs: [],
    };
  }

  get state(): GameUiState {
    return this.uiState$.value;
  }
  private patch(p: Partial<GameUiState>): void {
    this.uiState$.next({ ...this.state, ...p });
  }

  private addLog(msg: string): void {
    this.patch({ logs: [...this.state.logs, msg].slice(-100) });
  }

  // ==================== ゲーム開始 ====================

  async startGame(playerDeckId: number, cpuDifficulty: string = 'normal', cpuDeckId?: number): Promise<void> {
    this.patch({ isLoading: true, error: null });
    try {
      const res: any = await firstValueFrom(
        this.http.post(`${this.baseUrl}/start`, {
          player_deck_id: playerDeckId,
          cpu_deck_id: cpuDeckId ?? null,
          cpu_difficulty: cpuDifficulty,
        }),
      );
      const gs: GameStateResponse = res.state;
      const first = gs.first_player_id === 'player1' ? 'あなた' : 'CPU';
      this.patch({
        gameId: res.game_id,
        gameState: gs,
        screen: 'coin-toss',
        isLoading: false,
        logs: [`🪙 コイントス結果: ${first}が先行！`],
      });
    } catch (e: any) {
      this.patch({ isLoading: false, error: e?.error?.detail ?? 'ゲーム開始に失敗しました' });
    }
  }

  proceedToPlaceInitial(): void {
    const mulligan = this.state.gameState?.mulligan_info;
    const logs = [...this.state.logs];
    if (mulligan?.player1_mulligans)
      logs.push(`🔄 あなたは${mulligan.player1_mulligans}回マリガンしました`);
    if (mulligan?.player2_mulligans)
      logs.push(`🔄 CPUは${mulligan.player2_mulligans}回マリガンしました`);
    logs.push('🃏 バトル場とベンチにポケモンを配置してください');
    this.patch({ screen: 'place-initial', logs });
  }

  // ==================== 初期配置 ====================

  toggleInitialActive(cardId: number): void {
    const current = this.state.initialActiveId;
    this.patch({
      initialActiveId: current === cardId ? null : cardId,
      initialBenchIds: this.state.initialBenchIds.filter((id) => id !== cardId),
      error: null,
    });
  }

  toggleInitialBench(cardId: number): void {
    if (this.state.initialActiveId === cardId) return;
    const ids = [...this.state.initialBenchIds];
    const idx = ids.indexOf(cardId);
    if (idx >= 0) ids.splice(idx, 1);
    else if (ids.length < 5) ids.push(cardId);
    this.patch({ initialBenchIds: ids, error: null });
  }

  async confirmInitialPlacement(): Promise<void> {
    const { initialActiveId, initialBenchIds, gameId } = this.state;
    if (!initialActiveId || !gameId) return;
    this.patch({ isLoading: true, error: null });
    try {
      const res: any = await firstValueFrom(
        this.http.post(`${this.baseUrl}/${gameId}/place_initial`, {
          active_card_id: initialActiveId,
          bench_card_ids: initialBenchIds,
        }),
      );
      this.patch({
        gameState: res.state,
        screen: 'battle',
        isLoading: false,
        initialActiveId: null,
        initialBenchIds: [],
      });
      this.addLog('⚔️ ゲーム開始！');
      this._syncLogsFromState(res.state);
    } catch (e: any) {
      this.patch({ isLoading: false, error: e?.error?.detail ?? '初期配置に失敗しました' });
    }
  }

  // ==================== バトルアクション ====================

  async sendAction(
    actionType: string,
    opts: {
      cardId?: number;
      attackIndex?: number;
      benchIndex?: number;
      energyIndices?: number[];
      target?: string;
    } = {},
  ): Promise<void> {
    if (!this.state.gameId) return;
    this.patch({ isLoading: true, error: null });
    try {
      const res: any = await firstValueFrom(
        this.http.post(`${this.baseUrl}/${this.state.gameId}/action`, {
          action_type: actionType,
          card_id: opts.cardId ?? null,
          attack_index: opts.attackIndex ?? null,
          bench_index: opts.benchIndex ?? null,
          energy_indices: opts.energyIndices ?? null,
          target: opts.target ?? null,
        }),
      );
      this.patch({
        gameState: res.state,
        isLoading: false,
        selectedCardId: null,
        selectedAttackIndex: null,
        selectedBenchIndex: null,
      });
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
      const res: any = await firstValueFrom(
        this.http.post(`${this.baseUrl}/${this.state.gameId}/end_turn`, {}),
      );
      this.patch({
        gameState: res.state,
        isLoading: false,
        isCpuThinking: false,
        selectedCardId: null,
        selectedAttackIndex: null,
        selectedBenchIndex: null,
      });
      this._syncLogsFromState(res.state);
      this._checkGameOver(res.state);
    } catch (e: any) {
      this.patch({
        isLoading: false,
        isCpuThinking: false,
        error: e?.error?.detail ?? 'ターン終了に失敗しました',
      });
    }
  }

  async replaceActive(benchIndex: number): Promise<void> {
    if (!this.state.gameId) return;
    this.patch({ isLoading: true, error: null });
    try {
      const res: any = await firstValueFrom(
        this.http.post(`${this.baseUrl}/${this.state.gameId}/replace_active`, {
          bench_index: benchIndex,
        }),
      );
      this.patch({ gameState: res.state, isLoading: false });
      this._syncLogsFromState(res.state);
    } catch (e: any) {
      this.patch({ isLoading: false, error: e?.error?.detail ?? '交代に失敗しました' });
    }
  }

  // ==================== UI操作 ====================

  selectCard(cardId: number): void {
    this.patch({
      selectedCardId: this.state.selectedCardId === cardId ? null : cardId,
      selectedAttackIndex: null,
      selectedBenchIndex: null,
      error: null,
    });
  }

  selectAttack(index: number): void {
    this.patch({
      selectedAttackIndex: this.state.selectedAttackIndex === index ? null : index,
      selectedCardId: null,
    });
  }

  selectBench(index: number): void {
    this.patch({ selectedBenchIndex: this.state.selectedBenchIndex === index ? null : index });
  }

  clearSelections(): void {
    this.patch({
      selectedCardId: null,
      selectedAttackIndex: null,
      selectedBenchIndex: null,
      error: null,
    });
  }

  resetGame(): void {
    this.uiState$.next(this._initialState());
  }

  // ==================== ゲッター ====================

  get player1(): PlayerState | null {
    return this.state.gameState?.player1 ?? null;
  }
  get player2(): PlayerState | null {
    return this.state.gameState?.player2 ?? null;
  }
  get isPlayerTurn(): boolean {
    return this.state.gameState?.current_player_id === 'player1';
  }

  get needsReplacement(): boolean {
    const p1 = this.player1;
    return !!p1 && !p1.active_pokemon && p1.bench.length > 0;
  }

  get canAttack(): boolean {
    const gs = this.state.gameState;
    return (
      this.isPlayerTurn &&
      !!gs &&
      !gs.attacked_this_turn &&
      !gs.is_first_turn &&
      !!this.player1?.active_pokemon
    );
  }

  get basicPokemonInHand(): HandCard[] {
    return (this.player1?.hand ?? []).filter(
      (c) => c.card_type === 'pokemon' && c.evolution_stage === 'たね',
    );
  }

  // ==================== プライベート ====================

  private _syncLogsFromState(state: GameStateResponse): void {
    if (!state?.logs) return;
    const existing = new Set(this.state.logs);
    state.logs.forEach((l) => {
      const msg = `[T${l.turn}] ${l.player_id === 'player1' ? '🧑' : '🤖'} ${l.action}${l.detail ? ': ' + l.detail : ''}`;
      if (!existing.has(msg)) {
        this.addLog(msg);
        existing.add(msg);
      }
    });
  }

  private _checkGameOver(state: GameStateResponse): void {
    if (state?.game_phase === 'game_over') this.patch({ screen: 'game-over' });
  }
}
