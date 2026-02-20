import { Component, Input, Output, EventEmitter, OnChanges } from '@angular/core';
import { CommonModule } from '@angular/common';
import { PokemonCard, getTypeColor, getCardCategoryLabel } from '../../models/card.model';

@Component({
  selector: 'card-detail',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './card-detail.component.html',
  styleUrl: './card-detail.component.scss',
})
export class CardDetailComponent implements OnChanges {
  @Input() card: PokemonCard | null = null;
  @Output() close = new EventEmitter<void>();

  isVisible = false;

  ngOnChanges(): void {
    this.isVisible = !!this.card;
  }

  onClose(): void {
    this.close.emit();
  }

  /** オーバーレイクリックで閉じる */
  onOverlayClick(event: MouseEvent): void {
    if ((event.target as HTMLElement).classList.contains('modal-overlay')) {
      this.onClose();
    }
  }

  getTypeColor(type: string | null): string {
    return getTypeColor(type);
  }

  getCategoryLabel(stage: string | null): string {
    return getCardCategoryLabel(stage);
  }

  /** エネルギーコスト表示用（例: ["炎","炎","無色"] → "炎×2 無色×1"）*/
  formatEnergyCost(energy: string[]): string {
    if (!energy.length) return '0';
    const counts: Record<string, number> = {};
    energy.forEach((e) => { counts[e] = (counts[e] ?? 0) + 1; });
    return Object.entries(counts)
      .map(([type, count]) => (count > 1 ? `${type}×${count}` : type))
      .join(' ');
  }
}
