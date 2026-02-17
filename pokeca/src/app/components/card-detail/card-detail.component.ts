import { Component, Input, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';
import { PokemonCard, TYPE_COLORS, TYPE_ICONS } from '../../models/card.model';

@Component({
  selector: 'card-detail',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './card-detail.component.html',
  styleUrl: './card-detail.component.scss'
})
export class CardDetailComponent {
  @Input() card: PokemonCard | null = null;
  @Output() close = new EventEmitter<void>();
  
  /**
   * タイプの色を取得
   */
  getTypeColor(type: string): string {
    return TYPE_COLORS[type] || 'var(--color_grey)';
  }
  
  /**
   * タイプのアイコンを取得
   */
  getTypeIcon(type: string): string {
    return TYPE_ICONS[type] || '⭐';
  }
  
  /**
   * 閉じるボタンのクリック処理
   */
  onClose(): void {
    this.close.emit();
  }
  
  /**
   * 背景クリックで閉じる
   */
  onBackdropClick(event: MouseEvent): void {
    if ((event.target as HTMLElement).classList.contains('modal-backdrop')) {
      this.onClose();
    }
  }
}
