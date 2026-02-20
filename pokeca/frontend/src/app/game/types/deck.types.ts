/**
 * デッキ関連の型定義
 * backend/api/deck.py のレスポンスと整合性を取る
 */
import { PokemonCard } from '../../models/card.model';

/** デッキ内のカードエントリ（APIレスポンス用） */
export interface DeckCardEntry {
  card_id: number;
  count: number;
  name: string;
  hp: number | null;
  type: string | null;
  evolution_stage: string | null;
  image_url: string | null;
}

/** デッキ（APIレスポンス用） */
export interface Deck {
  id: number;
  name: string;
  description: string;
  energies: Record<string, number>;  // {"草": 10, "炎": 6}
  created_at: string;
  total_count: number;
  cards: DeckCardEntry[];
}

/** デッキ作成リクエスト */
export interface DeckCreateRequest {
  name: string;
  description?: string;
  cards: { card_id: number; count: number }[];
  energies: Record<string, number>;
}

/** デッキ更新リクエスト */
export interface DeckUpdateRequest {
  name?: string;
  description?: string;
  cards?: { card_id: number; count: number }[];
  energies?: Record<string, number>;
}

/** UI上で編集中のデッキ状態 */
export interface EditingDeck {
  id: number | null;
  name: string;
  description: string;
  /** card_id → count（通常カード用。id が負数の場合は基本エネルギー） */
  cardCounts: Map<number, number>;
  /** card_id → PokemonCard（表示用） */
  cardMap: Map<number, PokemonCard>;
}

/** デッキ制約 */
export const DECK_CONSTRAINTS = {
  TOTAL_CARDS: 60,
  MAX_SAME_CARD: 4,
} as const;

/** 基本エネルギーかどうかを判定（id が負数 = フロントエンドの固定データ） */
export function isBasicEnergy(card: PokemonCard): boolean {
  return card.evolution_stage === 'エネルギー';
}

/** evolution_stage からフィルター用カテゴリを返す */
export function getCardFilterCategory(
  stage: string | null
): 'POKEMON' | 'TRAINER' | 'ENERGY' | 'OTHER' {
  if (!stage) return 'OTHER';
  if (['たね', '1 進化', '2 進化'].includes(stage)) return 'POKEMON';
  if (['サポート', 'グッズ', 'スタジアム'].includes(stage)) return 'TRAINER';
  if (stage === 'エネルギー') return 'ENERGY';
  return 'OTHER';
}

/** EditingDeck の合計枚数を返す */
export function getTotalCount(deck: EditingDeck): number {
  let total = 0;
  deck.cardCounts.forEach((count) => { total += count; });
  return total;
}

/**
 * EditingDeck をAPIリクエスト形式に変換。
 * id が負数（基本エネルギー）は energies に集約し、通常カードは cards に含める。
 */
export function toSaveRequest(deck: EditingDeck): DeckCreateRequest {
  const cards: { card_id: number; count: number }[] = [];
  const energies: Record<string, number> = {};

  deck.cardCounts.forEach((count, card_id) => {
    if (count <= 0) return;
    const card = deck.cardMap.get(card_id);
    if (isBasicEnergy(card!)) {
      // 基本エネルギー → energies に集約
      if (card!.type) energies[card!.type] = count;
    } else {
      cards.push({ card_id, count });
    }
  });

  return { name: deck.name, description: deck.description, cards, energies };
}

/** Deck（APIレスポンス）から EditingDeck を生成 */
export function toEditingDeck(
  deck: Deck,
  allCards: PokemonCard[],
  basicEnergies: PokemonCard[]
): EditingDeck {
  const apiCardMap = new Map<number, PokemonCard>();
  allCards.forEach((c) => apiCardMap.set(c.id, c));

  const energyByType = new Map<string, PokemonCard>();
  basicEnergies.forEach((e) => { if (e.type) energyByType.set(e.type, e); });

  const cardCounts = new Map<number, number>();
  const cardMap = new Map<number, PokemonCard>();

  // 通常カード
  deck.cards.forEach((entry) => {
    const card = apiCardMap.get(entry.card_id);
    if (card) {
      cardCounts.set(entry.card_id, entry.count);
      cardMap.set(entry.card_id, card);
    }
  });

  // 基本エネルギー（energiesフィールドから復元）
  Object.entries(deck.energies).forEach(([type, count]) => {
    const energy = energyByType.get(type);
    if (energy && count > 0) {
      cardCounts.set(energy.id, count);
      cardMap.set(energy.id, energy);
    }
  });

  return { id: deck.id, name: deck.name, description: deck.description, cardCounts, cardMap };
}

/** 空の新規デッキを生成 */
export function newEditingDeck(): EditingDeck {
  return {
    id: null,
    name: '',
    description: '',
    cardCounts: new Map(),
    cardMap: new Map(),
  };
}
