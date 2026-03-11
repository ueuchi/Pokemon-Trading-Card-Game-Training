import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap } from 'rxjs';
import { Deck, DeckCreateRequest, DeckUpdateRequest } from '../types/deck.types';

const API_BASE = 'http://localhost:8000/api';

@Injectable({ providedIn: 'root' })
export class DeckService {
  private http = inject(HttpClient);
  private baseUrl = `${API_BASE}/decks`;

  /** 全デッキ一覧を取得 */
  getDecks(): Observable<Deck[]> {
    return this.http.get<Deck[]>(this.baseUrl).pipe(
      tap((decks) => console.log('デッキ一覧取得成功:', decks?.length, '件')),
    );
  }

  /** デッキを新規作成 */
  createDeck(req: DeckCreateRequest): Observable<Deck> {
    return this.http.post<Deck>(this.baseUrl, req);
  }

  /** デッキを更新 */
  updateDeck(id: number, req: DeckUpdateRequest): Observable<Deck> {
    return this.http.put<Deck>(`${this.baseUrl}/${id}`, req);
  }

  /** デッキを削除 */
  deleteDeck(id: number): Observable<void> {
    return this.http.delete<void>(`${this.baseUrl}/${id}`);
  }
}
