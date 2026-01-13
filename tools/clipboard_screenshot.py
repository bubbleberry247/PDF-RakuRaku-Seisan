# -*- coding: utf-8 -*-
"""
クリップボード スクリーンショット自動保存ツール

クリップボードに画像がコピーされたら自動的にリサイズして保存する。
Claude API制限対応: 複数画像リクエスト時は各画像2000px以下が必要

使用方法:
    python clipboard_screenshot.py

停止:
    Ctrl+C
"""

import os
import sys
import time
import hashlib
from datetime import datetime
from io import BytesIO

try:
    from PIL import Image, ImageGrab
except ImportError:
    print("Pillowがインストールされていません。")
    print("実行: pip install Pillow")
    sys.exit(1)

# 設定
MAX_WIDTH = 1600      # 最大幅（2000px制限に余裕を持たせる）
MAX_HEIGHT = 1200     # 最大高さ
SAVE_DIR = r"C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\docs\screenshots"
CHECK_INTERVAL = 0.5  # クリップボード確認間隔（秒）
COOLDOWN_TIME = 2.0   # 保存後のクールダウン時間（秒）

# 最後に保存した画像のハッシュ（重複防止用）
last_image_hash = None
last_save_time = 0    # 最後に保存した時刻


def get_image_hash(img):
    """画像のハッシュを計算（重複検出用）"""
    img_bytes = BytesIO()
    img.save(img_bytes, format='PNG')
    return hashlib.md5(img_bytes.getvalue()).hexdigest()


def resize_image(img, max_width=MAX_WIDTH, max_height=MAX_HEIGHT):
    """画像をリサイズ（アスペクト比維持）"""
    width, height = img.size

    # リサイズ不要な場合はそのまま返す
    if width <= max_width and height <= max_height:
        return img

    # アスペクト比を維持してリサイズ
    ratio = min(max_width / width, max_height / height)
    new_width = int(width * ratio)
    new_height = int(height * ratio)

    resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
    print(f"  リサイズ: {width}x{height} -> {new_width}x{new_height}")
    return resized


def generate_filename():
    """ファイル名を生成（タイムスタンプ + 連番）"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"screenshot_{timestamp}"

    # 同じタイムスタンプのファイルがあれば連番を付ける
    counter = 1
    while True:
        if counter == 1:
            filename = f"{base_name}.png"
        else:
            filename = f"{base_name}_{counter:03d}.png"

        filepath = os.path.join(SAVE_DIR, filename)
        if not os.path.exists(filepath):
            return filepath
        counter += 1


def save_clipboard_image():
    """クリップボードから画像を取得して保存"""
    global last_image_hash, last_save_time

    try:
        # クールダウン中はスキップ
        if time.time() - last_save_time < COOLDOWN_TIME:
            return False

        # クリップボードから画像を取得
        img = ImageGrab.grabclipboard()

        if img is None or not isinstance(img, Image.Image):
            return False

        # 重複チェック
        current_hash = get_image_hash(img)
        if current_hash == last_image_hash:
            return False

        # リサイズ
        resized_img = resize_image(img)

        # 保存
        filepath = generate_filename()

        # RGBAをRGBに変換（PNGで透過がある場合）
        if resized_img.mode == 'RGBA':
            # 白背景に合成
            background = Image.new('RGB', resized_img.size, (255, 255, 255))
            background.paste(resized_img, mask=resized_img.split()[3])
            resized_img = background
        elif resized_img.mode != 'RGB':
            resized_img = resized_img.convert('RGB')

        # PNG形式で保存（最適化あり）
        resized_img.save(filepath, 'PNG', optimize=True)

        # ファイルサイズを確認
        file_size = os.path.getsize(filepath)
        file_size_kb = file_size / 1024

        print(f"保存: {os.path.basename(filepath)} ({file_size_kb:.1f} KB)")

        last_image_hash = current_hash
        last_save_time = time.time()  # 保存時刻を記録
        return True

    except Exception as e:
        print(f"エラー: {e}")
        return False


def main():
    """メインループ"""
    print("=" * 50)
    print("クリップボード スクリーンショット自動保存ツール")
    print("=" * 50)
    print(f"保存先: {SAVE_DIR}")
    print(f"最大サイズ: {MAX_WIDTH}x{MAX_HEIGHT}")
    print(f"確認間隔: {CHECK_INTERVAL}秒")
    print("-" * 50)
    print("PrintScreenでスクリーンショットを撮ると自動保存されます")
    print("停止するには Ctrl+C を押してください")
    print("-" * 50)

    # 保存先フォルダを作成
    os.makedirs(SAVE_DIR, exist_ok=True)

    try:
        while True:
            save_clipboard_image()
            time.sleep(CHECK_INTERVAL)
    except KeyboardInterrupt:
        print("\n終了しました")


if __name__ == "__main__":
    main()
