// カードデータの型定義

/**
 * ワザに必要なエネルギー情報
 */
export interface Attack {
  name: string;
  energy: string[];
  energy_count: number;
  damage: number;
  description: string;
}

/**
 * 弱点情報
 */
export interface Weakness {
  type: string;
  value: string;
}

/**
 * 抵抗力情報
 */
export interface Resistance {
  type: string;
  value: string;
}

/**
 * ポケモンカード情報
 */
export interface PokemonCard {
  name: string;
  image_url: string;
  list_index: number;
  hp: number;
  type: string;
  evolution_stage: string;
  attacks: Attack[];
  weakness: Weakness | null;
  resistance: Resistance | null;
  retreat_cost: number;
}

/**
 * タイプごとの色定義
 */
export const TYPE_COLORS: { [key: string]: string } = {
  '草': 'var(--color_grass)',
  '炎': 'var(--color_fire)',
  '水': 'var(--color_water)',
  '雷': 'var(--color_electric)',
  '超': 'var(--color_super)',
  '闘': 'var(--color_fight)',
  '悪': 'var(--color_dark)',
  '鋼': 'var(--color_grey)',
  'ドラゴン': 'var(--color_orange)',
  'フェアリー': 'var(--color_pink)',
  '無色': 'var(--color_grey)',
};

/**
 * タイプごとの絵文字定義
 */
export const TYPE_ICONS: { [key: string]: string } = {
  '草': '🌿',
  '炎': '🔥',
  '水': '💧',
  '雷': '⚡',
  '超': '🔮',
  '闘': '👊',
  '悪': '🌙',
  '鋼': '⚙️',
  'ドラゴン': '🐉',
  'フェアリー': '✨',
  '無色': '⭐',
};
