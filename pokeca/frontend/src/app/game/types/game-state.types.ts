/**
 * ゲーム全体の状態を表す型定義
 * 
 * 設計方針：
 * - 純粋なデータ構造（関数を持たない）
 * - Immutableを前提とする（状態更新は新しいオブジェクトを作る）
 * - すべての情報を含む（これだけでゲームを再現できる）
 */

/**
 * カードの種類
 */
export type CardType = 'POKEMON' | 'ENERGY' | 'TRAINER';

/**
 * エネルギーの色
 */
export type EnergyType = 'FIRE' | 'WATER' | 'GRASS' | 'ELECTRIC' | 'COLORLESS';

/**
 * カードの基本構造
 * すべてのカードが持つ共通プロパティ
 */
export interface BaseCard {
  id: string;           // カードのユニークID（例: "pikachu-001"）
  name: string;         // カード名
  type: CardType;       // カードの種類
}

/**
 * ポケモンカード
 * 場に出して戦うカード
 */
export interface PokemonCard extends BaseCard {
  type: 'POKEMON';
  hp: number;                    // 最大HP
  energyType: EnergyType;        // ポケモンのタイプ
  attacks: Attack[];             // 使えるワザ（最大2個程度）
  retreatCost: number;           // 逃げるコスト（簡略化のため数値のみ）
}

/**
 * ワザの定義
 * ポケモンが使える攻撃
 */
export interface Attack {
  name: string;                  // ワザの名前
  energyCost: EnergyCost[];      // 必要なエネルギー
  effects: Effect[];             // ワザの効果（再利用可能な部品）
}

/**
 * エネルギーコスト
 */
export interface EnergyCost {
  type: EnergyType;
  amount: number;
}

/**
 * エネルギーカード
 * ポケモンに付けて、ワザを使えるようにする
 */
export interface EnergyCard extends BaseCard {
  type: 'ENERGY';
  energyType: EnergyType;
}

/**
 * トレーナーカード（将来拡張用、今回は使わない）
 */
export interface TrainerCard extends BaseCard {
  type: 'TRAINER';
  effects: Effect[];
}

/**
 * すべてのカード型の統合型
 */
export type Card = PokemonCard | EnergyCard | TrainerCard;

/**
 * Effect（効果）システム
 * 
 * 設計思想：
 * - カードの効果は「再利用可能な部品」の組み合わせ
 * - 自由入力を禁止し、定義済みの効果タイプのみ使用
 * - 数値や条件は選択式
 */
export type EffectType = 
  | 'DAMAGE'              // ダメージを与える
  | 'HEAL'                // HPを回復
  | 'DRAW'                // カードを引く
  | 'ENERGY_ATTACH'       // エネルギーを付ける
  | 'CONDITIONAL';        // 条件付き効果

/**
 * ダメージ効果
 */
export interface DamageEffect {
  type: 'DAMAGE';
  amount: number;         // ダメージ量
  target: 'ACTIVE';       // 対象（今回は相手のアクティブのみ）
}

/**
 * 回復効果
 */
export interface HealEffect {
  type: 'HEAL';
  amount: number;
  target: 'SELF';         // 自分自身
}

/**
 * カードを引く効果
 */
export interface DrawEffect {
  type: 'DRAW';
  amount: number;         // 引く枚数
}

/**
 * 条件付き効果（例：コイン投げで成功したら追加ダメージ）
 */
export interface ConditionalEffect {
  type: 'CONDITIONAL';
  condition: 'COIN_FLIP';           // 今回はコイン投げのみ
  successEffects: Effect[];         // 成功時の効果
  failEffects?: Effect[];           // 失敗時の効果（オプション）
}

/**
 * すべての効果型の統合型
 */
export type Effect = DamageEffect | HealEffect | DrawEffect | ConditionalEffect;

/**
 * 場のポケモン（実際にバトルしているポケモン）
 * カード＋現在の状態を持つ
 */
export interface FieldPokemon {
  card: PokemonCard;
  currentHp: number;                // 現在のHP
  attachedEnergy: EnergyCard[];     // 付いているエネルギー
  damageCounters: number;           // ダメージカウンター（currentHpから計算可能だが明示）
}

/**
 * プレイヤーの状態
 */
export interface Player {
  id: 'PLAYER' | 'CPU';             // プレイヤーID
  deck: Card[];                      // 山札
  hand: Card[];                      // 手札
  activePokemon: FieldPokemon | null; // アクティブポケモン（1体のみ）
  bench: FieldPokemon[];             // ベンチ（簡略版では使わないかも）
  prizes: Card[];                    // サイドカード（簡略版では数だけでもOK）
  discardPile: Card[];               // トラッシュ
}

/**
 * ゲーム全体の状態
 * これがゲームのすべての情報を保持する
 */
export interface GameState {
  players: {
    PLAYER: Player;
    CPU: Player;
  };
  currentTurn: 'PLAYER' | 'CPU';    // 現在のターン
  turnCount: number;                 // ターン数
  phase: GamePhase;                  // 現在のフェーズ
  gameStatus: GameStatus;            // ゲームの状態
  winner: 'PLAYER' | 'CPU' | null;   // 勝者（ゲーム終了時）
}

/**
 * ゲームフェーズ
 * ターン内でどの段階にいるか
 */
export type GamePhase = 
  | 'SETUP'           // セットアップ（最初の手札配布など）
  | 'DRAW'            // ドローフェーズ
  | 'MAIN'            // メインフェーズ（行動可能）
  | 'END';            // ターン終了

/**
 * ゲームの状態
 */
export type GameStatus = 
  | 'NOT_STARTED'     // 未開始
  | 'IN_PROGRESS'     // 進行中
  | 'FINISHED';       // 終了

/**
 * ゲーム初期化時の設定
 */
export interface GameConfig {
  playerDeck: Card[];
  cpuDeck: Card[];
  prizeCount: number;    // サイドの枚数（通常6枚、簡略版では3枚など）
  handSize: number;      // 初期手札枚数（通常7枚）
}
