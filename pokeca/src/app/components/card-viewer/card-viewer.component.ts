import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { CardListComponent } from '../card-list/card-list.component';
import { CardDetailComponent } from '../card-detail/card-detail.component';
import { PokemonCard } from '../../models/card.model';

@Component({
  selector: 'card-viewer',
  standalone: true,
  imports: [CommonModule, CardListComponent, CardDetailComponent],
  templateUrl: './card-viewer.component.html',
  styleUrl: './card-viewer.component.scss'
})
export class CardViewerComponent {
  selectedCard: PokemonCard | null = null;
  
  /**
   * カードが選択された時の処理
   */
  onCardSelected(card: PokemonCard): void {
    this.selectedCard = card;
  }
  
  /**
   * 詳細表示を閉じる
   */
  onCloseDetail(): void {
    this.selectedCard = null;
  }
}
