/**
 * Turn Manager Service
 *
 * 役割：
 * - ターンの進行を管理
 * - フェーズ遷移の制御
 * - ターン開始/終了時の自動処理
 *
 * 設計方針：
 * - ターンの流れを明示的に定義
 * - 自動実行される処理（ドロー等）を管理
 */

import { Injectable } from '@angular/core';
import { GameState, GamePhase, Player } from '../types/game-state.types';
import { ActionExecutorService } from './action-executor.service';
import { GameRuleService } from './game-rule.service';
import { ActionResult } from '../types/action.types';

/**
 * ターン制限（1ターンに1回のみの行動を管理）
 */
export interface TurnLimits {
  energyAttached: boolean; // エネルギーを付けたか
  hasAttacked: boolean; // 攻撃したか
}

@Injectable({
  providedIn: 'root',
})
export class TurnManagerService {
  // 現在のターンの制限状態
  private currentTurnLimits: TurnLimits = {
    energyAttached: false,
    hasAttacked: false,
  };

  constructor(
    private actionExecutor: ActionExecutorService,
    private gameRule: GameRuleService,
  ) {}

  /**
   * ターン開始処理
   *
   * 自動的に行われる処理：
   * 1. ドローフェーズ：カードを1枚引く（最初のターン以外）
   * 2. メインフェーズへ移行
   *
   * @param state 現在のGameState
   * @returns 更新されたGameState
   */
  startTurn(state: GameState): ActionResult {
    const logs: string[] = [];
    let currentState = state;

    // ターン制限をリセット
    this.currentTurnLimits = {
      energyAttached: false,
      hasAttacked: false,
    };

    logs.push(`\n=== ターン ${state.turnCount} - ${state.currentTurn} ===`);

    // ドローフェーズ：カードを1枚引く
    if (state.phase === 'DRAW') {
      const drawResult = this.actionExecutor.executeAction(currentState, {
        type: 'DRAW_CARD',
        playerId: state.currentTurn,
        amount: 1,
      });

      if (drawResult.success && drawResult.newState) {
        currentState = drawResult.newState;
        logs.push(...(drawResult.logs || []));
      } else {
        logs.push('カードを引けませんでした');
      }
    }

    // メインフェーズへ移行
    currentState = {
      ...currentState,
      phase: 'MAIN',
    };

    logs.push('メインフェーズ：行動を選択してください');

    return {
      success: true,
      newState: currentState,
      logs,
    };
  }

  /**
   * ターン終了処理
   *
   * @param state 現在のGameState
   * @returns 更新されたGameState
   */
  endTurn(state: GameState): ActionResult {
    const logs: string[] = [];

    // ターン終了アクションを実行
    const result = this.actionExecutor.executeAction(state, {
      type: 'END_TURN',
      playerId: state.currentTurn,
    });

    if (!result.success || !result.newState) {
      return result;
    }

    logs.push(...(result.logs || []));

    // 勝敗判定
    const winner = this.gameRule.checkWinner(result.newState);
    if (winner) {
      const finalState: GameState = {
        ...result.newState,
        gameStatus: 'FINISHED',
        winner,
      };

      logs.push(`\n🎉 ${winner} の勝利！`);

      return {
        success: true,
        newState: finalState,
        logs,
      };
    }

    return {
      success: true,
      newState: result.newState,
      logs,
    };
  }

  /**
   * エネルギーを付けた記録
   */
  markEnergyAttached(): void {
    this.currentTurnLimits.energyAttached = true;
  }

  /**
   * 攻撃した記録
   */
  markAttacked(): void {
    this.currentTurnLimits.hasAttacked = true;
  }

  /**
   * このターンにエネルギーを付けたかチェック
   */
  hasAttachedEnergyThisTurn(): boolean {
    return this.currentTurnLimits.energyAttached;
  }

  /**
   * このターンに攻撃したかチェック
   */
  hasAttackedThisTurn(): boolean {
    return this.currentTurnLimits.hasAttacked;
  }

  /**
   * ターン制限をリセット（テスト用）
   */
  resetTurnLimits(): void {
    this.currentTurnLimits = {
      energyAttached: false,
      hasAttacked: false,
    };
  }

  /**
   * 現在のフェーズを取得
   */
  getCurrentPhase(state: GameState): GamePhase {
    return state.phase;
  }

  /**
   * メインフェーズかチェック（行動可能か）
   */
  isMainPhase(state: GameState): boolean {
    return state.phase === 'MAIN';
  }

  /**
   * プレイヤーができる行動をリストアップ（UI用）
   */
  getAvailableActions(state: GameState, playerId: 'PLAYER' | 'CPU'): string[] {
    const actions: string[] = [];
    const player = state.players[playerId];

    if (!this.isMainPhase(state)) {
      return ['ターン開始を待っています'];
    }

    // ポケモンを場に出せるか
    if (!player.activePokemon && this.gameRule.hasPokemonInHand(player)) {
      actions.push('ポケモンを場に出す');
    }

    // エネルギーを付けられるか
    if (
      player.activePokemon &&
      !this.hasAttachedEnergyThisTurn() &&
      this.gameRule.hasEnergyInHand(player)
    ) {
      actions.push('エネルギーを付ける');
    }

    // 攻撃できるか
    if (player.activePokemon && !this.hasAttackedThisTurn()) {
      for (let i = 0; i < player.activePokemon.card.attacks.length; i++) {
        if (this.gameRule.canUseAttack(player.activePokemon, i)) {
          actions.push(`ワザ: ${player.activePokemon.card.attacks[i].name}`);
        }
      }
    }

    // 常に可能な行動
    actions.push('ターン終了');

    return actions;
  }

  /**
   * デバッグ用：ターン状態の表示
   */
  debugTurnStatus(state: GameState): string {
    const lines: string[] = [];

    lines.push(`ターン ${state.turnCount} - ${state.currentTurn}`);
    lines.push(`フェーズ: ${state.phase}`);
    lines.push(`エネルギー付与: ${this.currentTurnLimits.energyAttached ? '済' : '未'}`);
    lines.push(`攻撃: ${this.currentTurnLimits.hasAttacked ? '済' : '未'}`);

    return lines.join(' | ');
  }
}
