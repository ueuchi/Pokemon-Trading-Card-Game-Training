# カードゲームエンジン セットアップガイド

## 前提条件

- Node.js 18.x または 20.x（Voltaで管理推奨）
- Angular CLI 17以上

---

## セットアップ手順

### 1. Angularプロジェクトの初期化

すでにAngularプロジェクト（`card-game-engine`）を作成済みの場合は、このステップをスキップしてください。

```bash
# Angularプロジェクトを作成
ng new card-game-engine

# 質問に答える
? Would you like to add Angular routing? No
? Which stylesheet format would you like to use? SCSS

cd card-game-engine
```

---

### 2. ファイルの配置

以下のファイルを対応するディレクトリに配置してください：

```
card-game-engine/
├── docs/                                    # ドキュメント
│   ├── step1-design-explanation.md
│   ├── step2-implementation.md
│   ├── step3-ui-implementation.md
│   └── directory-structure.md
│
└── src/
    ├── app/
    │   ├── game/                            # ゲームロジック
    │   │   ├── types/
    │   │   │   ├── game-state.types.ts
    │   │   │   └── action.types.ts
    │   │   │
    │   │   ├── data/
    │   │   │   └── test-cards.data.ts
    │   │   │
    │   │   └── services/
    │   │       ├── game-state.factory.ts
    │   │       ├── effect-resolver.service.ts
    │   │       ├── game-rule.service.ts
    │   │       ├── action-executor.service.ts
    │   │       ├── turn-manager.service.ts
    │   │       ├── cpu-ai.service.ts
    │   │       └── game.service.ts
    │   │
    │   ├── components/
    │   │   └── game-board/
    │   │       ├── game-board.component.ts
    │   │       ├── game-board.component.html
    │   │       └── game-board.component.scss
    │   │
    │   ├── app.component.ts
    │   └── app.config.ts
    │
    ├── main.ts
    └── index.html
```

---

### 3. 依存関係のインストール

```bash
# プロジェクトディレクトリに移動
cd card-game-engine

# 依存関係をインストール
npm install
```

---

### 4. 開発サーバーの起動

```bash
# 開発サーバーを起動
ng serve

# または、自動でブラウザを開く
ng serve --open
```

ブラウザで `http://localhost:4200` にアクセスすると、ゲームが表示されます。

---

## 使い方

### ゲームの開始

1. ブラウザで `http://localhost:4200` にアクセス
2. 「ゲーム開始」ボタンをクリック
3. 自動でセットアップが完了し、ゲームが始まります

### プレイ方法

#### 基本的な流れ
1. **手札からカードを選択**
   - カードをクリックして選択
   - 選択したカードは青く光ります

2. **行動を選択**
   - **ポケモンを場に出す**: ポケモンカードを選択して「場に出す」ボタン
   - **エネルギーを付ける**: エネルギーカードを選択して「エネルギーを付ける」ボタン
   - **攻撃する**: ワザをクリックして「ワザを使う」ボタン

3. **ターン終了**
   - 「ターン終了」ボタンをクリック
   - CPUのターンに切り替わり、自動で行動します

4. **勝敗**
   - 相手のポケモンを倒すか、相手の山札が尽きると勝利
   - ゲーム終了画面が表示されます

### 操作のコツ

- **エネルギーは1ターンに1枚まで**
- **攻撃は1ターンに1回まで**
- **ワザを使うには十分なエネルギーが必要**
- **ログを見ると何が起きたかわかります**

---

## トラブルシューティング

### エラーが出る場合

#### 1. コンパイルエラー
```bash
# node_modules を削除して再インストール
rm -rf node_modules
npm install
```

#### 2. 型エラー
```bash
# TypeScriptの設定を確認
# tsconfig.json で "strict": false にすると一時的に回避可能
```

#### 3. 画面が表示されない
```bash
# ブラウザのコンソールでエラーを確認
# F12 を押して Developer Tools を開く
```

#### 4. サービスが見つからないエラー
```typescript
// すべてのサービスに @Injectable() があるか確認
@Injectable({
  providedIn: 'root'
})
export class GameService { ... }
```

---

## 開発のヒント

### ホットリロード
ファイルを編集すると自動でブラウザがリロードされます。

### デバッグ
```typescript
// コンポーネントやサービス内でconsole.logを使用
console.log('現在の状態:', this.gameState);
```

### ゲームログ
画面下部のログエリアで、すべてのアクションを確認できます。

---

## プロジェクト構成の確認

正しく配置されているか確認：

```bash
# ファイル構成を表示
tree src/app -I 'node_modules'
```

---

## 本番ビルド

ゲームを本番環境用にビルド：

```bash
# 本番ビルド
ng build

# dist フォルダに出力される
# dist/card-game-engine/browser/ の内容をWebサーバーに配置
```

---

## カスタマイズ

### カードを追加する

`src/app/game/data/test-cards.data.ts` を編集：

```typescript
export const NEW_POKEMON: PokemonCard = {
  id: 'new-pokemon-001',
  name: '新しいポケモン',
  type: 'POKEMON',
  hp: 70,
  energyType: 'FIRE',
  retreatCost: 1,
  attacks: [
    {
      name: '新しいワザ',
      energyCost: [{ type: 'FIRE', amount: 1 }],
      effects: [
        { type: 'DAMAGE', amount: 30, target: 'ACTIVE' }
      ]
    }
  ]
};
```

### デッキを変更する

同じファイルの `createTestDeck()` 関数を編集：

```typescript
export function createTestDeck() {
  const deck = [];
  
  // 好きなカードを追加
  deck.push({ ...NEW_POKEMON, id: 'new-pokemon-001' });
  
  return deck;
}
```

### スタイルを変更する

`src/app/components/game-board/game-board.component.scss` を編集：

```scss
// 色を変更
.btn-primary {
  background: #your-color;
}
```

---

## 次のステップ

### 学習リソース
- [Angular公式ドキュメント](https://angular.jp/)
- [RxJS公式ドキュメント](https://rxjs.dev/)
- [TypeScript公式ドキュメント](https://www.typescriptlang.org/)

### 拡張アイデア
1. カードデータをJSONファイルに移行
2. アニメーションを追加
3. サウンドエフェクトを追加
4. ベンチポケモンの実装
5. デッキエディターの作成

---

## よくある質問（FAQ）

### Q: Voltaは必須ですか？
A: いいえ、Node.jsがインストールされていれば動作します。ただしVoltaを使うとバージョン管理が楽です。

### Q: オンライン対戦はできますか？
A: 現在のバージョンでは、ローカルでのCPU対戦のみです。将来的にバックエンドを追加すれば可能です。

### Q: カードの画像は使えますか？
A: はい、カードデータに `imageUrl` プロパティを追加すれば表示できます（要実装）。

### Q: モバイルで動きますか？
A: レスポンシブデザインですが、PCでのプレイを推奨します。

### Q: 商用利用できますか？
A: このプロジェクトは学習目的です。商用利用の場合は法的確認が必要です。

---

## サポート

問題が解決しない場合：
1. ブラウザのコンソール（F12）でエラーを確認
2. `docs/` フォルダのドキュメントを読む
3. コードのコメントを読む

---

## まとめ

これでカードゲームエンジンのセットアップが完了です！

```bash
ng serve --open
```

を実行して、ゲームを楽しんでください！🎮
