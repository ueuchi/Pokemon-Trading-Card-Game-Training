/**
 * 基本エネルギーの定数データ
 *
 * 草・雷エネルギーはスクレイピングした画像を使用する。
 * その他はBulbagardenの画像を使用。
 * id は負数の固定値（DBのカードと衝突しないようにするため）。
 * evolution_stage = 'エネルギー' で基本エネルギーと判定される。
 */
import { PokemonCard } from '../../models/card.model';
import { environment } from '../../../environments/environment';

const API_HOST = environment.apiUrl.replace('/api/cards', '');

export const BASIC_ENERGIES: PokemonCard[] = [
  {
    id: -1,
    name: '草エネルギー',
    card_type: 'energy',
    type: '草',
    evolution_stage: 'エネルギー',
    hp: null,
    image_url:
      `${API_HOST}/static/scraped/processed/energy/0001_基本草エネルギー.jpg`,
    attacks: [],
    weakness: null,
    resistance: null,
    retreat_cost: null,
    list_index: null,
    created_at: null,
  },
  {
    id: -2,
    name: '炎エネルギー',
    card_type: 'energy',
    type: '炎',
    evolution_stage: 'エネルギー',
    hp: null,
    image_url:
      'https://archives.bulbagarden.net/media/upload/thumb/d/de/Fire-Energy.jpg/170px-Fire-Energy.jpg',
    attacks: [],
    weakness: null,
    resistance: null,
    retreat_cost: null,
    list_index: null,
    created_at: null,
  },
  {
    id: -3,
    name: '水エネルギー',
    card_type: 'energy',
    type: '水',
    evolution_stage: 'エネルギー',
    hp: null,
    image_url:
      'https://archives.bulbagarden.net/media/upload/thumb/a/a0/Water-Energy.jpg/170px-Water-Energy.jpg',
    attacks: [],
    weakness: null,
    resistance: null,
    retreat_cost: null,
    list_index: null,
    created_at: null,
  },
  {
    id: -4,
    name: '雷エネルギー',
    card_type: 'energy',
    type: '雷',
    evolution_stage: 'エネルギー',
    hp: null,
    image_url:
      `${API_HOST}/static/scraped/processed/energy/0004_基本雷エネルギー.jpg`,
    attacks: [],
    weakness: null,
    resistance: null,
    retreat_cost: null,
    list_index: null,
    created_at: null,
  },
  {
    id: -5,
    name: '超エネルギー',
    card_type: 'energy',
    type: '超',
    evolution_stage: 'エネルギー',
    hp: null,
    image_url:
      'https://archives.bulbagarden.net/media/upload/thumb/1/17/Psychic-Energy.jpg/170px-Psychic-Energy.jpg',
    attacks: [],
    weakness: null,
    resistance: null,
    retreat_cost: null,
    list_index: null,
    created_at: null,
  },
  {
    id: -6,
    name: '闘エネルギー',
    card_type: 'energy',
    type: '闘',
    evolution_stage: 'エネルギー',
    hp: null,
    image_url:
      'https://archives.bulbagarden.net/media/upload/thumb/7/7e/Fighting-Energy.jpg/170px-Fighting-Energy.jpg',
    attacks: [],
    weakness: null,
    resistance: null,
    retreat_cost: null,
    list_index: null,
    created_at: null,
  },
  {
    id: -7,
    name: '悪エネルギー',
    card_type: 'energy',
    type: '悪',
    evolution_stage: 'エネルギー',
    hp: null,
    image_url:
      'https://archives.bulbagarden.net/media/upload/thumb/0/0c/Darkness-Energy.jpg/170px-Darkness-Energy.jpg',
    attacks: [],
    weakness: null,
    resistance: null,
    retreat_cost: null,
    list_index: null,
    created_at: null,
  },
  {
    id: -8,
    name: '鋼エネルギー',
    card_type: 'energy',
    type: '鋼',
    evolution_stage: 'エネルギー',
    hp: null,
    image_url:
      'https://archives.bulbagarden.net/media/upload/thumb/0/09/Metal-Energy.jpg/170px-Metal-Energy.jpg',
    attacks: [],
    weakness: null,
    resistance: null,
    retreat_cost: null,
    list_index: null,
    created_at: null,
  },
  {
    id: -9,
    name: '無色エネルギー',
    card_type: 'energy',
    type: '無色',
    evolution_stage: 'エネルギー',
    hp: null,
    image_url:
      'https://archives.bulbagarden.net/media/upload/thumb/9/94/Colorless-Energy.jpg/170px-Colorless-Energy.jpg',
    attacks: [],
    weakness: null,
    resistance: null,
    retreat_cost: null,
    list_index: null,
    created_at: null,
  },
];
