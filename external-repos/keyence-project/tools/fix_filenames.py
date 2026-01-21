#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ファイル名修正スクリプト
file_info_mapping.jsonを使用して、
Windowsで文字化けしたファイル名を正しい名前にリネームします。
"""

import os
import json
import shutil
from pathlib import Path
from datetime import datetime


def load_file_mapping(mapping_file="file_info_mapping.json"):
    """ファイルマッピング情報を読み込む"""
    if not os.path.exists(mapping_file):
        print(f"Error: {mapping_file} が見つかりません")
        print("先に collect_file_info.py を実行してください")
        return None

    with open(mapping_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def find_file_by_hash(target_hash, file_info_list):
    """MD5ハッシュからファイル情報を検索"""
    for file_info in file_info_list:
        if file_info['md5_hash'] == target_hash:
            return file_info
    return None


def find_file_by_size_and_dir(target_size, parent_dir, file_info_list):
    """ファイルサイズと親ディレクトリからファイル情報を検索"""
    matches = [
        f for f in file_info_list
        if f['file_size'] == target_size and f['parent_directory'] == parent_dir
    ]
    return matches


def calculate_file_hash(filepath):
    """ファイルのMD5ハッシュを計算"""
    import hashlib
    try:
        hash_md5 = hashlib.md5()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        return None


def detect_garbled_files(directory="."):
    """文字化けの可能性があるファイルを検出"""
    garbled_files = []
    exclude_dirs = {'.git', '.vscode', '__pycache__', 'venv', 'node_modules'}

    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]

        for filename in files:
            # 文字化けの特徴: 不明な文字、疑問符、特殊な文字コード
            if any(char in filename for char in ['�', '?']) or \
               filename.encode('utf-8', errors='ignore').decode('utf-8') != filename:
                filepath = Path(root) / filename
                garbled_files.append(filepath)

    return garbled_files


def rename_file_interactive(mapping_data):
    """対話形式でファイル名を修正"""
    if not mapping_data:
        return

    file_info_list = mapping_data.get('files', [])
    print(f"\nファイルマッピング情報を読み込みました")
    print(f"収集日時: {mapping_data['collected_at']}")
    print(f"総ファイル数: {mapping_data['total_files']}")

    # 現在のディレクトリ内のファイルを取得
    current_files = []
    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in {'.git', '.vscode', '__pycache__', 'venv', 'node_modules'}]
        for filename in files:
            if filename not in ['collect_file_info.py', 'fix_filenames.py', 'file_info_mapping.json']:
                filepath = Path(root) / filename
                current_files.append(filepath)

    if not current_files:
        print("\n修正対象のファイルが見つかりませんでした")
        return

    print(f"\n現在のディレクトリ内のファイル: {len(current_files)}件")
    print("\n--- ファイル名の修正を開始します ---\n")

    renamed_count = 0
    backup_dir = Path("renamed_backup") / datetime.now().strftime("%Y%m%d_%H%M%S")

    for current_file in current_files:
        print(f"\n現在のファイル: {current_file.name}")
        print(f"パス: {current_file}")
        print(f"サイズ: {current_file.stat().st_size} bytes")

        # ハッシュで照合
        file_hash = calculate_file_hash(current_file)
        if file_hash:
            matched_info = find_file_by_hash(file_hash, file_info_list)

            if matched_info:
                original_name = matched_info['original_filename']
                print(f"\n✓ 一致するファイルが見つかりました!")
                print(f"元のファイル名: {original_name}")

                if current_file.name != original_name:
                    response = input(f"\nこのファイル名に変更しますか? (y/n): ").strip().lower()

                    if response == 'y':
                        new_path = current_file.parent / original_name

                        # バックアップを作成
                        backup_dir.mkdir(parents=True, exist_ok=True)
                        backup_path = backup_dir / current_file.name
                        shutil.copy2(current_file, backup_path)

                        # リネーム
                        current_file.rename(new_path)
                        print(f"✓ リネームしました: {original_name}")
                        print(f"  バックアップ: {backup_path}")
                        renamed_count += 1
                else:
                    print("ファイル名は既に正しい名前です")
            else:
                print("× マッピング情報に一致するファイルが見つかりませんでした")

        print("-" * 60)

    print(f"\n\n=== 完了 ===")
    print(f"リネームしたファイル数: {renamed_count}")
    if renamed_count > 0:
        print(f"バックアップ: {backup_dir}")


def main():
    print("=" * 60)
    print("ファイル名修正ツール")
    print("=" * 60)

    mapping_data = load_file_mapping()
    if mapping_data:
        rename_file_interactive(mapping_data)
    else:
        print("\nまず collect_file_info.py を実行してファイル情報を収集してください")


if __name__ == "__main__":
    main()
