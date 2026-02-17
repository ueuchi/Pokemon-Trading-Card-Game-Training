/**
 * 役割：
 * - カード作成フォームを表示
 * - プルダウン、ラジオボタンで選択式入力
 * - 作成したカードをプレビュー
 */

import pokemon from 'pokemon';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClientModule, HttpClient } from '@angular/common/http';
import { MaterialModule } from '../../shared/material.module';
import { map, startWith } from 'rxjs/operators';
import { Observable } from 'rxjs';

import {
  CardCreationForm,
  AttackCreationForm,
  EffectCreationForm,
  EnergyCostForm,
  CARD_PRESETS,
} from '../../game/types/card-creation.types';
import { AutoInputComponent } from '../../shared/auto-input/auto-input.component';
import { CardCreatorService } from '../../game/services/card-creator.service';
import { Card, EnergyType } from '../../game/types/game-state.types';

@Component({
  selector: 'card-creator',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ReactiveFormsModule,
    HttpClientModule,
    MaterialModule,
    AutoInputComponent,
  ],
  templateUrl: './card-creator.component.html',
  styleUrl: './card-creator.component.scss',
})
export class CardCreatorComponent implements OnInit {
  // プリセット定数をテンプレートで使用できるようにする
  readonly PRESETS = CARD_PRESETS;

  // フォームデータ
  formData: CardCreationForm = {
    name: '',
    cardType: 'POKEMON',
    evolution: 'BASIC',
    hp: 50,
    energyType: 'FIRE',
    retreatCost: 1,
    attacks: [],
  };

  /** 名前入力補助 */
  nameCtrl = new FormControl('');

  // 作成済みカード
  customCards: Card[] = [];

  filteredNames: Observable<string[]> = this.nameCtrl.valueChanges.pipe(
    startWith(''),
    map((value) => this.filter(value || '')),
  );

  // 現在編集中のワザのインデックス
  editingAttackIndex: number | null = null;

  // 一時的なワザフォーム
  tempAttack: AttackCreationForm = this.createEmptyAttack();

  readonly pokemonNameList = pokemon.all('ja');

  /** トレーナー名 */
  trainerNameList: string[] = [
    'アイリス',
    'アカネ',
    'アスナ',
    'アヤコ',
    'イツキ',
    'ウララ',
    'エリカ',
    'カスミ',
    'カレン',
    'キョウコ',
    'クチナシ',
    'コトネ',
    'サナ',
    'シロナ',
    'セレナ',
    'ダイゴ',
    'タケシ',
    'ナタネ',
    'ナツメ',
    'ノゾミ',
    'ハルカ',
    'ヒカリ',
    'フウロ',
    'マオ',
    'マリィ',
    'ミカン',
    'ミヅキ',
    'ミツル',
    'メイ',
    'モミ',
    'ヤナギ',
    'ユウリ',
    'ユウキ',
    'リーフ',
    'ルチア',
    'レッド',
    'レンブ',
    'ロケット団',
  ];

  constructor(
    private cardCreatorService: CardCreatorService,
    private http: HttpClient,
  ) {}

  ngOnInit(): void {
    // 作成済みカードを監視
    this.cardCreatorService.customCards$.subscribe((cards) => {
      this.customCards = cards;
    });

    // this.http
    //   .get<string[]>('assets/data/trainers.json')
    //   .subscribe((list: string[]) => (this.trainerNameList = list));
  }

  /**
   * 空のワザを作成
   */
  private createEmptyAttack(): AttackCreationForm {
    return {
      name: '',
      energyCosts: [{ type: 'COLORLESS', amount: 1 }],
      effects: [{ effectType: 'DAMAGE', damageAmount: 10 }],
    };
  }

  /**
   * カードタイプ変更
   */
  onCardTypeChange(): void {
    if (this.formData.cardType === 'ENERGY') {
      // エネルギーカードの場合はワザ不要
      this.formData.attacks = undefined;
    } else {
      // ポケモンカードの場合は最低1つのワザ
      if (!this.formData.attacks || this.formData.attacks.length === 0) {
        this.formData.attacks = [];
      }
    }
  }

  /**
   * ワザを追加開始
   */
  startAddingAttack(): void {
    this.tempAttack = this.createEmptyAttack();
    this.editingAttackIndex = null;
  }

