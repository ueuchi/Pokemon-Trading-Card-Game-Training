import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { PokemonCard } from '../../models/card.model';

const API_BASE = 'http://localhost:8000/api';

@Injectable({ providedIn: 'root' })
export class CardService {
  constructor(private http: HttpClient) {}

  /** 全カード一覧を取得 */
  getCards(): Observable<PokemonCard[]> {
    return this.http.get<PokemonCard[]>(`${API_BASE}/cards`);
  }

  /** IDでカードを取得 */
  getCardById(id: number): Observable<PokemonCard> {
    return this.http.get<PokemonCard>(`${API_BASE}/cards/${id}`);
  }
}
