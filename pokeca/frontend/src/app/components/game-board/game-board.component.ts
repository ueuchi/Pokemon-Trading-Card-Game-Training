import { Component, OnInit, OnDestroy, ChangeDetectorRef, NgZone } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Subject, takeUntil } from 'rxjs';
import {
  GameApiService,
  GameUiState,
  ActivePokemon,
  HandCard,
} from '../../game/services/game-api.service';
import { DeckService } from '../../game/services/deck.service';
import { Deck } from '../../game/types/deck.types';

@Component({
  selector: 'game-board',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './game-board.component.html',
  styleUrl: './game-board.component.scss',
})
export class GameBoardComponent implements OnInit, OnDestroy {
  state: GameUiState | null = null;
  decks: Deck[] = [];
  selectedDeckId: number | null = null;

  private destroy$ = new Subject<void>();

  constructor(
    public gameApi: GameApiService,
    private deckService: DeckService,
    private cdr: ChangeDetectorRef,
    private ngZone: NgZone,
  ) {}

  ngOnInit(): void {
    this.gameApi.state$.pipe(takeUntil(this.destroy$)).subscribe((state) => {
      this.state = state;
      this.cdr.detectChanges();
      this._scrollLogs();
    });
    this.loadDecks();
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  loadDecks(): void {
    this.deckService.getDecks().subscribe({
      next: (d: Deck[]) => {
        this.ngZone.run(() => {
          this.decks = d;
          this.cdr.detectChanges();
        });
      },
      error: (err) => {
        console.error('[loadDecks] failed:', err);
        this.ngZone.run(() => {
          this.decks = [];
          this.cdr.detectChanges();
        });
      },
    });
  }

  // ==================== デッキ選択 ====================

  async startGame(): Promise<void> {
    if (!this.selectedDeckId) return;
    await this.gameApi.startGame(this.selectedDeckId);
  }

  // ==================== コイントス ====================

  get firstPlayerLabel(): string {
    const fp = this.state?.gameState?.first_player_id;
    return fp === 'player1' ? 'あなた' : 'CPU';
  }

  get isPlayerFirst(): boolean {
    return this.state?.gameState?.first_player_id === 'player1';
  }

  proceedToPlaceInitial(): void {
    this.gameApi.proceedToPlaceInitial();
  }

  // ==================== 初期配置 ====================

  get basicPokemonInHand(): HandCard[] {
    return this.gameApi.basicPokemonInHand;
  }

  isInitialActive(cardId: number): boolean {
    return this.state?.initialActiveId === cardId;
  }

  isInitialBench(cardId: number): boolean {
    return this.state?.initialBenchIds.includes(cardId) ?? false;
  }

  toggleInitialActive(cardId: number): void {
    this.gameApi.toggleInitialActive(cardId);
  }

  toggleInitialBench(cardId: number): void {
    if (this.state?.initialActiveId === cardId) {
      this.gameApi.toggleInitialActive(cardId);
    } else {
      this.gameApi.toggleInitialBench(cardId);
    }
  }

  get canConfirmInitial(): boolean {
    return !!this.state?.initialActiveId && !this.state?.isLoading;
  }

  async confirmInitialPlacement(): Promise<void> {
    await this.gameApi.confirmInitialPlacement();
  }

  // ==================== 手札操作 ====================

  selectHandCard(cardId: number): void {
    if (!this.gameApi.isPlayerTurn) return;
    this.gameApi.selectCard(cardId);
  }

  isHandCardSelected(cardId: number): boolean {
    return this.state?.selectedCardId === cardId;
  }

  get selectedHandCard(): HandCard | null {
    if (!this.state?.selectedCardId) return null;
    return this.gameApi.player1?.hand.find((c) => c.uid === this.state!.selectedCardId) ?? null;
  }

  // ==================== アクション判定 ====================

  get canPlaceActive(): boolean {
    const c = this.selectedHandCard;
    return (
      !!c &&
      c.card_type === 'pokemon' &&
      c.evolution_stage === 'たね' &&
      !this.gameApi.player1?.active_pokemon
    );
  }

  get canPlaceBench(): boolean {
    const c = this.selectedHandCard;
    const bench = this.gameApi.player1?.bench ?? [];
    return !!c && c.card_type === 'pokemon' && c.evolution_stage === 'たね' && bench.length < 5;
  }

  get canAttachEnergy(): boolean {
    const c = this.selectedHandCard;
    const p1 = this.gameApi.player1;
    if (!c || !p1 || p1.energy_attached_this_turn) return false;
    return c.card_type === 'energy' && (!!p1.active_pokemon || p1.bench.length > 0);
  }

  get canEvolveActive(): boolean {
    const c = this.selectedHandCard;
    const active = this.gameApi.player1?.active_pokemon;
    if (!c || !active || c.card_type !== 'pokemon') return false;
    const stage = c.evolution_stage;
    return (stage === '1進化' || stage === '2進化') && c.evolves_from === active.name;
  }

  get canRetreat(): boolean {
    const p1 = this.gameApi.player1;
    if (!p1 || !this.gameApi.isPlayerTurn || p1.retreated_this_turn) return false;
    return !!p1.active_pokemon && p1.bench.length > 0;
  }

  // ==================== バトルアクション ====================

  async placeToActive(): Promise<void> {
    if (!this.state?.selectedCardId) return;
    await this.gameApi.sendAction('place_active', { cardId: this.state.selectedCardId });
  }

  async placeToBench(): Promise<void> {
    if (!this.state?.selectedCardId) return;
    await this.gameApi.sendAction('place_bench', { cardId: this.state.selectedCardId });
  }

  async attachEnergyToActive(): Promise<void> {
    if (!this.state?.selectedCardId) return;
    await this.gameApi.sendAction('attach_energy', {
      cardId: this.state.selectedCardId,
      target: 'active',
    });
  }

  async attachEnergyToBench(benchIndex: number): Promise<void> {
    if (!this.state?.selectedCardId) return;
    await this.gameApi.sendAction('attach_energy', {
      cardId: this.state.selectedCardId,
      target: 'bench',
      benchIndex,
    });
  }

  async evolveActive(): Promise<void> {
    if (!this.state?.selectedCardId) return;
    await this.gameApi.sendAction('evolve_active', { cardId: this.state.selectedCardId });
  }

  selectAttack(index: number): void {
    if (!this.gameApi.isPlayerTurn || !this.gameApi.canAttack) return;
    this.gameApi.selectAttack(index);
  }

  async executeAttack(): Promise<void> {
    if (this.state?.selectedAttackIndex == null) return;
    await this.gameApi.sendAction('attack', { attackIndex: this.state.selectedAttackIndex });
  }

  async replaceFainted(benchIndex: number): Promise<void> {
    await this.gameApi.replaceActive(benchIndex);
  }

  async endTurn(): Promise<void> {
    await this.gameApi.endTurn();
  }

  resetGame(): void {
    this.gameApi.resetGame();
    this.selectedDeckId = null;
  }

  // ==================== ベンチ操作 ====================

  toggleBenchForEnergy(index: number): void {
    if (!this.gameApi.isPlayerTurn) return;
    this.gameApi.selectBench(index);
  }

  isBenchSelectedForEnergy(index: number): boolean {
    return this.state?.selectedBenchIndex === index;
  }

  // ==================== 表示ヘルパー ====================

  // ==================== デッキ情報ヘルパー ====================

  /** デッキのエネルギーバッジ一覧を返す */
  getDeckEnergyBadges(deck: Deck): { type: string; count: number; emoji: string; color: string }[] {
    return Object.entries(deck.energies ?? {}).map(([type, count]) => ({
      type,
      count,
      emoji: this.getTypeEmoji(type),
      color: this.getTypeColor(type),
    }));
  }

  /** デッキ内のポケモンカード合計枚数 */
  getDeckPokemonCount(deck: Deck): number {
    const stages = ['たね', '1 進化', '2 進化'];
    return deck.cards
      .filter((c) => c.evolution_stage && stages.includes(c.evolution_stage))
      .reduce((sum, c) => sum + c.count, 0);
  }

  /** デッキ内のトレーナーカード合計枚数 */
  getDeckTrainerCount(deck: Deck): number {
    const trainerTypes = ['サポート', 'グッズ', 'スタジアム'];
    return deck.cards
      .filter((c) => c.type && trainerTypes.includes(c.type))
      .reduce((sum, c) => sum + c.count, 0);
  }

  /** デッキのメインカラー（エネルギーの最初のタイプ） */
  getDeckMainColor(deck: Deck): string {
    const topType = Object.keys(deck.energies ?? {})[0] ?? null;
    return this.getTypeColor(topType);
  }

  getTypeColor(type: string | null): string {
    if (!type) return '#9E9E9E';
    const colors: Record<string, string> = {
      草: '#4CAF50',
      炎: '#FF5722',
      水: '#2196F3',
      雷: '#FFC107',
      超: '#9C27B0',
      闘: '#FF8F00',
      悪: '#424242',
      鋼: '#78909C',
      ドラゴン: '#1565C0',
      フェアリー: '#EC407A',
      無色: '#9E9E9E',
    };
    return colors[type] ?? '#9E9E9E';
  }

  getTypeEmoji(type: string | null): string {
    if (!type) return '⭕';
    const emojis: Record<string, string> = {
      草: '🌿',
      炎: '🔥',
      水: '💧',
      雷: '⚡',
      超: '🔮',
      闘: '👊',
      悪: '🌑',
      鋼: '⚙️',
      ドラゴン: '🐉',
      フェアリー: '✨',
      無色: '⭕',
    };
    return emojis[type] ?? '⭕';
  }

  getCardRuleLabel(rule: string | null): string {
    if (rule === 'ex') return 'EX';
    if (rule === 'mega_ex') return 'MEGA EX';
    return '';
  }

  getPokemonTypeLabel(pt: string | null): string {
    if (pt === 'trainer_pokemon') return 'トレーナーポケモン';
    return '';
  }

  getCardBackPlaceholders(count: number): number[] {
    const capped = Math.max(0, Math.min(12, count));
    return Array.from({ length: capped }, (_, i) => i);
  }

  hpPercent(pokemon: ActivePokemon): number {
    if (!pokemon.hp) return 100;
    return Math.max(0, Math.min(100, (pokemon.current_hp / pokemon.hp) * 100));
  }

  hpBarClass(pokemon: ActivePokemon): string {
    const pct = this.hpPercent(pokemon);
    if (pct > 50) return 'hp-high';
    if (pct > 25) return 'hp-mid';
    return 'hp-low';
  }

  get turnLabel(): string {
    if (!this.state?.gameState) return '';
    return this.gameApi.isPlayerTurn
      ? 'あなたのターン'
      : this.state.isCpuThinking
        ? 'CPUが考え中…'
        : 'CPUのターン';
  }

  get phaseLabel(): string {
    const p = this.state?.gameState?.turn_phase;
    const m: Record<string, string> = {
      draw: 'ドロー',
      main: 'メイン',
      attack: '攻撃後',
      end: '終了',
    };
    return p ? (m[p] ?? p) : '';
  }

  get needsReplacement(): boolean {
    return this.gameApi.needsReplacement;
  }

  private _scrollLogs(): void {
    setTimeout(() => {
      const el = document.getElementById('game-logs');
      if (el) el.scrollTop = el.scrollHeight;
    }, 50);
  }
}
