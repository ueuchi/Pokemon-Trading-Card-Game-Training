/**
 * CPU AI Service
 *
 * 役割：
 * - CPUの行動を決定する
 * - ルールベースの簡易AI
 *
 * 設計方針：
 * - 複雑なAIは不要（賢さより安定性）
 * - 優先順位ベースの決定
 * - 同じActionインターフェースを使用
 *
 * AI の優先順位：
 * 1. アクティブポケモンがいなければ場に出す
 * 2. 相手を倒せる攻撃があれば攻撃
 * 3. 攻撃できるなら攻撃
 * 4. エネルギーが足りなければ付ける
 * 5. それ以外はターン終了
 */

import { Injectable } from '@angular/core';
import {
  GameState,
  Player,
  FieldPokemon,
  PokemonCard,
  EnergyCard,
} from '../types/game-state.types';
import { Action } from '../types/action.types';
import { GameRuleService } from './game-rule.service';
import { TurnManagerService } from './turn-manager.service';

@Injectable({
  providedIn: 'root',
})
export class CpuAiService {
  constructor(
    private gameRule: GameRuleService,
    private turnManager: TurnManagerService,
  ) {}

  /**
   * CPUの次の行動を決定
   *
   * @param state 現在のGameState
   * @returns 実行するAction
   */
  decideAction(state: GameState): Action {
    const cpu = state.players.CPU;
    const player = state.players.PLAYER;

    // 優先度1: アクティブポケモンがいなければ場に出す
    if (!cpu.activePokemon) {
      const pokemonCard = this.findPokemonInHand(cpu);
      if (pokemonCard) {
        return {
          type: 'PLAY_POKEMON',
          playerId: 'CPU',
          cardId: pokemonCard.id,
          position: 'ACTIVE',
        };
      }
    }

    // 優先度2: 相手を倒せる攻撃があれば実行
    if (cpu.activePokemon && player.activePokemon) {
      const lethalAttack = this.findLethalAttack(cpu.activePokemon, player.activePokemon);
      if (lethalAttack !== null && !this.turnManager.hasAttackedThisTurn()) {
        return {
          type: 'ATTACK',
          playerId: 'CPU',
          attackIndex: lethalAttack,
        };
      }
    }

    // 優先度3: 攻撃できるなら最大ダメージの攻撃を選択
    if (cpu.activePokemon && !this.turnManager.hasAttackedThisTurn()) {
      const attackIndex = this.findBestAttack(cpu.activePokemon);
      if (attackIndex !== null) {
        return {
          type: 'ATTACK',
          playerId: 'CPU',
          attackIndex,
        };
      }
    }

    // 優先度4: エネルギーを付けられるなら付ける
    if (cpu.activePokemon && !this.turnManager.hasAttachedEnergyThisTurn()) {
      const energyCard = this.findBestEnergyInHand(cpu, cpu.activePokemon);
      if (energyCard) {
        return {
          type: 'ATTACH_ENERGY',
          playerId: 'CPU',
          energyCardId: energyCard.id,
          targetPokemonId: cpu.activePokemon.card.id,
          targetPosition: 'ACTIVE',
        };
      }
    }

    // 優先度5: それ以外はターン終了
    return {
      type: 'END_TURN',
      playerId: 'CPU',
    };
  }

  /**
   * 手札からポケモンカードを探す
   */
  private findPokemonInHand(player: Player): PokemonCard | null {
    const pokemon = player.hand.find((card) => card.type === 'POKEMON');
    return pokemon ? (pokemon as PokemonCard) : null;
  }

  /**
   * 相手を倒せる攻撃を探す
   *
   * @returns 倒せる攻撃のインデックス、なければnull
   */
  private findLethalAttack(attacker: FieldPokemon, defender: FieldPokemon): number | null {
    for (let i = 0; i < attacker.card.attacks.length; i++) {
      if (!this.gameRule.canUseAttack(attacker, i)) {
        continue;
      }

      const attack = attacker.card.attacks[i];
      const damage = this.calculateTotalDamage(attack.effects);

      // 相手のHPを削りきれるか
      if (damage >= defender.currentHp) {
        return i;
      }
    }

    return null;
  }

