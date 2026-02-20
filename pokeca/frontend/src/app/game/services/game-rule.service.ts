/**
 * Game Rule Service
 *
 * 役割：
 * - ゲームのルール判定を行う
 * - 勝敗判定
 * - アクションが実行可能かの判定
 * - エネルギーコストのチェック
 *
 * 設計方針：
 * - 純粋関数として実装（副作用なし）
 * - 判定ロジックを一箇所に集約
 */

import { Injectable } from '@angular/core';
import {
  GameState,
  Player,
  FieldPokemon,
  Attack,
  EnergyCost,
  EnergyType,
  Card,
} from '../types/game-state.types';

@Injectable({
  providedIn: 'root',
})
export class GameRuleService {
  /**
   * 勝敗判定
   *
   * 勝利条件：
   * 1. 相手のアクティブポケモンが倒れて、ベンチにもいない
   * 2. 相手の山札が尽きた
   * 3. サイドを全て取った（簡略版では使わないかも）
   *
   * @returns 勝者のID、または null（ゲーム続行）
   */
  checkWinner(state: GameState): 'PLAYER' | 'CPU' | null {
    const player = state.players.PLAYER;
    const cpu = state.players.CPU;

    // 1. アクティブポケモンが倒れている判定
    const playerHasActivePokemon = this.hasValidActivePokemon(player);
    const cpuHasActivePokemon = this.hasValidActivePokemon(cpu);

    if (!cpuHasActivePokemon) {
      return 'PLAYER'; // CPUのポケモンが全滅 → プレイヤー勝利
    }

    if (!playerHasActivePokemon) {
      return 'CPU'; // プレイヤーのポケモンが全滅 → CPU勝利
    }

    // 2. 山札が尽きた判定
    if (player.deck.length === 0) {
      return 'CPU'; // プレイヤーの山札切れ → CPU勝利
    }

    if (cpu.deck.length === 0) {
      return 'PLAYER'; // CPUの山札切れ → プレイヤー勝利
    }

    // 3. サイド判定（簡略版では省略可）
    // if (player.prizes.length === 0) return 'PLAYER';
    // if (cpu.prizes.length === 0) return 'CPU';

    return null; // ゲーム続行
  }

  /**
   * アクティブポケモンが有効か（HP > 0）
   */
  private hasValidActivePokemon(player: Player): boolean {
    if (!player.activePokemon) {
      return false;
    }
    return player.activePokemon.currentHp > 0;
  }

  /**
   * ポケモンが倒れたかチェック
   */
  isPokemonKnockedOut(pokemon: FieldPokemon | null): boolean {
    if (!pokemon) {
      return true;
    }
    return pokemon.currentHp <= 0;
  }

  /**
   * ワザが使用可能かチェック
   *
   * 条件：
   * 1. 必要なエネルギーが足りている
   * 2. アクティブポケモンが存在する
   */
  canUseAttack(pokemon: FieldPokemon | null, attackIndex: number): boolean {
    if (!pokemon) {
      return false;
    }

    const attack = pokemon.card.attacks[attackIndex];
    if (!attack) {
      return false;
    }

    return this.hasEnoughEnergy(pokemon, attack.energyCost);
  }

  /**
   * エネルギーが足りているかチェック
   *
   * @param pokemon チェック対象のポケモン
   * @param costs 必要なエネルギーコスト
   * @returns 足りていればtrue
   */
  private hasEnoughEnergy(pokemon: FieldPokemon, costs: EnergyCost[]): boolean {
    // 付いているエネルギーをカウント
    const energyCount = this.countEnergy(pokemon.attachedEnergy);

    // 各コストをチェック
    for (const cost of costs) {
      if (cost.type === 'COLORLESS') {
        // 無色エネルギーは任意のエネルギーで支払える
        const totalEnergy = Object.values(energyCount).reduce((sum, count) => sum + count, 0);
        if (totalEnergy < cost.amount) {
          return false;
        }
      } else {
        // 特定のタイプのエネルギーが必要
        const available = energyCount[cost.type] || 0;
        if (available < cost.amount) {
          return false;
        }
      }
    }

    return true;
  }

  /**
   * エネルギーカードをタイプ別にカウント
   */
  private countEnergy(energyCards: any[]): Record<EnergyType, number> {
    const count: Record<EnergyType, number> = {
      FIRE: 0,
      WATER: 0,
      GRASS: 0,
      ELECTRIC: 0,
      FIGHT: 0,
      SUPER: 0,
      DARK: 0,
      COLORLESS: 0,
      SPECIAL: 0,
    };

    for (const energy of energyCards) {
      if (energy && energy.type === 'ENERGY' && energy.energyType) {
        const key = energy.energyType as EnergyType;
        if (key in count) {
          count[key] = (count[key] ?? 0) + 1;
        }
      }
    }

    return count;
  }

  /**
   * 手札にポケモンカードがあるかチェック
   */
  hasPokemonInHand(player: Player): boolean {
    return player.hand.some((card) => card.type === 'POKEMON');
  }

  /**
   * 手札にエネルギーカードがあるかチェック
   */
  hasEnergyInHand(player: Player): boolean {
    return player.hand.some((card) => card.type === 'ENERGY');
  }

  /**
   * 指定したIDのカードを手札から探す
   */
  findCardInHand(player: Player, cardId: string): Card | null {
    return player.hand.find((card) => card.id === cardId) || null;
  }

  /**
   * ワザの詳細情報を取得
   */
  getAttackInfo(pokemon: FieldPokemon, attackIndex: number): Attack | null {
    return pokemon.card.attacks[attackIndex] || null;
  }

  /**
   * エネルギーコストを文字列で表示
   * 例: "でんき2個、無色1個"
   */
  formatEnergyCost(costs: EnergyCost[]): string {
    const typeNames: Record<EnergyType, string> = {
      FIRE: 'ほのお',
      WATER: 'みず',
      GRASS: 'くさ',
      ELECTRIC: 'でんき',
      FIGHT: '闘',
      SUPER: '超',
      DARK: '悪',
      COLORLESS: '無色',
      SPECIAL: '特殊',
    };

    return costs.map((cost) => `${typeNames[cost.type]}${cost.amount}個`).join('、');
  }

  /**
   * デバッグ用：ポケモンの状態を文字列で表示
   */
  debugPokemonStatus(pokemon: FieldPokemon | null): string {
    if (!pokemon) {
      return 'なし';
    }

    const energyTypes = pokemon.attachedEnergy.map((e) => e.energyType).join(', ');

    return [
      `${pokemon.card.name}`,
      `HP: ${pokemon.currentHp}/${pokemon.card.hp}`,
      `エネルギー: [${energyTypes}] (${pokemon.attachedEnergy.length}個)`,
    ].join(' | ');
  }
}
