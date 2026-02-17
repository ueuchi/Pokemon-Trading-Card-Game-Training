/**
 * ゲーム初期化のためのファクトリー関数
 * 
 * GameStateを作成するためのヘルパー関数群
 */

import {
  GameState,
  Player,
  Card,
  GameConfig,
  GamePhase,
  GameStatus,
  FieldPokemon,
  PokemonCard
} from '../types/game-state.types';

/**
 * 配列をシャッフルする（Fisher-Yates）
 */
function shuffleArray<T>(array: T[]): T[] {
  const shuffled = [...array];
  for (let i = shuffled.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
  }
  return shuffled;
}

/**
 * プレイヤーの初期状態を作成
 */
function createInitialPlayer(
  id: 'PLAYER' | 'CPU',
  deck: Card[],
  handSize: number,
  prizeCount: number
): Player {
  // デッキをシャッフル
  const shuffledDeck = shuffleArray(deck);
  
  // 初期手札を引く
  const hand = shuffledDeck.slice(0, handSize);
  
  // サイドを取る
  const prizes = shuffledDeck.slice(handSize, handSize + prizeCount);
  
  // 残りが山札
  const remainingDeck = shuffledDeck.slice(handSize + prizeCount);

  return {
    id,
    deck: remainingDeck,
    hand,
    activePokemon: null,  // セットアップフェーズで設定
    bench: [],
    prizes,
    discardPile: []
  };
}

/**
 * ゲームの初期状態を作成
 * 
 * @param config ゲーム設定
 * @returns 初期化されたGameState
 */
export function createInitialGameState(config: GameConfig): GameState {
  const playerState = createInitialPlayer(
    'PLAYER',
    config.playerDeck,
    config.handSize,
    config.prizeCount
  );

  const cpuState = createInitialPlayer(
    'CPU',
    config.cpuDeck,
    config.handSize,
    config.prizeCount
  );

  return {
    players: {
      PLAYER: playerState,
      CPU: cpuState
    },
    currentTurn: 'PLAYER',  // プレイヤーが先攻
    turnCount: 1,
    phase: 'SETUP',
    gameStatus: 'NOT_STARTED',
    winner: null
  };
}

/**
 * FieldPokemonを作成
 * ポケモンカードから場のポケモンを生成
 */
export function createFieldPokemon(card: PokemonCard): FieldPokemon {
  return {
    card,
    currentHp: card.hp,
    attachedEnergy: [],
    damageCounters: 0
  };
}

/**
 * ゲーム開始処理
 * セットアップフェーズを完了し、最初のターンを開始
 * 
 * 簡略版：
 * - 手札に最初のポケモンカードがあればアクティブに出す
 * - なければマリガン（今回は省略、必ずポケモンがある前提）
 */
export function startGame(state: GameState): GameState {
  // プレイヤーとCPUの最初のポケモンを自動で出す
  const newState = { ...state };
  
  // プレイヤーの最初のポケモンを探す
  const playerPokemon = newState.players.PLAYER.hand.find(
    card => card.type === 'POKEMON'
  ) as PokemonCard | undefined;

  // CPUの最初のポケモンを探す
  const cpuPokemon = newState.players.CPU.hand.find(
    card => card.type === 'POKEMON'
  ) as PokemonCard | undefined;

  if (playerPokemon) {
    // 手札から削除
    newState.players.PLAYER.hand = newState.players.PLAYER.hand.filter(
      card => card.id !== playerPokemon.id
    );
    // アクティブに配置
    newState.players.PLAYER.activePokemon = createFieldPokemon(playerPokemon);
  }

  if (cpuPokemon) {
    // 手札から削除
    newState.players.CPU.hand = newState.players.CPU.hand.filter(
      card => card.id !== cpuPokemon.id
    );
    // アクティブに配置
    newState.players.CPU.activePokemon = createFieldPokemon(cpuPokemon);
  }

  // ゲームを開始状態に
  newState.gameStatus = 'IN_PROGRESS';
  newState.phase = 'DRAW';  // 最初のドローフェーズへ

  return newState;
}

/**
 * デバッグ用：GameStateを文字列で出力
 */
export function debugGameState(state: GameState): string {
  const lines: string[] = [];
  
  lines.push(`=== ターン ${state.turnCount} (${state.currentTurn}) ===`);
  lines.push(`フェーズ: ${state.phase}`);
  lines.push(`ステータス: ${state.gameStatus}`);
  
  // プレイヤー情報
  lines.push('\n[PLAYER]');
  lines.push(`  山札: ${state.players.PLAYER.deck.length}枚`);
  lines.push(`  手札: ${state.players.PLAYER.hand.length}枚`);
  lines.push(`  サイド: ${state.players.PLAYER.prizes.length}枚`);
  if (state.players.PLAYER.activePokemon) {
    const p = state.players.PLAYER.activePokemon;
    lines.push(`  アクティブ: ${p.card.name} (HP: ${p.currentHp}/${p.card.hp})`);
    lines.push(`  付いているエネルギー: ${p.attachedEnergy.length}枚`);
  } else {
    lines.push(`  アクティブ: なし`);
  }
  
  // CPU情報
  lines.push('\n[CPU]');
  lines.push(`  山札: ${state.players.CPU.deck.length}枚`);
  lines.push(`  手札: ${state.players.CPU.hand.length}枚`);
  lines.push(`  サイド: ${state.players.CPU.prizes.length}枚`);
  if (state.players.CPU.activePokemon) {
    const p = state.players.CPU.activePokemon;
    lines.push(`  アクティブ: ${p.card.name} (HP: ${p.currentHp}/${p.card.hp})`);
    lines.push(`  付いているエネルギー: ${p.attachedEnergy.length}枚`);
  } else {
    lines.push(`  アクティブ: なし`);
  }
  
  return lines.join('\n');
}
