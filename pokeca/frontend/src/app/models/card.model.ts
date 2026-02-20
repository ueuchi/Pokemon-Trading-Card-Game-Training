/**
 * カードモデル型定義
 * backend/models/card.py の PokemonCard と整合性を取る
 *
 * NOTE: game-board が使う既存の型（FieldPokemon等）とは別ファイル。
 * カード管理UI（card-viewer / card-list / card-detail）専用の型定義。
 */

/** ワザ情報 */
export interface Attack {
  name: string;
  energy: string[];        // タイプ文字列の配列（例: ["炎", "無色"]）
  energy_count: number;
  damage: number;
  description: string;
}

/** 弱点情報 */
export interface Weakness {
  type: string;   // 例: "水"
  value: string;  // 例: "×2"
}

/** 抵抗力情報 */
export interface Resistance {
  type: string;   // 例: "炎"
  value: string;  // 例: "-30"
}

/** APIから返ってくるポケモンカードの完全な型 */
export interface PokemonCard {
  id: number;
  name: string;
  image_url: string | null;
  list_index: number | null;
  hp: number | null;
  type: string | null;
  evolution_stage: string | null;
  attacks: Attack[];
  weakness: Weakness | null;
  resistance: Resistance | null;
  retreat_cost: number | null;
  created_at: string | null;
}

/** タイプ文字列からCSSカラーを返す */
export const TYPE_COLOR_MAP: Record<string, string> = {
  '草':       '#5db85d',
  '炎':       '#e8652a',
  '水':       '#4a90d9',
  '雷':       '#d4b800',
  '超':       '#9b59b6',
  '闘':       '#c0392b',
  '悪':       '#5d4e37',
  '鋼':       '#7f8c8d',
  'ドラゴン': '#6c3483',
  'フェアリー':'#e91e8c',
  '無色':     '#888888',
};

export function getTypeColor(type: string | null): string {
  if (!type) return '#aaaaaa';
  return TYPE_COLOR_MAP[type] ?? '#aaaaaa';
}

/** evolution_stage からカード種別ラベルを返す */
export function getCardCategoryLabel(stage: string | null): string {
  if (!stage) return '不明';
  if (['たね', '1 進化', '2 進化'].includes(stage)) return 'ポケモン';
  if (['サポート', 'グッズ', 'スタジアム'].includes(stage)) return 'トレーナー';
  if (stage === 'エネルギー') return 'エネルギー';
  return stage;
}
