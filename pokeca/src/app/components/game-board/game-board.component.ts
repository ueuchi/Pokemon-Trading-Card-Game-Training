/**
 * Game Board Component
 *
 * 役割：
 * - ゲーム全体のUIを管理
 * - GameServiceと連携
 * - プレイヤーとCPUの状態を表示
 */

import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Subject, takeUntil } from 'rxjs';
import { GameService } from '../../game/services/game.service';
import { GameState, Player, FieldPokemon } from '../../game/types/game-state.types';
import { createPlayerDeck, createCPUDeck } from '../../game/data/test-cards.data';

@Component({
  selector: 'game-board',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './game-board.component.html',
  styleUrl: './game-board.component.scss',
})
export class GameBoardComponent implements OnInit, OnDestroy {
  gameState: GameState | null = null;
  logs: string[] = [];
  isPlayerTurn = false;

  // 選択中のカード
  selectedCardId: string | null = null;
  selectedAttackIndex: number | null = null;

  // ベンチ関連
  selectedBenchIndex: number | null = null; // エネルギー付与先のベンチ
  selectedSwitchBenchIndex: number | null = null; // 入れ替え先のベンチ

  private destroy$ = new Subject<void>();

  constructor(private gameService: GameService) {}

  ngOnInit(): void {
    // ゲーム状態を監視
    this.gameService.gameState$.pipe(takeUntil(this.destroy$)).subscribe((state) => {
      this.gameState = state;
      this.isPlayerTurn = state?.currentTurn === 'PLAYER';
    });

    // ログを監視
    this.gameService.logs$.pipe(takeUntil(this.destroy$)).subscribe((logs) => {
      this.logs = logs;
      // 自動スクロール（最新のログを表示）
      setTimeout(() => this.scrollLogsToBottom(), 100);
    });
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  /**
   * ゲーム開始
   */
  startGame(): void {
    const config = {
      playerDeck: createPlayerDeck(),
      cpuDeck: createCPUDeck(),
      prizeCount: 3,
      handSize: 5,
    };

    this.gameService.initializeGame(config);
    this.selectedCardId = null;
    this.selectedAttackIndex = null;
  }

  /**
   * ゲームリセット
   */
  resetGame(): void {
    this.gameService.resetGame();
    this.selectedCardId = null;
    this.selectedAttackIndex = null;
    this.selectedBenchIndex = null;
    this.selectedSwitchBenchIndex = null;
  }

  /**
   * カードを選択
   */
  selectCard(cardId: string): void {
    if (!this.isPlayerTurn) return;

    this.selectedCardId = this.selectedCardId === cardId ? null : cardId;
    this.selectedAttackIndex = null;
  }

  /**
   * ポケモンを場に出す
   */
  playPokemon(position: 'ACTIVE' | 'BENCH'): void {
    if (!this.selectedCardId || !this.isPlayerTurn) return;

    this.gameService.executePlayerAction({
      type: 'PLAY_POKEMON',
      playerId: 'PLAYER',
      cardId: this.selectedCardId,
      position: position,
    } as any);

    this.selectedCardId = null;
  }

  /**
   * エネルギーを付ける
   */
  attachEnergy(): void {
    if (!this.selectedCardId || !this.isPlayerTurn || !this.gameState) return;

    const player = this.gameState.players.PLAYER;

    // アクティブに付ける場合
    if (this.selectedBenchIndex === null && player.activePokemon) {
      this.gameService.executePlayerAction({
        type: 'ATTACH_ENERGY',
        playerId: 'PLAYER',
        energyCardId: this.selectedCardId,
        targetPosition: 'ACTIVE',
      } as any);
    }
    // ベンチに付ける場合
    else if (this.selectedBenchIndex !== null) {
      this.gameService.executePlayerAction({
        type: 'ATTACH_ENERGY',
        playerId: 'PLAYER',
        energyCardId: this.selectedCardId,
        targetPosition: 'BENCH',
        targetBenchIndex: this.selectedBenchIndex,
      } as any);
    }

    this.selectedCardId = null;
    this.selectedBenchIndex = null;
  }

  /**
   * ベンチポケモンを選択（エネルギー付与用）
   */
  selectBenchForEnergy(index: number): void {
    if (!this.isPlayerTurn) return;
    this.selectedBenchIndex = this.selectedBenchIndex === index ? null : index;
    this.selectedSwitchBenchIndex = null; // 入れ替え選択をリセット
  }

  /**
   * ベンチポケモンを選択（入れ替え用）
   */
  selectBenchForSwitch(index: number): void {
    if (!this.isPlayerTurn) return;
    this.selectedSwitchBenchIndex = this.selectedSwitchBenchIndex === index ? null : index;
    this.selectedBenchIndex = null; // エネルギー選択をリセット
  }

  /**
   * ポケモンを入れ替える
   */
  switchPokemon(): void {
    if (this.selectedSwitchBenchIndex === null || !this.isPlayerTurn) return;

    this.gameService.executePlayerAction({
      type: 'SWITCH_POKEMON',
      playerId: 'PLAYER',
      benchIndex: this.selectedSwitchBenchIndex,
    } as any);

    this.selectedSwitchBenchIndex = null;
  }

  /**
   * ワザを選択
   */
  selectAttack(index: number): void {
    if (!this.isPlayerTurn) return;
    this.selectedAttackIndex = index;
  }

  /**
   * 攻撃実行
   */
  executeAttack(): void {
    if (this.selectedAttackIndex === null || !this.isPlayerTurn) return;

    this.gameService.executePlayerAction({
      type: 'ATTACK',
      playerId: 'PLAYER',
      attackIndex: this.selectedAttackIndex,
    });

    this.selectedAttackIndex = null;
  }

  /**
   * ターン終了
   */
  endTurn(): void {
    if (!this.isPlayerTurn) return;

    this.gameService.executePlayerAction({
      type: 'END_TURN',
      playerId: 'PLAYER',
    });

    this.selectedCardId = null;
    this.selectedAttackIndex = null;
    this.selectedBenchIndex = null;
    this.selectedSwitchBenchIndex = null;
  }

  /**
   * カードタイプを判定
   */
  getCardType(card: any): 'POKEMON' | 'ENERGY' | 'TRAINER' {
    return card.type;
  }

  /**
   * エネルギータイプの日本語名
   */
  getEnergyTypeName(type: string): string {
    const names: Record<string, string> = {
      FIRE: 'ほのお',
      WATER: 'みず',
      GRASS: 'くさ',
      ELECTRIC: 'でんき',
      COLORLESS: '無色',
    };
    return names[type] || type;
  }

  /**
   * ログを最下部にスクロール
   */
  private scrollLogsToBottom(): void {
    const logElement = document.getElementById('game-logs');
    if (logElement) {
      logElement.scrollTop = logElement.scrollHeight;
    }
  }

  /**
   * プレイヤー情報取得
   */
  get player(): Player | null {
    return this.gameState?.players.PLAYER || null;
  }

  /**
   * CPU情報取得
   */
  get cpu(): Player | null {
    return this.gameState?.players.CPU || null;
  }

  /**
   * ゲームが終了しているか
   */
  get isGameFinished(): boolean {
    return this.gameState?.gameStatus === 'FINISHED';
  }

  /**
   * 勝者
   */
  get winner(): string | null {
    if (!this.isGameFinished || !this.gameState) return null;
    return this.gameState.winner === 'PLAYER' ? 'あなた' : 'CPU';
  }

  /**
   * 選択されたカードをアクティブに出せるか
   */
  canPlayPokemonActive(): boolean {
    if (!this.selectedCardId || !this.player) return false;
    const card = this.player.hand.find((c) => c.id === this.selectedCardId);
    return card ? this.getCardType(card) === 'POKEMON' && !this.player.activePokemon : false;
  }

  /**
   * 選択されたカードをベンチに出せるか
   */
  canPlayPokemonBench(): boolean {
    if (!this.selectedCardId || !this.player) return false;
    const card = this.player.hand.find((c) => c.id === this.selectedCardId);
    return card ? this.getCardType(card) === 'POKEMON' && this.player.bench.length < 5 : false;
  }

  /**
   * アクティブにエネルギーを付けられるか
   */
  canAttachEnergyActive(): boolean {
    if (!this.selectedCardId || !this.player || this.selectedBenchIndex !== null) return false;
    const card = this.player.hand.find((c) => c.id === this.selectedCardId);
    return card ? this.getCardType(card) === 'ENERGY' && !!this.player.activePokemon : false;
  }

  /**
   * ベンチにエネルギーを付けられるか
   */
  canAttachEnergyBench(): boolean {
    if (!this.selectedCardId || !this.player || this.selectedBenchIndex === null) return false;
    const card = this.player.hand.find((c) => c.id === this.selectedCardId);
    return card ? this.getCardType(card) === 'ENERGY' : false;
  }
}
