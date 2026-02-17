/**
 * Card Creator Service
 *
 * 役割：
 * - カード作成フォームのデータをCardオブジェクトに変換
 * - 作成したカードを保存・管理
 * - カードのバリデーション
 */

import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable } from 'rxjs';
import {
  Card,
  PokemonCard,
  EnergyCard,
  Attack,
  Effect,
  DamageEffect,
  HealEffect,
  DrawEffect,
  ConditionalEffect,
} from '../types/game-state.types';
import {
  CardCreationForm,
  AttackCreationForm,
  EffectCreationForm,
  generateCardId,
} from '../types/card-creation.types';

@Injectable({
  providedIn: 'root',
})
export class CardCreatorService {
  // 作成されたカードのリスト
  private customCardsSubject = new BehaviorSubject<Card[]>([]);
  public customCards$: Observable<Card[]> = this.customCardsSubject.asObservable();

  pokemonNameList = [
    'ピカチュウ',
    'ヒトカゲ',
    'ゼニガメ',
    'フシギダネ',
    'イーブイ',
    'カビゴン',
    'ミュウツー',
    'ルカリオ',
    'ゲンガー',
    'リザードン',
  ];

  constructor() {
    // ローカルストレージから読み込み
    this.loadFromLocalStorage();
  }

  /**
   * ポケモン名リストを取得
   */
  getPokemonNameList(): string[] {
    return this.pokemonNameList;
  }

  /**
   * フォームデータからカードを作成
   */
  createCard(formData: CardCreationForm): Card | null {
    // バリデーション
    if (!this.validateForm(formData)) {
      return null;
    }

    if (formData.cardType === 'POKEMON') {
      return this.createPokemonCard(formData);
    } else if (formData.cardType === 'TRAINER') {
      return this.createEnergyCard(formData);
    } else if (formData.cardType === 'ENERGY') {
      return this.createEnergyCard(formData);
    }

    return null;
  }

  /**
   * ポケモンカードを作成
   */
  private createPokemonCard(formData: CardCreationForm): PokemonCard {
    const cardId = generateCardId(formData.name, 'POKEMON');

    // ワザを変換
    const attacks: Attack[] = (formData.attacks || []).map((attackForm) =>
      this.createAttack(attackForm),
    );

    const pokemonCard: PokemonCard = {
      id: cardId,
      name: formData.name,
      type: 'POKEMON',
      evolution: 'BASIC',
      hp: formData.hp || 50,
      energyType: formData.energyType || 'COLORLESS',
      retreatCost: formData.retreatCost || 1,
      attacks: attacks,
    };

    return pokemonCard;
  }

  /**
   * エネルギーカードを作成
   */
  private createEnergyCard(formData: CardCreationForm): EnergyCard {
    const cardId = generateCardId(formData.name, 'ENERGY');

    const energyCard: EnergyCard = {
      id: cardId,
      name: formData.name,
      type: 'ENERGY',
      energyType: formData.energyType || 'COLORLESS',
    };

    return energyCard;
  }

  /**
   * ワザを作成
   */
  private createAttack(attackForm: AttackCreationForm): Attack {
    return {
      name: attackForm.name,
      energyCost: attackForm.energyCosts.map((cost) => ({
        type: cost.type,
        amount: cost.amount,
      })),
      effects: attackForm.effects.map((effectForm) => this.createEffect(effectForm)),
    };
  }

  /**
   * 効果を作成
   */
  private createEffect(effectForm: EffectCreationForm): Effect {
    switch (effectForm.effectType) {
      case 'DAMAGE':
        return {
          type: 'DAMAGE',
          amount: effectForm.damageAmount || 10,
          target: 'ACTIVE',
        } as DamageEffect;

      case 'HEAL':
        return {
          type: 'HEAL',
          amount: effectForm.healAmount || 10,
          target: 'SELF',
        } as HealEffect;

      case 'DRAW':
        return {
          type: 'DRAW',
          amount: effectForm.drawAmount || 1,
        } as DrawEffect;

      case 'CONDITIONAL':
        const successEffects = (effectForm.successEffects || []).map((e) => this.createEffect(e));

        return {
          type: 'CONDITIONAL',
          condition: 'COIN_FLIP',
          successEffects: successEffects,
        } as ConditionalEffect;

      default:
        // デフォルトは10ダメージ
        return {
          type: 'DAMAGE',
          amount: 10,
          target: 'ACTIVE',
        } as DamageEffect;
    }
  }

  /**
   * フォームのバリデーション
   */
  private validateForm(formData: CardCreationForm): boolean {
    // 名前は必須
    if (!formData.name || formData.name.trim().length === 0) {
      console.error('カード名は必須です');
      return false;
    }

    // ポケモンカードの場合
    if (formData.cardType === 'POKEMON') {
      if (!formData.hp || formData.hp <= 0) {
        console.error('HPは1以上である必要があります');
        return false;
      }

      if (!formData.attacks || formData.attacks.length === 0) {
        console.error('ポケモンカードには最低1つのワザが必要です');
        return false;
      }
    }

    return true;
  }

  /**
   * カードを保存
   */
  saveCard(card: Card): void {
    const currentCards = this.customCardsSubject.value;
    const updatedCards = [...currentCards, card];

    this.customCardsSubject.next(updatedCards);
    this.saveToLocalStorage(updatedCards);
  }

  /**
   * カードを削除
   */
  deleteCard(cardId: string): void {
    const currentCards = this.customCardsSubject.value;
    const updatedCards = currentCards.filter((card) => card.id !== cardId);

    this.customCardsSubject.next(updatedCards);
    this.saveToLocalStorage(updatedCards);
  }

  /**
   * すべてのカードを取得
   */
  getAllCards(): Card[] {
    return this.customCardsSubject.value;
  }

  /**
   * ローカルストレージに保存
   */
  private saveToLocalStorage(cards: Card[]): void {
    try {
      localStorage.setItem('customCards', JSON.stringify(cards));
    } catch (error) {
      console.error('カードの保存に失敗しました', error);
    }
  }

  /**
   * ローカルストレージから読み込み
   */
  private loadFromLocalStorage(): void {
    try {
      const saved = localStorage.getItem('customCards');
      if (saved) {
        const cards = JSON.parse(saved);
        this.customCardsSubject.next(cards);
      }
    } catch (error) {
      console.error('カードの読み込みに失敗しました', error);
    }
  }

  /**
   * すべてのカードをクリア
   */
  clearAllCards(): void {
    this.customCardsSubject.next([]);
    localStorage.removeItem('customCards');
  }
}
