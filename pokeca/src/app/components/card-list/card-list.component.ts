import { Component, OnInit, Output, EventEmitter, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { PokemonCard } from '../../models/card.model';
import { CardService } from '../../game/services/card.service';

@Component({
  selector: 'card-list',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './card-list.component.html',
  styleUrl: './card-list.component.scss',
})
export class CardListComponent implements OnInit {
  cards: PokemonCard[] = [];
  loading = true;

  @Output() cardSelected = new EventEmitter<PokemonCard>();

  constructor(
    private cardService: CardService,
    private cdr: ChangeDetectorRef,
  ) {}

  ngOnInit(): void {
    this.loadCards();
  }

  /**
   * カード一覧を読み込む
   */
  loadCards(): void {
    this.loading = true;
    this.cardService.getCards().subscribe({
      next: (cards) => {
        this.cards = cards;
        this.loading = false;
        this.cdr.detectChanges();
      },
      error: (error) => {
        console.error('カードの読み込みに失敗しました:', error);
        this.loading = false;
      },
    });
  }

  /**
   * カードがクリックされた時の処理
   */
  onCardClick(card: PokemonCard): void {
    this.cardSelected.emit(card);
  }
}
