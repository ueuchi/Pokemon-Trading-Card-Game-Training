import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { PokemonCard } from '../../models/card.model';
import { environment } from '../../../environments/environment';

@Injectable({
  providedIn: 'root',
})
export class CardService {
  private http = inject(HttpClient);
  // APIのベースURL（環境設定から取得）
  // private apiUrl = 'http://localhost:8000/api/cards';
  private apiUrl = environment.apiUrl;

  /**
   * カード一覧を取得
   */
  getCards(): Observable<PokemonCard[]> {
    return this.http.get<PokemonCard[]>(this.apiUrl);
  }

  /**
   * カード詳細を取得
   * @param id カードID
   */
  getCardById(id: number): Observable<PokemonCard> {
    return this.http.get<PokemonCard>(`${this.apiUrl}/${id}`);
  }

  /**
   * タイプでカードを検索
   * @param type カードタイプ
   */
  getCardsByType(type: string): Observable<PokemonCard[]> {
    return this.http.get<PokemonCard[]>(`${this.apiUrl}/type/${type}`);
  }

  /**
   * 名前でカードを検索
   * @param name カード名（部分一致）
   */
  searchCardsByName(name: string): Observable<PokemonCard[]> {
    return this.http.get<PokemonCard[]>(`${this.apiUrl}/search`, {
      params: { name },
    });
  }
}
