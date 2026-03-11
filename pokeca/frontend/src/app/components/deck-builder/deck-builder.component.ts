import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { CardService } from '../../game/services/card.service';
import { BASIC_ENERGIES } from '../../game/data/basic-energies.data';
import { DeckService } from '../../game/services/deck.service';
import { DeckBuilderService } from '../../game/services/deck-builder.service';
import { PokemonCard, getCardCategoryLabel, getTypeColor } from '../../models/card.model';
import {
  Deck,
  EditingDeck,
  DECK_CONSTRAINTS,
  newEditingDeck,
  toEditingDeck,
  toSaveRequest,
  getCardFilterCategory,
  isBasicEnergy,
} from '../../game/types/deck.types';

type FilterType = 'ALL' | 'POKEMON' | 'TRAINER' | 'ENERGY';

@Component({
  selector: 'deck-builder',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './deck-builder.component.html',
  styleUrl: './deck-builder.component.scss',
})
export class DeckBuilderComponent implements OnInit {
  readonly CONSTRAINTS = DECK_CONSTRAINTS;

  // 状態
  allCards: PokemonCard[] = [];
  readonly basicEnergies: PokemonCard[] = BASIC_ENERGIES;
  savedDecks: Deck[] = [];
  currentDeck: EditingDeck | null = null;
  isCreatingNewDeck = false;
  isLoading = false;
  isSaving = false;
  errorMessage = '';

  // 新規作成フォーム
  newDeckName = '';
  newDeckDescription = '';

  // フィルター
  filterType: FilterType = 'ALL';
  searchQuery = '';

  constructor(
    private cardService: CardService,
    private deckService: DeckService,
    protected deckBuilderService: DeckBuilderService,
  ) {}

  ngOnInit(): void {
    this.loadDecks();
    this.loadCards();
  }

  // ==================== データ読み込み ====================

  loadDecks(): void {
    this.deckService.getDecks().subscribe({
      next: (decks) => {
        this.savedDecks = decks ?? [];
      },
      error: (err) => {
        console.error('デッキ取得エラー:', err);
        this.errorMessage = 'デッキの取得に失敗しました';
      },
    });
  }

  loadCards(): void {
    this.isLoading = true;
    this.cardService.getCards().subscribe({
      next: (cards) => {
        this.allCards = cards;
        this.isLoading = false;
      },
      error: () => {
        this.errorMessage = 'カードの取得に失敗しました';
        this.isLoading = false;
      },
    });
  }

  // ==================== 画面遷移 ====================

  startNewDeck(): void {
    this.isCreatingNewDeck = true;
    this.newDeckName = '';
    this.newDeckDescription = '';
  }

  createNewDeck(): void {
    if (!this.newDeckName.trim()) return;
    this.currentDeck = newEditingDeck();
    this.currentDeck.name = this.newDeckName.trim();
    this.currentDeck.description = this.newDeckDescription;
    this.isCreatingNewDeck = false;
  }

  cancelNewDeck(): void {
    this.isCreatingNewDeck = false;
  }

  editDeck(deck: Deck): void {
    this.currentDeck = toEditingDeck(deck, this.allCards, this.basicEnergies);
  }

  cancelEdit(): void {
    if (confirm('編集内容を破棄しますか？')) {
      this.currentDeck = null;
    }
  }

  // ==================== デッキ操作 ====================

  addCard(card: PokemonCard): void {
    if (!this.currentDeck) return;
    const ok = this.deckBuilderService.addCard(this.currentDeck, card);
    if (!ok) {
      const total = this.deckBuilderService.getTotalCount(this.currentDeck);
      if (total >= DECK_CONSTRAINTS.TOTAL_CARDS) {
        alert(`デッキは${DECK_CONSTRAINTS.TOTAL_CARDS}枚までです`);
      } else {
        alert(`このカードは${DECK_CONSTRAINTS.MAX_SAME_CARD}枚までです`);
      }
    }
  }

  removeCard(cardId: number): void {
    if (!this.currentDeck) return;
    this.deckBuilderService.removeCard(this.currentDeck, cardId);
  }

  // ==================== 保存・削除 ====================

