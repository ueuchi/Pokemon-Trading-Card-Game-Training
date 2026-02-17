/**
 * Effect Resolver Service
 * 
 * 役割：
 * - カードの効果（Effect）を実際にGameStateに適用する
 * - 効果の解決ロジックを一箇所に集約
 * - ダメージ、回復、ドローなどの処理を実装
 * 
 * 設計方針：
 * - 各Effectタイプごとに解決関数を持つ
 * - GameStateを変更せず、新しいStateを返す（Immutable）
 * - ログメッセージを生成して返す
 */

import { Injectable } from '@angular/core';
import {
  GameState,
  Effect,
  DamageEffect,
  HealEffect,
  DrawEffect,
  ConditionalEffect,
  Player,
  FieldPokemon
} from '../types/game-state.types';

/**
 * 効果解決の結果
 */
export interface EffectResolutionResult {
  newState: GameState;
  logs: string[];
}

@Injectable({
  providedIn: 'root'
})
export class EffectResolverService {

  /**
   * 効果のリストを順番に解決
   * 
   * @param state 現在のGameState
   * @param effects 解決する効果のリスト
   * @param attackerId 攻撃側のプレイヤーID
   * @returns 解決後の状態とログ
   */
  resolveEffects(
    state: GameState,
    effects: Effect[],
    attackerId: 'PLAYER' | 'CPU'
  ): EffectResolutionResult {
    let currentState = state;
    const allLogs: string[] = [];

    // 効果を順番に適用
    for (const effect of effects) {
      const result = this.resolveSingleEffect(currentState, effect, attackerId);
      currentState = result.newState;
      allLogs.push(...result.logs);
    }

    return {
      newState: currentState,
      logs: allLogs
    };
  }

  /**
   * 単一の効果を解決
   */
  private resolveSingleEffect(
    state: GameState,
    effect: Effect,
    attackerId: 'PLAYER' | 'CPU'
  ): EffectResolutionResult {
    switch (effect.type) {
      case 'DAMAGE':
        return this.resolveDamage(state, effect, attackerId);
      
      case 'HEAL':
        return this.resolveHeal(state, effect, attackerId);
      
      case 'DRAW':
        return this.resolveDraw(state, effect, attackerId);
      
      case 'CONDITIONAL':
        return this.resolveConditional(state, effect, attackerId);
      
      default:
        // 未知の効果タイプ（型安全性のため）
        return {
          newState: state,
          logs: ['未知の効果タイプです']
        };
    }
  }

  /**
   * ダメージ効果を解決
   * 
   * 相手のアクティブポケモンにダメージを与える
   */
  private resolveDamage(
    state: GameState,
    effect: DamageEffect,
    attackerId: 'PLAYER' | 'CPU'
  ): EffectResolutionResult {
    const newState = { ...state };
    const defenderId: 'PLAYER' | 'CPU' = attackerId === 'PLAYER' ? 'CPU' : 'PLAYER';
    
    // 防御側のプレイヤーを取得
    const defender = newState.players[defenderId];
    
    if (!defender.activePokemon) {
      return {
        newState: state,
        logs: ['対象のポケモンがいません']
      };
    }

    // 新しいプレイヤーオブジェクトを作成（Immutable）
    const newDefender: Player = {
      ...defender,
      activePokemon: {
        ...defender.activePokemon,
        currentHp: Math.max(0, defender.activePokemon.currentHp - effect.amount),
        damageCounters: defender.activePokemon.damageCounters + effect.amount
      }
    };

    // 状態を更新
    newState.players = {
      ...newState.players,
      [defenderId]: newDefender
    };

    const pokemonName = defender.activePokemon.card.name;
    const remainingHp = newDefender.activePokemon!.currentHp;

    return {
      newState,
      logs: [
        `${pokemonName}に${effect.amount}ダメージ！`,
        `${pokemonName}の残りHP: ${remainingHp}`
      ]
    };
  }

  /**
   * 回復効果を解決
   * 
   * 自分のアクティブポケモンのHPを回復
   */
  private resolveHeal(
    state: GameState,
    effect: HealEffect,
    attackerId: 'PLAYER' | 'CPU'
  ): EffectResolutionResult {
    const newState = { ...state };
    const player = newState.players[attackerId];
    
    if (!player.activePokemon) {
      return {
        newState: state,
        logs: ['回復対象のポケモンがいません']
      };
    }

    const maxHp = player.activePokemon.card.hp;
    const currentHp = player.activePokemon.currentHp;
    const healAmount = Math.min(effect.amount, maxHp - currentHp);

    const newPlayer: Player = {
      ...player,
      activePokemon: {
        ...player.activePokemon,
        currentHp: currentHp + healAmount,
        damageCounters: Math.max(0, player.activePokemon.damageCounters - healAmount)
      }
    };

    newState.players = {
      ...newState.players,
      [attackerId]: newPlayer
    };

    const pokemonName = player.activePokemon.card.name;

    return {
      newState,
      logs: [
        `${pokemonName}は${healAmount}回復した！`,
        `${pokemonName}のHP: ${newPlayer.activePokemon!.currentHp}/${maxHp}`
      ]
    };
  }

  /**
   * ドロー効果を解決
   * 
   * カードを引く
   */
  private resolveDraw(
    state: GameState,
    effect: DrawEffect,
    attackerId: 'PLAYER' | 'CPU'
  ): EffectResolutionResult {
    const newState = { ...state };
    const player = newState.players[attackerId];
    
    // 山札から引ける枚数を計算
    const drawAmount = Math.min(effect.amount, player.deck.length);
    
    if (drawAmount === 0) {
      return {
        newState: state,
        logs: ['山札がありません']
      };
    }

    // 山札から引く
    const drawnCards = player.deck.slice(0, drawAmount);
    const remainingDeck = player.deck.slice(drawAmount);

    const newPlayer: Player = {
      ...player,
      deck: remainingDeck,
      hand: [...player.hand, ...drawnCards]
    };

    newState.players = {
      ...newState.players,
      [attackerId]: newPlayer
    };

    return {
      newState,
      logs: [`${drawAmount}枚カードを引きました`]
    };
  }

  /**
   * 条件付き効果を解決
   * 
   * 例：コイン投げで表なら追加ダメージ
   */
  private resolveConditional(
    state: GameState,
    effect: ConditionalEffect,
    attackerId: 'PLAYER' | 'CPU'
  ): EffectResolutionResult {
    const logs: string[] = [];
    
    // コイン投げ（50%の確率）
    if (effect.condition === 'COIN_FLIP') {
      const isSuccess = Math.random() < 0.5;
      
      logs.push(isSuccess ? 'コイン投げ：表' : 'コイン投げ：裏');

      if (isSuccess && effect.successEffects) {
        // 成功時の効果を解決
        const result = this.resolveEffects(state, effect.successEffects, attackerId);
        return {
          newState: result.newState,
          logs: [...logs, ...result.logs]
        };
      } else if (!isSuccess && effect.failEffects) {
        // 失敗時の効果を解決
        const result = this.resolveEffects(state, effect.failEffects, attackerId);
        return {
          newState: result.newState,
          logs: [...logs, ...result.logs]
        };
      }
    }

    return {
      newState: state,
      logs
    };
  }
}
