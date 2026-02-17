/**
 * Action Executor Service
 * 
 * 役割：
 * - Actionを受け取り、GameStateに適用する
 * - アクションのバリデーション
 * - 新しいGameStateを返す（Immutable）
 * 
 * 設計方針：
 * - 各アクションタイプごとに実行関数を持つ
 * - EffectResolverとGameRuleServiceに依存
 * - すべての状態変更はここを通る
 */

import { Injectable } from '@angular/core';
import {
  Action,
  ActionResult,
  ActionValidation,
  DrawCardAction,
  PlayPokemonAction,
  AttachEnergyAction,
  AttackAction,
  EndTurnAction
} from '../types/action.types';
import {
  GameState,
  Player,
  PokemonCard,
  EnergyCard
} from '../types/game-state.types';
import { EffectResolverService } from './effect-resolver.service';
import { GameRuleService } from './game-rule.service';
import { createFieldPokemon } from './game-state.factory';

@Injectable({
  providedIn: 'root'
})
export class ActionExecutorService {

  constructor(
    private effectResolver: EffectResolverService,
    private gameRule: GameRuleService
  ) {}

  /**
   * アクションを実行
   * 
   * @param state 現在のGameState
   * @param action 実行するアクション
   * @returns 実行結果（成功/失敗、新しいState、ログ）
   */
  executeAction(state: GameState, action: Action): ActionResult {
    // バリデーション
    const validation = this.validateAction(state, action);
    if (!validation.valid) {
      return {
        success: false,
        error: validation.reason
      };
    }

    // アクションタイプごとに処理を分岐
    switch (action.type) {
      case 'DRAW_CARD':
        return this.executeDraw(state, action);
      
      case 'PLAY_POKEMON':
        return this.executePlayPokemon(state, action);
      
      case 'ATTACH_ENERGY':
        return this.executeAttachEnergy(state, action);
      
      case 'ATTACK':
        return this.executeAttack(state, action);
      
      case 'END_TURN':
        return this.executeEndTurn(state, action);
      
      case 'PASS':
        return {
          success: true,
          newState: state,
          logs: ['パスしました']
        };
      
      default:
        return {
          success: false,
          error: '未知のアクションタイプです'
        };
    }
  }

  /**
   * アクションのバリデーション
   */
  private validateAction(state: GameState, action: Action): ActionValidation {
    // 基本チェック：現在のターンのプレイヤーか
    if (state.currentTurn !== action.playerId) {
      return {
        valid: false,
        reason: '現在のターンではありません'
      };
    }

    // ゲームが進行中か
    if (state.gameStatus !== 'IN_PROGRESS') {
      return {
        valid: false,
        reason: 'ゲームが進行中ではありません'
      };
    }

    // アクションタイプごとの詳細バリデーションは各実行関数内で行う
    return { valid: true };
  }

  /**
   * ドローアクションを実行
   */
  private executeDraw(state: GameState, action: DrawCardAction): ActionResult {
    const player = state.players[action.playerId];
    
    if (player.deck.length === 0) {
      return {
        success: false,
        error: '山札がありません'
      };
    }

    const drawAmount = Math.min(action.amount, player.deck.length);
    const drawnCards = player.deck.slice(0, drawAmount);
    const remainingDeck = player.deck.slice(drawAmount);

    const newPlayer: Player = {
      ...player,
      deck: remainingDeck,
      hand: [...player.hand, ...drawnCards]
    };

    const newState: GameState = {
      ...state,
      players: {
        ...state.players,
        [action.playerId]: newPlayer
      }
    };

    return {
      success: true,
      newState,
      logs: [`${drawAmount}枚カードを引きました`]
    };
  }

