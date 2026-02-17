/**
 * Game Service（メインサービス）
 *
 * 役割：
 * - ゲーム全体の状態管理
 * - 各サービスを統合
 * - UIからのエントリーポイント
 *
 * 設計方針：
 * - すべてのゲームロジックの窓口
 * - 状態の一元管理
 * - RxJSで状態を監視可能にする（将来拡張）
 */

import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable } from 'rxjs';
import { GameState, GameConfig } from '../types/game-state.types';
import { Action, ActionResult } from '../types/action.types';
import { createInitialGameState, startGame, debugGameState } from './game-state.factory';
import { ActionExecutorService } from './action-executor.service';
import { TurnManagerService } from './turn-manager.service';
import { GameRuleService } from './game-rule.service';
import { CpuAiService } from './cpu-ai.service';

@Injectable({
  providedIn: 'root',
})
export class GameService {
  // ゲーム状態（RxJS）
  private gameStateSubject = new BehaviorSubject<GameState | null>(null);
  public gameState$: Observable<GameState | null> = this.gameStateSubject.asObservable();

  // ログ
  private logsSubject = new BehaviorSubject<string[]>([]);
  public logs$: Observable<string[]> = this.logsSubject.asObservable();

  constructor(
    private actionExecutor: ActionExecutorService,
    private turnManager: TurnManagerService,
    private gameRule: GameRuleService,
    private cpuAi: CpuAiService,
  ) {}

  /**
   * ゲームを初期化して開始
   *
   * @param config ゲーム設定
   */
  initializeGame(config: GameConfig): void {
    // 初期状態を作成
    let state = createInitialGameState(config);

    // ゲーム開始（セットアップ）
    state = startGame(state);

    // 状態を保存
    this.gameStateSubject.next(state);

    this.addLog('ゲーム開始！');
    this.addLog(debugGameState(state));

    // 最初のターンを開始
    this.startTurn();
  }

  /**
   * 現在のゲーム状態を取得
   */
  getCurrentState(): GameState | null {
    return this.gameStateSubject.value;
  }

  /**
   * プレイヤーのアクションを実行
   *
   * @param action 実行するアクション
   */
  executePlayerAction(action: Action): void {
    const currentState = this.getCurrentState();
    if (!currentState) {
      this.addLog('エラー: ゲームが初期化されていません');
      return;
    }

    // アクションを実行
    const result = this.actionExecutor.executeAction(currentState, action);

    if (!result.success) {
      this.addLog(`エラー: ${result.error}`);
      return;
    }

    // ログを追加
    if (result.logs) {
      result.logs.forEach((log) => this.addLog(log));
    }

    // 状態を更新
    if (result.newState) {
      this.gameStateSubject.next(result.newState);

      // エネルギー付与の記録
      if (action.type === 'ATTACH_ENERGY') {
        this.turnManager.markEnergyAttached();
      }

      // 攻撃の記録
      if (action.type === 'ATTACK') {
        this.turnManager.markAttacked();
      }

      // ターン終了時の処理
      if (action.type === 'END_TURN') {
        this.handleTurnEnd(result.newState);
      }
    }
  }

  /**
   * ターン開始処理
   */
  private startTurn(): void {
    const currentState = this.getCurrentState();
    if (!currentState) return;

    const result = this.turnManager.startTurn(currentState);

    if (result.success && result.newState) {
      this.gameStateSubject.next(result.newState);

      if (result.logs) {
        result.logs.forEach((log) => this.addLog(log));
      }

      this.addLog(debugGameState(result.newState));

      // CPUのターンなら自動実行
      if (result.newState.currentTurn === 'CPU') {
        setTimeout(() => this.executeCpuTurn(), 1000); // 1秒待ってから実行
      }
    }
  }

  /**
   * ターン終了時の処理
   */
  private handleTurnEnd(state: GameState): void {
    const result = this.turnManager.endTurn(state);

    if (result.success && result.newState) {
      this.gameStateSubject.next(result.newState);

      if (result.logs) {
        result.logs.forEach((log) => this.addLog(log));
      }

      // ゲーム終了判定
      if (result.newState.gameStatus === 'FINISHED') {
        this.addLog('ゲーム終了！');
        return;
      }

      // 次のターンを開始
      this.startTurn();
    }
  }

  /**
   * CPUのターンを実行
   */
  private executeCpuTurn(): void {
    const currentState = this.getCurrentState();
    if (!currentState || currentState.currentTurn !== 'CPU') {
      return;
    }

    // CPU思考（デバッグ用）
    const thinkingLogs = this.cpuAi.debugThinking(currentState);
    thinkingLogs.forEach((log) => this.addLog(log));

    // アクションを決定
    const action = this.cpuAi.decideAction(currentState);

    // 少し待ってから実行（演出）
    setTimeout(() => {
      this.executePlayerAction(action);

      // まだCPUのターンが続く場合は次の行動へ
      const newState = this.getCurrentState();
      if (newState && newState.currentTurn === 'CPU' && newState.gameStatus === 'IN_PROGRESS') {
        setTimeout(() => this.executeCpuTurn(), 800);
      }
    }, 500);
  }

  /**
   * ログを追加
   */
  private addLog(message: string): void {
    const currentLogs = this.logsSubject.value;
    this.logsSubject.next([...currentLogs, message]);
  }

  /**
   * ログをクリア
   */
  clearLogs(): void {
    this.logsSubject.next([]);
  }

  /**
   * ゲームをリセット
   */
  resetGame(): void {
    this.gameStateSubject.next(null);
    this.clearLogs();
    this.turnManager.resetTurnLimits();
  }

  /**
   * デバッグ用：現在の状態を表示
   */
  debugCurrentState(): void {
    const state = this.getCurrentState();
    if (state) {
      console.log(debugGameState(state));
      this.addLog(debugGameState(state));
    }
  }

  /**
   * プレイヤーができる行動のリストを取得（UI用）
   */
  getAvailablePlayerActions(): string[] {
    const state = this.getCurrentState();
    if (!state || state.currentTurn !== 'PLAYER') {
      return [];
    }
    return this.turnManager.getAvailableActions(state, 'PLAYER');
  }
}