  /**
   * 使用可能な最大ダメージの攻撃を探す
   *
   * @returns 最適な攻撃のインデックス、なければnull
   */
  private findBestAttack(pokemon: FieldPokemon): number | null {
    let bestIndex: number | null = null;
    let maxDamage = 0;

    for (let i = 0; i < pokemon.card.attacks.length; i++) {
      if (!this.gameRule.canUseAttack(pokemon, i)) {
        continue;
      }

      const attack = pokemon.card.attacks[i];
      const damage = this.calculateTotalDamage(attack.effects);

      if (damage > maxDamage) {
        maxDamage = damage;
        bestIndex = i;
      }
    }

    return bestIndex;
  }

  /**
   * 効果から合計ダメージを計算（簡易版）
   */
  private calculateTotalDamage(effects: any[]): number {
    let totalDamage = 0;

    for (const effect of effects) {
      if (effect.type === 'DAMAGE') {
        totalDamage += effect.amount;
      }
      // 条件付き効果は期待値で計算（50%）
      if (effect.type === 'CONDITIONAL' && effect.successEffects) {
        for (const successEffect of effect.successEffects) {
          if (successEffect.type === 'DAMAGE') {
            totalDamage += successEffect.amount * 0.5; // 期待値
          }
        }
      }
    }

    return totalDamage;
  }

  /**
   * 手札から最適なエネルギーを探す
   *
   * 優先順位：
   * 1. ポケモンのタイプと一致するエネルギー
   * 2. 無色エネルギー
   * 3. その他のエネルギー
   */
  private findBestEnergyInHand(player: Player, pokemon: FieldPokemon): EnergyCard | null {
    const energyCards = player.hand.filter((card) => card.type === 'ENERGY') as EnergyCard[];

    if (energyCards.length === 0) {
      return null;
    }

    // ポケモンのタイプと一致するエネルギーを優先
    const matchingEnergy = energyCards.find(
      (energy) => energy.energyType === pokemon.card.energyType,
    );
    if (matchingEnergy) {
      return matchingEnergy;
    }

    // 無色エネルギー
    const colorlessEnergy = energyCards.find((energy) => energy.energyType === 'COLORLESS');
    if (colorlessEnergy) {
      return colorlessEnergy;
    }

    // その他のエネルギー
    return energyCards[0];
  }

  /**
   * デバッグ用：CPUの思考過程を出力
   */
  debugThinking(state: GameState): string[] {
    const logs: string[] = [];
    const cpu = state.players.CPU;
    const player = state.players.PLAYER;

    logs.push('=== CPU 思考中 ===');

    if (!cpu.activePokemon) {
      logs.push('判断: アクティブポケモンがいない → ポケモンを出す');
      return logs;
    }

    if (player.activePokemon) {
      const lethalAttack = this.findLethalAttack(cpu.activePokemon, player.activePokemon);
      if (lethalAttack !== null) {
        logs.push(`判断: 相手を倒せる → ワザ${lethalAttack}を使用`);
        return logs;
      }
    }

    const bestAttack = this.findBestAttack(cpu.activePokemon);
    if (bestAttack !== null && !this.turnManager.hasAttackedThisTurn()) {
      logs.push(`判断: 攻撃可能 → ワザ${bestAttack}を使用`);
      return logs;
    }

    if (!this.turnManager.hasAttachedEnergyThisTurn()) {
      const energy = this.findBestEnergyInHand(cpu, cpu.activePokemon);
      if (energy) {
        logs.push('判断: エネルギー不足 → エネルギーを付ける');
        return logs;
      }
    }

    logs.push('判断: 有効な行動なし → ターン終了');
    return logs;
  }
}
