/**
 * Deck Builder Service
 *
 * 役割：
 * - デッキの作成・保存・管理
 * - デッキのバリデーション
 * - ローカルストレージでの永続化
 */

import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable } from 'rxjs';
import { Deck, DeckCard, DeckValidation, DECK_CONSTRAINTS } from '../types/deck.types';
import { Card } from '../types/game-state.types';

@Injectable({
  providedIn: 'root',
})
export class DeckBuilderService {
  // 保存されたデッキのリスト
  private decksSubject = new BehaviorSubject<Deck[]>([]);
  public decks$: Observable<Deck[]> = this.decksSubject.asObservable();

  constructor() {
    this.loadFromLocalStorage();
  }

  /**
   * 新しいデッキを作成
   */
  createDeck(name: string, description?: string): Deck {
    const deck: Deck = {
      id: this.generateDeckId(),
      name,
      description,
      cards: [],
      createdAt: new Date(),
      updatedAt: new Date(),
    };

    return deck;
  }

  /**
   * デッキを保存
   */
  saveDeck(deck: Deck): boolean {
    // バリデーション
    const validation = this.validateDeck(deck);
    if (!validation.valid) {
      console.error('デッキのバリデーションエラー:', validation.errors);
      return false;
    }

    const currentDecks = this.decksSubject.value;
    const existingIndex = currentDecks.findIndex((d) => d.id === deck.id);

    deck.updatedAt = new Date();

    let updatedDecks: Deck[];
    if (existingIndex >= 0) {
      // 既存のデッキを更新
      updatedDecks = [...currentDecks];
      updatedDecks[existingIndex] = deck;
    } else {
      // 新しいデッキを追加
      updatedDecks = [...currentDecks, deck];
    }

    this.decksSubject.next(updatedDecks);
    this.saveToLocalStorage(updatedDecks);
    return true;
  }

  /**
   * デッキを削除
   */
  deleteDeck(deckId: string): void {
    const currentDecks = this.decksSubject.value;
    const updatedDecks = currentDecks.filter((deck) => deck.id !== deckId);

    this.decksSubject.next(updatedDecks);
    this.saveToLocalStorage(updatedDecks);
  }

  /**
   * すべてのデッキを取得
   */
  getAllDecks(): Deck[] {
    return this.decksSubject.value;
  }

  /**
   * デッキIDでデッキを取得
   */
  getDeckById(deckId: string): Deck | null {
    return this.decksSubject.value.find((deck) => deck.id === deckId) || null;
  }

  /**
   * デッキにカードを追加
   */
  addCardToDeck(deck: Deck, card: Card, count: number = 1): boolean {
    console.warn('デッキにカード追加', card, count);
    // 既にデッキに含まれているか確認
    const existingCard = deck.cards.find((dc) => dc.card.id === card.id);

    if (existingCard) {
      // 既にある場合は枚数を増やす
      const newCount = existingCard.count + count;

      // 同じカードの上限チェック
      if (card.type !== 'ENERGY' && newCount > DECK_CONSTRAINTS.MAX_SAME_CARD) {
        return false;
      }

      existingCard.count = newCount;
    } else {
      // 新しいカードを追加
      if (count > DECK_CONSTRAINTS.MAX_SAME_CARD) {
        return false;
      }

      deck.cards.push({
        card,
        count,
      });
    }

    // 合計枚数チェック
    const totalCards = this.getTotalCardCount(deck);
    if (totalCards > DECK_CONSTRAINTS.MAX_CARDS) {
      // 元に戻す
      if (existingCard) {
        existingCard.count -= count;
      } else {
        deck.cards.pop();
      }
      return false;
    }

    return true;
  }

  /**
   * デッキからカードを削除
   */
  removeCardFromDeck(deck: Deck, cardId: string, count: number = 1): void {
    const cardIndex = deck.cards.findIndex((dc) => dc.card.id === cardId);

    if (cardIndex >= 0) {
      deck.cards[cardIndex].count -= count;

      // 0枚以下になったら削除
      if (deck.cards[cardIndex].count <= 0) {
        deck.cards.splice(cardIndex, 1);
      }
    }
  }

  /**
   * デッキの合計カード枚数を取得
   */
  getTotalCardCount(deck: Deck): number {
    return deck.cards.reduce((total, deckCard) => total + deckCard.count, 0);
  }

  /**
   * デッキのバリデーション
   */
  validateDeck(deck: Deck): DeckValidation {
    const errors: string[] = [];
    const warnings: string[] = [];

    // 合計枚数チェック
    const totalCards = this.getTotalCardCount(deck);
    if (totalCards !== DECK_CONSTRAINTS.TOTAL_CARDS) {
      errors.push(
        `デッキは${DECK_CONSTRAINTS.TOTAL_CARDS}枚である必要があります（現在${totalCards}枚）`,
      );
    }

    // 同じカードの枚数チェック
    // for (const deckCard of deck.cards) {
    //   if (deckCard.count > DECK_CONSTRAINTS.MAX_SAME_CARD) {
    //     errors.push(
    //       `${deckCard.card.name}が${DECK_CONSTRAINTS.MAX_SAME_CARD}枚を超えています（${deckCard.count}枚）`,
    //     );
    //   }
    // }

    // ポケモンカードが含まれているかチェック
    const pokemonCount = deck.cards
      .filter((dc) => dc.card.type === 'POKEMON')
      .reduce((total, dc) => total + dc.count, 0);

    if (pokemonCount < DECK_CONSTRAINTS.MIN_POKEMON) {
      errors.push(
        `ポケモンカードが最低${DECK_CONSTRAINTS.MIN_POKEMON}枚必要です（現在${pokemonCount}枚）`,
      );
    }

    // 警告：エネルギーバランス
    const energyCount = deck.cards
      .filter((dc) => dc.card.type === 'ENERGY')
      .reduce((total, dc) => total + dc.count, 0);

    if (energyCount < 15) {
      warnings.push('エネルギーカードが少ない可能性があります');
    }

    if (energyCount > 30) {
      warnings.push('エネルギーカードが多すぎる可能性があります');
    }

    return {
      valid: errors.length === 0,
      errors,
      warnings,
    };
  }

  /**
   * デッキIDを生成
   */
  private generateDeckId(): string {
    return `deck-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * ローカルストレージに保存
   */
  private saveToLocalStorage(decks: Deck[]): void {
    try {
      // Dateオブジェクトを文字列に変換
      const serializedDecks = decks.map((deck) => ({
        ...deck,
        createdAt: deck.createdAt.toISOString(),
        updatedAt: deck.updatedAt.toISOString(),
      }));

      localStorage.setItem('decks', JSON.stringify(serializedDecks));
    } catch (error) {
      console.error('デッキの保存に失敗しました', error);
    }
  }

  /**
   * ローカルストレージから読み込み
   */
  private loadFromLocalStorage(): void {
    try {
      const saved = localStorage.getItem('decks');
      if (saved) {
        const parsedDecks = JSON.parse(saved);

        // 文字列をDateオブジェクトに変換
        const decks = parsedDecks.map((deck: any) => ({
          ...deck,
          createdAt: new Date(deck.createdAt),
          updatedAt: new Date(deck.updatedAt),
        }));

        this.decksSubject.next(decks);
      }
    } catch (error) {
      console.error('デッキの読み込みに失敗しました', error);
    }
  }

  /**
   * すべてのデッキをクリア
   */
  clearAllDecks(): void {
    this.decksSubject.next([]);
    localStorage.removeItem('decks');
  }
}
