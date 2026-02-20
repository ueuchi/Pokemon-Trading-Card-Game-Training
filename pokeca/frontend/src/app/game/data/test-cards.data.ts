/**
 * テスト用カードデータ
 *
 * 実際のポケカ風のカードを数枚定義
 * 将来的にはJSONファイルから読み込む想定
 */

import {
  PokemonCard,
  EnergyCard,
  EnergyType,
  DamageEffect,
  ConditionalEffect,
} from '../types/game-state.types';

/**
 * ポケモンカード: ピカチュウ風
 *
 * HP: 60
 * タイプ: でんき
 * ワザ1: でんきショック (でんき1個) 20ダメージ
 * ワザ2: 10まんボルト (でんき2個) 50ダメージ
 */
export const PIKACHU: PokemonCard = {
  id: 'pikachu-001',
  name: 'ピカチュウ',
  type: 'POKEMON',
  evolution: 'BASIC',
  hp: 60,
  energyType: 'ELECTRIC',
  retreatCost: 1,
  attacks: [
    {
      name: 'でんきショック',
      energyCost: [{ type: 'ELECTRIC', amount: 1 }],
      effects: [
        {
          type: 'DAMAGE',
          amount: 20,
          target: 'ACTIVE',
        } as DamageEffect,
      ],
    },
    {
      name: '10まんボルト',
      energyCost: [{ type: 'ELECTRIC', amount: 2 }],
      effects: [
        {
          type: 'DAMAGE',
          amount: 50,
          target: 'ACTIVE',
        } as DamageEffect,
      ],
    },
  ],
};

/**
 * ポケモンカード: ヒトカゲ風
 *
 * HP: 50
 * タイプ: ほのお
 * ワザ1: ひっかく (無色1個) 10ダメージ
 * ワザ2: ひのこ (ほのお1個、無色1個) 30ダメージ
 */
export const CHARMANDER: PokemonCard = {
  id: 'charmander-001',
  name: 'ヒトカゲ',
  type: 'POKEMON',
  evolution: 'BASIC',
  hp: 50,
  energyType: 'FIRE',
  retreatCost: 1,
  attacks: [
    {
      name: 'ひっかく',
      energyCost: [{ type: 'COLORLESS', amount: 1 }],
      effects: [
        {
          type: 'DAMAGE',
          amount: 10,
          target: 'ACTIVE',
        } as DamageEffect,
      ],
    },
    {
      name: 'ひのこ',
      energyCost: [
        { type: 'FIRE', amount: 1 },
        { type: 'COLORLESS', amount: 1 },
      ],
      effects: [
        {
          type: 'DAMAGE',
          amount: 30,
          target: 'ACTIVE',
        } as DamageEffect,
      ],
    },
  ],
};

/**
 * ポケモンカード: ゼニガメ風
 *
 * HP: 50
 * タイプ: みず
 * ワザ1: あわ (みず1個) 10ダメージ
 * ワザ2: みずでっぽう (みず2個) 40ダメージ
 */
export const SQUIRTLE: PokemonCard = {
  id: 'squirtle-001',
  name: 'ゼニガメ',
  type: 'POKEMON',
  evolution: 'BASIC',
  hp: 50,
  energyType: 'WATER',
  retreatCost: 1,
  attacks: [
    {
      name: 'あわ',
      energyCost: [{ type: 'WATER', amount: 1 }],
      effects: [
        {
          type: 'DAMAGE',
          amount: 10,
          target: 'ACTIVE',
        } as DamageEffect,
      ],
    },
    {
      name: 'みずでっぽう',
      energyCost: [{ type: 'WATER', amount: 2 }],
      effects: [
        {
          type: 'DAMAGE',
          amount: 40,
          target: 'ACTIVE',
        } as DamageEffect,
      ],
    },
  ],
};

/**
 * エネルギーカード: でんきエネルギー
 */
