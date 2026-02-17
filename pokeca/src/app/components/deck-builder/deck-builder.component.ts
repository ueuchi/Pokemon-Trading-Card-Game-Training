/**
 * Deck Builder Component
 *
 * 役割：
 * - デッキの作成・編集
 * - カードの追加・削除
 * - デッキのバリデーション
 */

import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { DeckBuilderService } from '../../game/services/deck-builder.service';
import { CardCreatorService } from '../../game/services/card-creator.service';
import { Deck, DeckCard, DECK_CONSTRAINTS } from '../../game/types/deck.types';
import { Card } from '../../game/types/game-state.types';
import {
  createPlayerDeck,
  createCPUDeck,
  PIKACHU,
  CHARMANDER,
  SQUIRTLE,
  ELECTRIC_ENERGY,
  FIRE_ENERGY,
  WATER_ENERGY,
  COLORLESS_ENERGY,
} from '../../game/data/test-cards.data';

@Component({
  selector: 'deck-builder',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './deck-builder.component.html',
  styleUrl: './deck-builder.component.scss',
})
export class DeckBuilderComponent implements OnInit {
  // 定数をテンプレートで使用できるようにする
  readonly CONSTRAINTS = DECK_CONSTRAINTS;

  // 利用可能なカード（デフォルト + カスタム）
  availableCards: Card[] = [];

  // カスタムカード
  customCards: Card[] = [];

  // 保存済みデッキ
  savedDecks: Deck[] = [];

  // 現在編集中のデッキ
  currentDeck: Deck | null = null;

  // 新規デッキ作成モード
  isCreatingNewDeck = false;

  // 新規デッキの情報
  newDeckName = '';
  newDeckDescription = '';

  // フィルター
  filterType: 'ALL' | 'POKEMON' | 'TRAINER' | 'ENERGY' = 'ALL';
  searchQuery = '';

  constructor(
    protected deckBuilderService: DeckBuilderService,
    protected cardCreatorService: CardCreatorService,
  ) {}

  ngOnInit(): void {
    // デフォルトカードを読み込み
    this.loadDefaultCards();

    // カスタムカードを監視
    this.cardCreatorService.customCards$.subscribe((cards) => {
      this.customCards = cards;
      this.updateAvailableCards();
    });

    // 保存済みデッキを監視
    this.deckBuilderService.decks$.subscribe((decks) => {
      this.savedDecks = decks;
    });
  }

  /**
   * デフォルトカードを読み込み
   */
  private loadDefaultCards(): void {
    const defaultCards: Card[] = [
      { ...PIKACHU, id: 'default-pikachu-1' },
      { ...CHARMANDER, id: 'default-charmander-1' },
      { ...SQUIRTLE, id: 'default-squirtle-1' },
      { ...ELECTRIC_ENERGY, id: 'default-electric-energy' },
      { ...FIRE_ENERGY, id: 'default-fire-energy' },
      { ...WATER_ENERGY, id: 'default-water-energy' },
      { ...COLORLESS_ENERGY, id: 'default-colorless-energy' },
    ];

    this.availableCards = [...defaultCards];
  }

  /**
   * 利用可能なカードを更新
   */
  private updateAvailableCards(): void {
    this.loadDefaultCards();
    this.availableCards = [...this.availableCards, ...this.customCards];
  }

  /**
   * 新規デッキ作成を開始
   */
  startNewDeck(): void {
    this.isCreatingNewDeck = true;
    this.newDeckName = '';
    this.newDeckDescription = '';
  }

  /**
   * 新規デッキを作成
   */
  createNewDeck(): void {
    if (!this.newDeckName.trim()) {
      alert('デッキ名を入力してください');
      return;
    }

    this.currentDeck = this.deckBuilderService.createDeck(
      this.newDeckName,
      this.newDeckDescription,
    );

    this.isCreatingNewDeck = false;
    this.newDeckName = '';
    this.newDeckDescription = '';
  }

  /**
   * デッキ作成をキャンセル
   */
  cancelNewDeck(): void {
    this.isCreatingNewDeck = false;
    this.newDeckName = '';
    this.newDeckDescription = '';
  }

  /**
   * 既存のデッキを編集
   */
  editDeck(deck: Deck): void {
    this.currentDeck = JSON.parse(JSON.stringify(deck)); // ディープコピー
  }

