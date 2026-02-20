/**
 * Actionシステムの型定義
 *
 * 設計思想：
 * - プレイヤーとCPUが同じActionインターフェースを使う
 * - すべての行動は「Action」として表現される
 * - Actionは「何をするか」だけを記述（実行ロジックは別）
 * - Immutableな設計（GameStateを変更せず、新しいStateを返す）
 */

import { Card, PokemonCard, EnergyCard } from './game-state.types';

/**
 * アクションの種類
 */
export type ActionType =
  | 'DRAW_CARD' // カードを引く
  | 'PLAY_POKEMON' // ポケモンを場に出す
  | 'ATTACH_ENERGY' // エネルギーを付ける
  | 'SWITCH_POKEMON' // ポケモンを入れ替える
  | 'ATTACK' // ワザを使う
  | 'END_TURN' // ターン終了
  | 'PASS'; // パス（何もしない）

/**
 * アクションの基本構造
 */
export interface BaseAction {
  type: ActionType;
  playerId: 'PLAYER' | 'CPU'; // 誰が実行するか
}

/**
 * カードを引くアクション
 */
export interface DrawCardAction extends BaseAction {
  type: 'DRAW_CARD';
  amount: number; // 引く枚数
}

/**
 * ポケモンを場に出すアクション
 */
export interface PlayPokemonAction extends BaseAction {
  type: 'PLAY_POKEMON';
  cardId: string; // 手札のどのカードを出すか
  position: 'ACTIVE' | 'BENCH'; // 出す場所
}

/**
 * エネルギーを付けるアクション
 */
export interface AttachEnergyAction extends BaseAction {
  type: 'ATTACH_ENERGY';
  energyCardId: string; // 付けるエネルギーカードのID
  targetPokemonId?: string; // どのポケモンに付けるか（アクティブのカードID）
  targetBenchIndex?: number; // ベンチの場合のインデックス
  targetPosition: 'ACTIVE' | 'BENCH'; // 付ける場所
}

/**
 * 攻撃アクション
 */
export interface AttackAction extends BaseAction {
  type: 'ATTACK';
  attackIndex: number; // 使うワザのインデックス（0 or 1）
}

/**
 * ターン終了アクション
 */
export interface EndTurnAction extends BaseAction {
  type: 'END_TURN';
}

/**
 * ポケモンを入れ替えるアクション
 */
export interface SwitchPokemonAction extends BaseAction {
  type: 'SWITCH_POKEMON';
  benchIndex: number; // ベンチのどのポケモンと入れ替えるか
}

/**
 * パスアクション（何もしない）
 */
export interface PassAction extends BaseAction {
  type: 'PASS';
}

/**
 * すべてのアクション型の統合型
 */
export type Action =
  | DrawCardAction
  | PlayPokemonAction
  | AttachEnergyAction
  | SwitchPokemonAction
  | AttackAction
  | EndTurnAction
  | PassAction;

/**
 * アクション実行結果
 *
 * アクションが実行可能かどうか、実行後の状態などを返す
 */
export interface ActionResult {
  success: boolean; // 成功したか
  newState?: GameState; // 新しいゲーム状態（成功時のみ）
  error?: string; // エラーメッセージ（失敗時）
  logs?: string[]; // ログメッセージ（何が起きたか）
}

/**
 * アクションのバリデーション結果
 * アクションが実行可能かどうかをチェック
 */
export interface ActionValidation {
  valid: boolean;
  reason?: string; // 無効な理由
}

/**
 * ターン内でできる行動の制限
 *
 * 例：
 * - エネルギーは1ターンに1枚まで
 * - 攻撃は1ターンに1回まで
 */
export interface TurnLimits {
  energyAttached: boolean; // このターンにエネルギーを付けたか
  hasAttacked: boolean; // このターンに攻撃したか
}

/**
 * import を追加（循環参照を避けるため、必要に応じて調整）
 */
import { GameState } from './game-state.types';
