import { Injectable } from '@angular/core';
import { PokemonCard } from '../../models/card.model';
import {
  EditingDeck,
  DECK_CONSTRAINTS,
  getTotalCount,
  getCardFilterCategory,
  isBasicEnergy,
} from '../types/deck.types';

@Injectable({ providedIn: 'root' })
export class DeckBuilderService {
  /** カードをデッキに1枚追加。成功したら true を返す */
  addCard(deck: EditingDeck, card: PokemonCard): boolean {
    const current = deck.cardCounts.get(card.id) ?? 0;
    const total = getTotalCount(deck);

    if (total >= DECK_CONSTRAINTS.TOTAL_CARDS) return false;
    // 基本エネルギーは枚数制限なし
    if (!isBasicEnergy(card) && current >= DECK_CONSTRAINTS.MAX_SAME_CARD) return false;

    deck.cardCounts.set(card.id, current + 1);
    deck.cardMap.set(card.id, card);
    return true;
  }

  /** カードをデッキから1枚削除。0になったらエントリを削除 */
  removeCard(deck: EditingDeck, cardId: number): void {
    const current = deck.cardCounts.get(cardId) ?? 0;
    if (current <= 1) {
      deck.cardCounts.delete(cardId);
      deck.cardMap.delete(cardId);
    } else {
      deck.cardCounts.set(cardId, current - 1);
    }
  }

  /** デッキ内の合計枚数 */
  getTotalCount(deck: EditingDeck): number {
    return getTotalCount(deck);
  }

  /** デッキ内の特定カードの枚数（0なら未投入） */
  getCardCount(deck: EditingDeck, cardId: number): number {
    return deck.cardCounts.get(cardId) ?? 0;
  }

  /** バリデーション結果を返す */
  validate(deck: EditingDeck): { valid: boolean; errors: string[]; warnings: string[] } {
    const errors: string[] = [];
    const warnings: string[] = [];

    if (!deck.name.trim()) errors.push('デッキ名を入力してください');

    const total = getTotalCount(deck);
    if (total > DECK_CONSTRAINTS.TOTAL_CARDS) {
      errors.push(
        `デッキは${DECK_CONSTRAINTS.TOTAL_CARDS}枚以内にしてください（現在: ${total}枚）`,
      );
    }
    if (total < DECK_CONSTRAINTS.TOTAL_CARDS) {
      warnings.push(
        `あと${DECK_CONSTRAINTS.TOTAL_CARDS - total}枚追加できます（現在: ${total}枚）`,
      );
    }
    if (total === 0) {
      errors.push('カードが1枚も入っていません');
    }

    // たねポケモンが1枚以上必要
    let hasBasic = false;
    deck.cardMap.forEach((card) => {
      if (card.evolution_stage === 'たね') hasBasic = true;
    });
    if (!hasBasic && total > 0) {
      warnings.push('たねポケモンが1枚も入っていません（対戦では必要です）');
    }

    return {
      valid: errors.length === 0 && total > 0,
      errors,
      warnings,
    };
  }

  /** デッキのカード種別カウント（一覧表示用） */
  getCategoryCounts(
    cards: { evolution_stage: string | null; card_type?: string | null; count: number }[],
  ): {
    pokemon: number;
    trainer: number;
    energy: number;
  } {
    let pokemon = 0,
      trainer = 0,
      energy = 0;
    cards.forEach(({ evolution_stage, card_type, count }) => {
      const cat = getCardFilterCategory(evolution_stage, card_type);
      if (cat === 'POKEMON') pokemon += count;
      else if (cat === 'TRAINER') trainer += count;
      else if (cat === 'ENERGY') energy += count;
    });
    return { pokemon, trainer, energy };
  }
}