  /**
   * ポケモンを場に出すアクションを実行
   */
  private executePlayPokemon(state: GameState, action: PlayPokemonAction): ActionResult {
    const player = state.players[action.playerId];
    
    // 手札にそのカードがあるかチェック
    const card = this.gameRule.findCardInHand(player, action.cardId);
    if (!card || card.type !== 'POKEMON') {
      return {
        success: false,
        error: '手札にそのポケモンカードがありません'
      };
    }

    // すでにアクティブポケモンがいるかチェック（簡略版では交代なし）
    if (player.activePokemon) {
      return {
        success: false,
        error: 'すでにアクティブポケモンがいます'
      };
    }

    // 手札から削除
    const newHand = player.hand.filter(c => c.id !== action.cardId);
    
    // アクティブに配置
    const fieldPokemon = createFieldPokemon(card as PokemonCard);

    const newPlayer: Player = {
      ...player,
      hand: newHand,
      activePokemon: fieldPokemon
    };

    const newState: GameState = {
      ...state,
      players: {
        ...state.players,
        [action.playerId]: newPlayer
      }
    };

    return {
      success: true,
      newState,
      logs: [`${card.name}を場に出しました`]
    };
  }

  /**
   * エネルギーを付けるアクションを実行
   */
  private executeAttachEnergy(state: GameState, action: AttachEnergyAction): ActionResult {
    const player = state.players[action.playerId];
    
    // 手札にそのエネルギーカードがあるかチェック
    const energyCard = this.gameRule.findCardInHand(player, action.energyCardId);
    if (!energyCard || energyCard.type !== 'ENERGY') {
      return {
        success: false,
        error: '手札にそのエネルギーカードがありません'
      };
    }

    // アクティブポケモンがいるかチェック
    if (!player.activePokemon) {
      return {
        success: false,
        error: 'アクティブポケモンがいません'
      };
    }

    // 手札から削除
    const newHand = player.hand.filter(c => c.id !== action.energyCardId);
    
    // ポケモンにエネルギーを付ける
    const newActivePokemon = {
      ...player.activePokemon,
      attachedEnergy: [...player.activePokemon.attachedEnergy, energyCard as EnergyCard]
    };

    const newPlayer: Player = {
      ...player,
      hand: newHand,
      activePokemon: newActivePokemon
    };

    const newState: GameState = {
      ...state,
      players: {
        ...state.players,
        [action.playerId]: newPlayer
      }
    };

    return {
      success: true,
      newState,
      logs: [`${energyCard.name}を${player.activePokemon.card.name}に付けました`]
    };
  }

  /**
   * 攻撃アクションを実行
   */
  private executeAttack(state: GameState, action: AttackAction): ActionResult {
    const player = state.players[action.playerId];
    
    // アクティブポケモンがいるかチェック
    if (!player.activePokemon) {
      return {
        success: false,
        error: 'アクティブポケモンがいません'
      };
    }

    // ワザが使用可能かチェック
    if (!this.gameRule.canUseAttack(player.activePokemon, action.attackIndex)) {
      return {
        success: false,
        error: 'エネルギーが足りません'
      };
    }

    const attack = player.activePokemon.card.attacks[action.attackIndex];
    
    // 効果を解決
    const effectResult = this.effectResolver.resolveEffects(
      state,
      attack.effects,
      action.playerId
    );

    const logs = [
      `${player.activePokemon.card.name}の${attack.name}！`,
      ...effectResult.logs
    ];

    return {
      success: true,
      newState: effectResult.newState,
      logs
    };
  }

  /**
   * ターン終了アクションを実行
   */
  private executeEndTurn(state: GameState, action: EndTurnAction): ActionResult {
    const nextPlayer: 'PLAYER' | 'CPU' = state.currentTurn === 'PLAYER' ? 'CPU' : 'PLAYER';

    const newState: GameState = {
      ...state,
      currentTurn: nextPlayer,
      turnCount: nextPlayer === 'PLAYER' ? state.turnCount + 1 : state.turnCount,
      phase: 'DRAW'  // 次のターンのドローフェーズへ
    };

    return {
      success: true,
      newState,
      logs: [`ターン終了。${nextPlayer}のターン`]
    };
  }
}
