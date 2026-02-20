#!/bin/bash
# ============================================================
# Phase 7 マージスクリプト
# 使い方: bash merge.sh /path/to/pokeca
# 例:     bash merge.sh ~/projects/pokeca
#         bash merge.sh .   （pokecaディレクトリ内から実行）
# ============================================================

set -e

# ---- 引数チェック ----
if [ -z "$1" ]; then
  echo "❌ プロジェクトのパスを指定してください"
  echo "   使い方: bash merge.sh /path/to/pokeca"
  exit 1
fi

PROJECT_DIR="$1"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ ! -d "$PROJECT_DIR" ]; then
  echo "❌ ディレクトリが見つかりません: $PROJECT_DIR"
  exit 1
fi

echo "============================================"
echo "🚀 Phase 7 マージ開始"
echo "   対象: $PROJECT_DIR"
echo "============================================"

# ---- マージ対象の定義 ----
# 形式: "出力側パス(SCRIPT_DIRからの相対)" "プロジェクト内の配置先(PROJECT_DIRからの相対)"
declare -a FILES=(
  "backend/main.py"                                                     "backend/main.py"
  "backend/api/game.py"                                                 "backend/api/game.py"
  "frontend/src/app/game/services/game-api.service.ts"                 "src/app/game/services/game-api.service.ts"
  "frontend/src/app/components/game-board/game-board.component.ts"     "src/app/components/game-board/game-board.component.ts"
  "frontend/src/app/components/game-board/game-board.component.html"   "src/app/components/game-board/game-board.component.html"
  "frontend/src/app/components/game-board/game-board.component.scss"   "src/app/components/game-board/game-board.component.scss"
)

# ---- バックアップ ----
BACKUP_DIR="$PROJECT_DIR/.merge_backup/phase7_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
echo ""
echo "📦 バックアップ先: $BACKUP_DIR"

MERGED=0
SKIPPED=0

# ---- ファイルをペアで処理 ----
for (( i=0; i<${#FILES[@]}; i+=2 )); do
  SRC="$SCRIPT_DIR/${FILES[$i]}"
  DEST_REL="${FILES[$i+1]}"
  DEST="$PROJECT_DIR/$DEST_REL"

  if [ ! -f "$SRC" ]; then
    echo "  ⚠️  スキップ (出力ファイルなし): ${FILES[$i]}"
    (( SKIPPED++ )) || true
    continue
  fi

  if [ -f "$DEST" ]; then
    BACKUP_PATH="$BACKUP_DIR/$DEST_REL"
    mkdir -p "$(dirname "$BACKUP_PATH")"
    cp "$DEST" "$BACKUP_PATH"
  fi

  mkdir -p "$(dirname "$DEST")"
  cp "$SRC" "$DEST"
  echo "  ✅ $DEST_REL"
  (( MERGED++ )) || true
done

echo ""
echo "============================================"
echo "✅ マージ完了"
echo "   マージ: ${MERGED} ファイル"
echo "   スキップ: ${SKIPPED} ファイル"
echo "   バックアップ: $BACKUP_DIR"
echo "============================================"

# ---- マージ確認 ----
echo ""
echo "🔍 マージ確認:"
ALL_OK=true
for (( i=0; i<${#FILES[@]}; i+=2 )); do
  SRC="$SCRIPT_DIR/${FILES[$i]}"
  DEST="$PROJECT_DIR/${FILES[$i+1]}"

  if [ ! -f "$SRC" ]; then continue; fi

  if [ ! -f "$DEST" ]; then
    echo "  ❌ ${FILES[$i+1]}  ← ファイルが存在しない"
    ALL_OK=false
  elif diff -q "$SRC" "$DEST" > /dev/null 2>&1; then
    echo "  ✅ ${FILES[$i+1]}"
  else
    echo "  ❌ ${FILES[$i+1]}  ← 内容が一致しない"
    ALL_OK=false
  fi
done

echo ""
if [ "$ALL_OK" = true ]; then
  echo "🎉 全ファイルのマージを確認しました！"
else
  echo "⚠️  一部のファイルに問題があります。上記を確認してください。"
fi

echo "============================================"
echo ""
echo "📋 次のステップ:"
echo "   1. バックエンド再起動:"
echo "      cd $PROJECT_DIR/backend && uvicorn main:app --reload"
echo "   2. フロントエンド確認:"
echo "      cd $PROJECT_DIR && ng serve"
echo "============================================"
