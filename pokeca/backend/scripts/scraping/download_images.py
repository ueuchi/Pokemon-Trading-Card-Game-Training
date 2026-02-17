import requests
import json
import os
from pathlib import Path

def download_image(url, save_path):
    """
    画像をダウンロードして保存
    
    Args:
        url: 画像URL
        save_path: 保存先パス
    """
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        # ディレクトリを作成
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        
        # 画像を保存
        with open(save_path, 'wb') as f:
            f.write(response.content)
        
        print(f"Downloaded: {save_path}")
        return True
        
    except Exception as e:
        print(f"Error downloading {url}: {e}")
        return False

def download_all_images(json_file, output_dir):
    """
    JSONファイルからカード画像を全てダウンロード
    
    Args:
        json_file: スクレイピング結果のJSONファイル
        output_dir: 画像保存先ディレクトリ
    """
    # JSONファイルを読み込み
    with open(json_file, 'r', encoding='utf-8') as f:
        cards = json.load(f)
    
    print(f"Found {len(cards)} cards")
    
    success_count = 0
    for i, card in enumerate(cards):
        if 'image_url' not in card or not card['image_url']:
            print(f"[{i+1}/{len(cards)}] No image URL for: {card.get('name', 'Unknown')}")
            continue
        
        # ファイル名を生成（カード名 + 拡張子）
        card_name = card.get('name', f'card_{i}')
        # ファイル名に使えない文字を削除
        safe_name = "".join(c for c in card_name if c.isalnum() or c in (' ', '_', '-'))
        
        # 画像の拡張子を取得
        ext = Path(card['image_url']).suffix or '.png'
        
        save_path = os.path.join(output_dir, f"{safe_name}{ext}")
        
        print(f"[{i+1}/{len(cards)}] Downloading: {card_name}")
        
        if download_image(card['image_url'], save_path):
            success_count += 1
        
        # サーバー負荷軽減
        import time
        time.sleep(1)
    
    print(f"\n✅ Download completed!")
    print(f"Success: {success_count}/{len(cards)}")

if __name__ == "__main__":
    # スクレイピング結果から画像をダウンロード
    json_file = "backend/data/scraped/raw/all_cards.json"
    output_dir = "backend/data/images/official"
    
    download_all_images(json_file, output_dir)