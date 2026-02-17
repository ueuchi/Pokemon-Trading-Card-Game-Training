/**
 * デッキ作成用の型定義
 */

import { Card } from './game-state.types';

/**
 * デッキ
 */
export interface Deck {
  id: string;
  name: string;
  description?: string;
  cards: DeckCard[];
  createdAt: Date;
  updatedAt: Date;
}

/**
 * デッキに含まれるカード（枚数情報付き）
 */
export interface DeckCard {
  card: Card;
  count: number;  // このカードが何枚入っているか
}

/**
 * デッキのバリデーション結果
 */
export interface DeckValidation {
  valid: boolean;
  errors: string[];
  warnings: string[];
}

/**
 * デッキの制約
 */
export const DECK_CONSTRAINTS = {
  TOTAL_CARDS: 60,           // デッキの合計枚数
  MIN_CARDS: 60,             // 最小枚数
  MAX_CARDS: 60,             // 最大枚数
  MAX_SAME_CARD: 4,          // 同じカードの最大枚数（通常4枚制限）
  MIN_POKEMON: 1             // 最低限必要なポケモンの枚数
};
