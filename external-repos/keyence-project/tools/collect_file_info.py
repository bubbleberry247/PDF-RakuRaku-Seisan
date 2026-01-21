#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ファイル情報収集スクリプト
Windowsで文字化けしたファイル名を修正するために、
ファイル名とその詳細情報をJSONファイルに保存します。
"""

import os
import json
import hashlib
from datetime import datetime
from pathlib import Path


def calculate_file_hash(filepath):
    """ファイルのMD5ハッシュを計算"""
    try:
        hash_md5 = hashlib.md5()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        return f"Error: {str(e)}"


def collect_file_info(directory="."):
    """指定ディレクトリ内のファイル情報を収集"""
    file_info_list = []
    base_path = Path(directory).resolve()

    # 除外するディレクトリ
    exclude_dirs = {'.git', '.vscode', '__pycache__', 'venv', 'node_modules', '.env'}

    for root, dirs, files in os.walk(directory):
        # 除外ディレクトリをスキップ
        dirs[:] = [d for d in dirs if d not in exclude_dirs]

        for filename in files:
            filepath = Path(root) / filename

            try:
                stat_info = filepath.stat()

                file_info = {
                    "original_filename": filename,
                    "original_filename_bytes": filename.encode('utf-8').hex(),
                    "relative_path": str(filepath.relative_to(base_path)),
                    "absolute_path": str(filepath.absolute()),
                    "file_size": stat_info.st_size,
                    "file_size_human": format_size(stat_info.st_size),
                    "created_time": datetime.fromtimestamp(stat_info.st_ctime).isoformat(),
                    "modified_time": datetime.fromtimestamp(stat_info.st_mtime).isoformat(),
                    "file_extension": filepath.suffix,
                    "md5_hash": calculate_file_hash(filepath),
                    "parent_directory": filepath.parent.name,
                }

                file_info_list.append(file_info)

            except Exception as e:
                print(f"Error processing {filepath}: {e}")

    return file_info_list


def format_size(size_bytes):
    """ファイルサイズを人間が読みやすい形式に変換"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def save_file_info(file_info_list, output_file="file_info_mapping.json"):
    """ファイル情報をJSON形式で保存"""
    output_data = {
        "collected_at": datetime.now().isoformat(),
        "total_files": len(file_info_list),
        "files": file_info_list
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"✓ ファイル情報を {output_file} に保存しました")
    print(f"✓ 収集したファイル数: {len(file_info_list)}")


def main():
    print("ファイル情報を収集しています...")
    file_info_list = collect_file_info(".")
    save_file_info(file_info_list)

    # 日本語ファイル名を持つファイルを表示
    japanese_files = [f for f in file_info_list if any(ord(c) > 127 for c in f['original_filename'])]

    if japanese_files:
        print(f"\n日本語を含むファイル名: {len(japanese_files)}件")
        for f in japanese_files[:10]:  # 最初の10件を表示
            print(f"  - {f['original_filename']} ({f['file_size_human']})")


if __name__ == "__main__":
    main()
