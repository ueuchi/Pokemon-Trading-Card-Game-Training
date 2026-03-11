import { Component, OnInit, Output, EventEmitter, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { CardService } from '../../game/services/card.service';
import { PokemonCard, getTypeColor, getCardCategoryLabel } from '../../models/card.model';

const CARD_TYPES = [
  '草',
  '炎',
  '水',
  '雷',
  '超',
  '闘',
  '悪',
  '鋼',
  'ドラゴン',
  'フェアリー',
  '無色',
];

@Component({
  selector: 'card-list',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './card-list.component.html',
  styleUrl: './card-list.component.scss',
})
export class CardListComponent implements OnInit {
  @Output() cardSelected = new EventEmitter<PokemonCard>();

  cards: PokemonCard[] = [];
  filteredCards: PokemonCard[] = [];
  isLoading = false;
  errorMessage = '';

  searchName = '';
  filterType = '';

  readonly cardTypes = CARD_TYPES;

  constructor(
    private cardService: CardService,
    private cdr: ChangeDetectorRef,
  ) {}

  ngOnInit(): void {
    this.loadCards();
  }

  loadCards(): void {
    this.isLoading = true;
    this.errorMessage = '';
    this.cardService.getCards().subscribe({
      next: (cards) => {
        this.cards = cards;
        this.applyFilter();
        this.isLoading = false;
        this.cdr.detectChanges();
      },
      error: () => {
        this.errorMessage =
          'カードの取得に失敗しました。バックエンドが起動しているか確認してください。';
        this.isLoading = false;
        this.cdr.detectChanges();
      },
    });
  }

  applyFilter(): void {
    let result = [...this.cards];
    if (this.searchName.trim()) {
      const q = this.searchName.trim().toLowerCase();
      result = result.filter((c) => c.name.toLowerCase().includes(q));
    }
    if (this.filterType) {
      result = result.filter((c) => c.type === this.filterType);
    }
    this.filteredCards = result;
  }

  clearFilters(): void {
    this.searchName = '';
    this.filterType = '';
    this.applyFilter();
  }

  selectCard(card: PokemonCard): void {
    this.cardSelected.emit(card);
  }

  getTypeColor(type: string | null): string {
    return getTypeColor(type);
  }

  getCategoryLabel(card: PokemonCard): string {
    return getCardCategoryLabel(card.evolution_stage, card.card_type);
  }

  /** 表示用タイプ文字列を返す（エネルギーカードは energy_type を使用）*/
  getDisplayType(card: PokemonCard): string | null {
    if (card.card_type === 'energy') return card.energy_type ?? null;
    return card.type;
  }

  getAttackNames(card: PokemonCard): string {
    if (!card.attacks.length) return '—';
    return card.attacks.map((a) => a.name).join(' / ');
  }
}