  saveDeck(): void {
    if (!this.currentDeck) return;
    const trimmedName = this.currentDeck.name.trim();
    if (!trimmedName) {
      alert('デッキ名を入力してください');
      return;
    }
    this.currentDeck.name = trimmedName;
    this.isSaving = true;
    const req = toSaveRequest(this.currentDeck);

    const obs =
      this.currentDeck.id != null
        ? this.deckService.updateDeck(this.currentDeck.id, req)
        : this.deckService.createDeck(req);

    obs.subscribe({
      next: () => {
        this.isSaving = false;
        this.currentDeck = null;
        this.loadDecks();
      },
      error: (err) => {
        this.isSaving = false;
        const detail = err.error?.detail;
        if (Array.isArray(detail?.errors)) {
          alert(`保存に失敗しました:\n${detail.errors.join('\n')}`);
        } else {
          alert('保存に失敗しました');
        }
      },
    });
  }

  deleteDeck(id: number): void {
    if (!confirm('このデッキを削除しますか？')) return;
    this.deckService.deleteDeck(id).subscribe({
      next: () => {
        this.loadDecks();
      },
      error: () => {
        alert('削除に失敗しました');
      },
    });
  }

  // ==================== テンプレート用ヘルパー ====================

  get filteredCards(): PokemonCard[] {
    let cards = this.allCards;
    if (this.filterType !== 'ALL') {
      cards = cards.filter(
        (c) => getCardFilterCategory(c.evolution_stage, c.card_type) === this.filterType,
      );
    }
    if (this.searchQuery.trim()) {
      const q = this.searchQuery.toLowerCase();
      cards = cards.filter((c) => c.name.toLowerCase().includes(q));
    }
    return cards;
  }

  /** 現在のデッキの合計枚数 */
  getTotalCount(): number {
    if (!this.currentDeck) return 0;
    return this.deckBuilderService.getTotalCount(this.currentDeck);
  }

  /** デッキ内の特定カードの枚数 */
  getCardCount(cardId: number): number {
    if (!this.currentDeck) return 0;
    return this.deckBuilderService.getCardCount(this.currentDeck, cardId);
  }

  /** 現在のデッキのバリデーション */
  get validation() {
    if (!this.currentDeck) return { valid: false, errors: [], warnings: [] };
    return this.deckBuilderService.validate(this.currentDeck);
  }

  get canSaveDeck(): boolean {
    return this.validation.valid && !this.isSaving;
  }

  get validationMessages(): string[] {
    return [...this.validation.errors, ...this.validation.warnings];
  }

  /** デッキカード一覧（表示用・枚数順） */
  get currentDeckEntries(): { card: PokemonCard; count: number }[] {
    if (!this.currentDeck) return [];
    const entries: { card: PokemonCard; count: number }[] = [];
    this.currentDeck.cardCounts.forEach((count, cardId) => {
      const card = this.currentDeck!.cardMap.get(cardId);
      if (card) entries.push({ card, count });
    });
    return entries.sort((a, b) => {
      const catOrder = { POKEMON: 0, TRAINER: 1, ENERGY: 2, OTHER: 3 };
      const oa = catOrder[getCardFilterCategory(a.card.evolution_stage, a.card.card_type)];
      const ob = catOrder[getCardFilterCategory(b.card.evolution_stage, b.card.card_type)];
      return oa - ob || a.card.name.localeCompare(b.card.name, 'ja');
    });
  }

  /** savedDecks用カウント */
  getDeckCounts(deck: Deck) {
    const energyTotal = Object.values(deck.energies ?? {}).reduce((s, n) => s + n, 0);
    const counts = this.deckBuilderService.getCategoryCounts(deck.cards ?? []);
    return { ...counts, energy: energyTotal };
  }

  getCategoryLabel(stage: string | null, cardType?: string | null): string {
    return getCardCategoryLabel(stage, cardType);
  }

  getTypeColor(type: string | null): string {
    return getTypeColor(type);
  }

  /** テンプレートで使用する基本エネルギー判定 */
  isBasicEnergy(card: PokemonCard): boolean {
    return isBasicEnergy(card);
  }
}