export const ELECTRIC_ENERGY: EnergyCard = {
  id: 'energy-electric',
  name: 'でんきエネルギー',
  type: 'ENERGY',
  energyType: 'ELECTRIC',
};

/**
 * エネルギーカード: ほのおエネルギー
 */
export const FIRE_ENERGY: EnergyCard = {
  id: 'energy-fire',
  name: 'ほのおエネルギー',
  type: 'ENERGY',
  energyType: 'FIRE',
};

/**
 * エネルギーカード: みずエネルギー
 */
export const WATER_ENERGY: EnergyCard = {
  id: 'energy-water',
  name: 'みずエネルギー',
  type: 'ENERGY',
  energyType: 'WATER',
};
/**
 * エネルギーカード: 闘エネルギー
 */
export const FIGHT_ENERGY: EnergyCard = {
  id: 'energy-fight',
  name: '闘エネルギー',
  type: 'ENERGY',
  energyType: 'FIGHT',
};
/**
 * エネルギーカード: 超エネルギー
 */
export const SUPER_ENERGY: EnergyCard = {
  id: 'energy-super',
  name: '超エネルギー',
  type: 'ENERGY',
  energyType: 'SUPER',
};
/**
 * エネルギーカード: 悪エネルギー
 */
export const DARK_ENERGY: EnergyCard = {
  id: 'energy-dark',
  name: '悪エネルギー',
  type: 'ENERGY',
  energyType: 'DARK',
};

/**
 * エネルギーカード: 無色エネルギー
 */
export const COLORLESS_ENERGY: EnergyCard = {
  id: 'energy-colorless',
  name: '無色エネルギー',
  type: 'ENERGY',
  energyType: 'COLORLESS',
};

/**
 * テスト用デッキ作成ヘルパー
 *
 * 簡単なデッキを生成（ポケモン + エネルギー）
 */
export function createTestDeck(pokemonType: 'ELECTRIC' | 'FIRE' | 'WATER'): any[] {
  const deck: any[] = [];

  // ポケモンを3枚入れる
  if (pokemonType === 'ELECTRIC') {
    deck.push({ ...PIKACHU, id: 'pikachu-001' });
    deck.push({ ...PIKACHU, id: 'pikachu-002' });
    deck.push({ ...PIKACHU, id: 'pikachu-003' });
  } else if (pokemonType === 'FIRE') {
    deck.push({ ...CHARMANDER, id: 'charmander-001' });
    deck.push({ ...CHARMANDER, id: 'charmander-002' });
    deck.push({ ...CHARMANDER, id: 'charmander-003' });
  } else if (pokemonType === 'WATER') {
    deck.push({ ...SQUIRTLE, id: 'squirtle-001' });
    deck.push({ ...SQUIRTLE, id: 'squirtle-002' });
    deck.push({ ...SQUIRTLE, id: 'squirtle-003' });
  }

  // エネルギーを15枚入れる
  for (let i = 0; i < 15; i++) {
    if (pokemonType === 'ELECTRIC') {
      deck.push({ ...ELECTRIC_ENERGY, id: `energy-electric-${i}` });
    } else if (pokemonType === 'FIRE') {
      deck.push({ ...FIRE_ENERGY, id: `energy-fire-${i}` });
    } else if (pokemonType === 'WATER') {
      deck.push({ ...WATER_ENERGY, id: `energy-water-${i}` });
    }
  }

  // 無色エネルギーを5枚追加
  for (let i = 0; i < 5; i++) {
    deck.push({ ...COLORLESS_ENERGY, id: `energy-colorless-${i}` });
  }

  return deck;
}

/**
 * プレイヤー用デッキ（でんきタイプ）
 */
export function createPlayerDeck() {
  return createTestDeck('ELECTRIC');
}

/**
 * CPU用デッキ（ほのおタイプ）
 */
export function createCPUDeck() {
  return createTestDeck('FIRE');
}