  /**
   * ワザを編集開始
   */
  startEditingAttack(index: number): void {
    this.editingAttackIndex = index;
    this.tempAttack = JSON.parse(JSON.stringify(this.formData.attacks![index]));
  }

  /**
   * ワザを保存
   */
  saveAttack(): void {
    if (!this.formData.attacks) {
      this.formData.attacks = [];
    }

    if (this.editingAttackIndex !== null) {
      // 編集中のワザを更新
      this.formData.attacks[this.editingAttackIndex] = this.tempAttack;
    } else {
      // 新しいワザを追加
      this.formData.attacks.push(this.tempAttack);
    }

    this.tempAttack = this.createEmptyAttack();
    this.editingAttackIndex = null;
  }

  /**
   * ワザを削除
   */
  deleteAttack(index: number): void {
    if (this.formData.attacks) {
      this.formData.attacks.splice(index, 1);
    }
  }

  /**
   * ワザ編集をキャンセル
   */
  cancelAttackEdit(): void {
    this.tempAttack = this.createEmptyAttack();
    this.editingAttackIndex = null;
  }

  /**
   * エネルギーコストを追加
   */
  addEnergyCost(): void {
    this.tempAttack.energyCosts.push({ type: 'COLORLESS', amount: 1 });
  }

  /**
   * エネルギーコストを削除
   */
  removeEnergyCost(index: number): void {
    this.tempAttack.energyCosts.splice(index, 1);
  }

  /**
   * 効果を追加
   */
  addEffect(): void {
    this.tempAttack.effects.push({ effectType: 'DAMAGE', damageAmount: 10 });
  }

  /**
   * 効果を削除
   */
  removeEffect(index: number): void {
    this.tempAttack.effects.splice(index, 1);
  }

  /**
   * カードを作成
   */
  createCard(): void {
    const card = this.cardCreatorService.createCard(this.formData);

    if (card) {
      this.cardCreatorService.saveCard(card);
      alert(`カード「${card.name}」を作成しました！`);
      this.resetForm();
    } else {
      alert('カードの作成に失敗しました。入力内容を確認してください。');
    }
  }

  /**
   * カードを削除
   */
  deleteCard(cardId: string): void {
    if (confirm('このカードを削除しますか？')) {
      this.cardCreatorService.deleteCard(cardId);
    }
  }

  /**
   * フォームをリセット
   */
  resetForm(): void {
    this.formData = {
      name: '',
      cardType: this.formData.cardType,
      evolution: 'BASIC',
      hp: 50,
      energyType: 'FIRE',
      retreatCost: 1,
      attacks: [],
    };
    this.tempAttack = this.createEmptyAttack();
    this.editingAttackIndex = null;
  }

  /**
   * エネルギータイプの日本語名を取得
   */
  getEnergyTypeName(type: EnergyType): string {
    const option = this.PRESETS.ENERGY_TYPE_OPTIONS.find((opt) => opt.value === type);
    return option ? option.label : type;
  }

  /**
   * 効果タイプの日本語名を取得
   */
  getEffectTypeName(type: string): string {
    const option = this.PRESETS.EFFECT_TYPE_OPTIONS.find((opt) => opt.value === type);
    return option ? option.label : type;
  }

  /** 名前入力フィルター */
  private filter(value: string): string[] {
    const v = this.normalizeKana(value);
    return this.pokemonNameList.filter((name) => this.normalizeKana(name).includes(v));
  }

  /** かなを全て平仮名に変換 */
  private normalizeKana(str: string): string {
    return str.replace(/[\u3041-\u3096]/g, (ch) => String.fromCharCode(ch.charCodeAt(0) + 0x60));
  }

  onSelect(value: string) {
    this.formData.name = value;
  }

  /**
   * ワザが編集中か
   */
  get isEditingAttack(): boolean {
    return this.editingAttackIndex !== null || this.tempAttack.name !== '';
  }

  /**
   * カード作成可能か
   */
  get canCreateCard(): boolean {
    // if (!this.formData.name || this.formData.name.trim().length === 0) {
    //   return false;
    // }

    // if (this.formData.cardType === 'POKEMON') {
    //   return this.formData.attacks !== undefined && this.formData.attacks.length > 0;
    // }

    return true;
  }

  test() {
    const names = pokemon.all('ja');
    console.log(names);
  }
}