  /**
   * デッキを保存
   */
  saveDeck(): void {
    if (!this.currentDeck) return;

    const success = this.deckBuilderService.saveDeck(this.currentDeck);

    if (success) {
      alert(`デッキ「${this.currentDeck.name}」を保存しました`);
      this.currentDeck = null;
    } else {
      const validation = this.deckBuilderService.validateDeck(this.currentDeck);
      alert(`保存に失敗しました:\n${validation.errors.join('\n')}`);
    }
  }

  /**
   * デッキ編集をキャンセル
   */
  cancelEdit(): void {
    if (confirm('編集内容を破棄しますか？')) {
      this.currentDeck = null;
    }
  }

  /**
   * デッキを削除
   */
  deleteDeck(deckId: string): void {
    if (confirm('このデッキを削除しますか？')) {
      this.deckBuilderService.deleteDeck(deckId);
    }
  }

  /**
   * デッキにカードを追加
   */
  addCardToDeck(card: Card): void {
    console.warn('カード追加');
    if (!this.currentDeck) return;

    const success = this.deckBuilderService.addCardToDeck(this.currentDeck, card, 1);

    if (!success) {
      const totalCards = this.getTotalCardCount();
      if (totalCards >= DECK_CONSTRAINTS.MAX_CARDS) {
        alert(`デッキは${DECK_CONSTRAINTS.MAX_CARDS}枚までです`);
      } else {
        alert(`このカードは${DECK_CONSTRAINTS.MAX_SAME_CARD}枚までです`);
      }
    }
  }

  /**
   * デッキからカードを削除
   */
  removeCardFromDeck(cardId: string): void {
    if (!this.currentDeck) return;
    this.deckBuilderService.removeCardFromDeck(this.currentDeck, cardId, 1);
  }

  /**
   * デッキの合計カード枚数を取得
   */
  getTotalCardCount(): number {
    if (!this.currentDeck) return 0;
    return this.deckBuilderService.getTotalCardCount(this.currentDeck);
  }

  /**
   * デッキ内の特定カードの枚数を取得
   */
  getCardCountInDeck(cardId: string): number {
    if (!this.currentDeck) return 0;
    const deckCard = this.currentDeck.cards.find((dc) => dc.card.id === cardId);
    return deckCard ? deckCard.count : 0;
  }

  /**
   * フィルタリングされたカードリストを取得
   */
  get filteredCards(): Card[] {
    let cards = this.availableCards;

    // タイプフィルター
    if (this.filterType !== 'ALL') {
      cards = cards.filter((card) => card.type === this.filterType);
    }

    // 検索フィルター
    if (this.searchQuery.trim()) {
      const query = this.searchQuery.toLowerCase();
      cards = cards.filter((card) => card.name.toLowerCase().includes(query));
    }

    return cards;
  }

  /**
   * デッキが保存可能か
   */
  get canSaveDeck(): boolean {
    if (!this.currentDeck) return false;
    const validation = this.deckBuilderService.validateDeck(this.currentDeck);
    return validation.valid;
  }

  /**
   * デッキのバリデーションメッセージを取得
   */
  get validationMessages(): string[] {
    if (!this.currentDeck) return [];
    const validation = this.deckBuilderService.validateDeck(this.currentDeck);
    return [...validation.errors, ...validation.warnings];
  }

  /**
   * カードタイプの日本語名を取得
   */
  getCardTypeName(card: Card): string {
    if (card.type === 'POKEMON') return 'ポケモン';
    if (card.type === 'TRAINER') return 'トレーナー';
    if (card.type === 'ENERGY') return 'エネルギー';
    return 'その他';
  }

  /**
   * エネルギータイプの日本語名を取得
   */
  getEnergyTypeName(type: string): string {
    const names: Record<string, string> = {
      FIRE: 'ほのお',
      WATER: 'みず',
      GRASS: 'くさ',
      ELECTRIC: 'でんき',
      COLORLESS: '無色',
    };
    return names[type] || type;
  }

  /**
   * カードカウント
   */
  getPokemonCount(i: number) {
    return this.savedDecks[i].cards.filter((dc) => dc.card.type === 'POKEMON').length;
  }
  /**
   * エネルギーカウント
   */
  getTrainerCount(i: number) {
    return this.savedDecks[i].cards.filter((dc) => dc.card.type === 'TRAINER').length;
  }
  /**
   * エネルギーカウント
   */
  getEnergieCount(i: number) {
    return this.savedDecks[i].cards.filter((dc) => dc.card.type === 'ENERGY').length;
  }
}
