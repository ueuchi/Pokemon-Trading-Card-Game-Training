/**
 * カード作成用の型定義
 *
 * UIでカードを作成するための選択肢と設定
 */

import { EnergyType, Effect, Target1, Target2, Target3 } from './game-state.types';

/**
 * カード作成フォームのデータ
 */
export interface CardCreationForm {
  // 基本情報
  name: string;
  cardType: 'POKEMON' | 'TRAINER' | 'ENERGY';

  // ポケモンカード用;
  /** 進化状態 */
  evolution: 'BASIC' | 'STAGE1' | 'STAGE2';
  /** ポケモンのルール */
  monsterRule?: 'ex' | 'メガシンカex';
  hp?: number;
  energyType?: EnergyType;
  retreatCost?: number;
  target1?: Target1;
  target2?: Target2;
  target3?: Target3;

  // ワザ（最大2個）
  attacks?: AttackCreationForm[];
}

/**
 * ワザ作成フォームのデータ
 */
export interface AttackCreationForm {
  name: string;
  energyCosts: EnergyCostForm[];
  effects: EffectCreationForm[];
}

/**
 * エネルギーコストフォーム
 */
export interface EnergyCostForm {
  type: EnergyType;
  amount: number;
}

/**
 * 効果作成フォームのデータ
 */
export interface EffectCreationForm {
  effectType: 'DAMAGE' | 'HEAL' | 'DRAW' | 'CONDITIONAL';

  // DAMAGE用
  damageAmount?: number;

  // HEAL用
  healAmount?: number;

  // DRAW用
  drawAmount?: number;

  // CONDITIONAL用
  condition?: 'COIN_FLIP';
  successEffects?: EffectCreationForm[];
}

/**
 * カード作成用のプリセット（選択肢）
 */
export const CARD_PRESETS = {
  // 進化段階の選択肢
  EVOLUTION_OPTIONS: [
    { value: 'BASIC', label: 'たね' },
    { value: 'STAGE1', label: '第1進化' },
    { value: 'STAGE2', label: '第2進化' },
  ],

  // ポケモンのルールの選択肢
  MONSTER_RULE_OPTIONS: [
    { value: 'ex', label: 'ex' },
    { value: 'mega', label: 'メガシンカex' },
  ],

  // HPの選択肢
  HP_OPTIONS: [30, 40, 50, 60, 70, 80, 90, 100],

  // 逃げるコストの選択肢
  RETREAT_COST_OPTIONS: [0, 1, 2, 3],

  // エネルギータイプの選択肢
  ENERGY_TYPE_OPTIONS: [
    { value: 'FIRE', label: 'ほのお', color: 'var(--color_fire)' },
    { value: 'WATER', label: 'みず', color: '#2196f3' },
    { value: 'GRASS', label: 'くさ', color: '#4caf50' },
    { value: 'ELECTRIC', label: 'でんき', color: '#ffeb3b' },
    { value: 'FIGHT', label: '闘', color: '#ffeb3b' },
    { value: 'SUPER', label: '超', color: '#ffeb3b' },
    { value: 'DARK', label: '悪', color: '#ffeb3b' },
    { value: 'DRAGON', label: 'ドラゴン', color: '#ffeb3b' },
    { value: 'COLORLESS', label: '無色', color: '#9e9e9e' },
  ],

  // ダメージ量の選択肢
  DAMAGE_OPTIONS: [10, 20, 30, 40, 50, 60, 70, 80, 90, 100],

  // 回復量の選択肢
  HEAL_OPTIONS: [10, 20, 30, 40, 50],

  // ドロー枚数の選択肢
  DRAW_OPTIONS: [1, 2, 3],

  // 効果タイプの選択肢
  EFFECT_TYPE_OPTIONS: [
    { value: 'DAMAGE', label: 'ダメージを与える' },
    { value: 'DAMAGE_COUNT', label: 'ダメージカウントを乗せる' },
    { value: 'ENERGY', label: 'エネルギーをつける' },
    { value: 'HEAL', label: 'ポケモンを回復' },
    { value: 'CHANGE', label: 'ポケモンを入れ替える' },
    { value: 'DRAW', label: 'カードを引く' },
    { value: 'CHOICE', label: 'カードを選んで引く' },
    { value: 'DROP', label: 'カードを捨てる' },
    { value: 'RETURN', label: 'カードを戻す' },
    // { value: 'CONDITIONAL', label: 'コイン投げ（条件付き）' },
  ],

  // ワザ名のサンプル
  ATTACK_NAME_SAMPLES: [
    'ひっかく',
    'たいあたり',
    'かみつく',
    'ほのお',
    'みずでっぽう',
    'はっぱカッター',
    'でんきショック',
    '10まんボルト',
    'ハイドロポンプ',
    'だいもんじ',
    'ソーラービーム',
    'かみなり',
  ],

  TARGET1: [
    { value: 'SELF', label: '自分' },
    { value: 'ENEMY', label: '相手' },
    { value: 'ALL', label: '全員' },
  ],

  TARGET2: [
    { value: 'BATTLE', label: 'バトル場' },
    { value: 'BENCH', label: 'ベンチ' },
    { value: 'ALL', label: 'すべて' },
  ],

  TARGET3: [
    { value: 'DECK', label: '山札' },
    { value: 'TRASH', label: 'トラッシュ' },
    { value: 'HAND', label: '手札' },
    { value: 'DRAW_CARD', label: '引いたカード' },
  ],

  TARGET4: [
    { value: 'POKEMON', label: 'ポケモン' },
    { value: 'TRAINER', label: 'トレーナー' },
    { value: 'ENERGY', label: 'エネルギー' },
    { value: 'ALL', label: 'すべて' },
  ],

  SITUATIONS: [
    { value: 'ANYTIME', label: 'いつでも' },
    { value: 'WIN', label: '勝ってる時' },
    { value: 'LOSE', label: '負けてる時' },
    { value: 'FIRST_TURN', label: '最初のターン' },
  ],
};

/**
 * カードIDを生成
 */
export function generateCardId(name: string, type: string): string {
  const timestamp = Date.now();
  const sanitizedName = name.toLowerCase().replace(/\s+/g, '-');
  return `${sanitizedName}-${type.toLowerCase()}-${timestamp}`;
}
