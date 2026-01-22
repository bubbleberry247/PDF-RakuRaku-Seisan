# -*- coding: utf-8 -*-
"""
RKSファイルの日付フォーマット修正スクリプト v2
完成版.rksをベースに、日付フォーマットを修正
"""
import zipfile
import os
import sys

# パス設定
base_dir = r"C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\scenario"

# 完成版（metaファイルが正しい）をベースに使用
source_name = "４３ETC-実行環境選択可能版-20251227-1ー申請用ファイル作成完成版.rks"
target_name = "４３ETC-実行環境選択可能版-20251227-1ー申請用ファイル作成完成版_fixed_v51.rks"

source_rks = os.path.join(base_dir, source_name)
target_rks = os.path.join(base_dir, target_name)

print(f"Source: {source_rks}")
print(f"Target: {target_rks}")
print()

# ファイル存在確認
if not os.path.exists(source_rks):
    print(f"Error: Source file not found")
    sys.exit(1)

# RKSからProgram.csを読み込み
with zipfile.ZipFile(source_rks, 'r') as z:
    code = z.read('Program.cs').decode('utf-8-sig')

lines = code.split('\n')

# ConvertFromTextToDatetime を検索
print("=== ConvertFromTextToDatetime locations ===")
for i, line in enumerate(lines):
    if 'ConvertFromTextToDatetime' in line:
        print(f"{i+1}: {line.strip()[:120]}")

print()

# 修正: yyyy年MM月dd日 → yyyy年M月d日
modified_code = code

if 'yyyy年MM月dd日' in code:
    modified_code = modified_code.replace('yyyy年MM月dd日', 'yyyy年M月d日')
    print("Applied: yyyy年MM月dd日 -> yyyy年M月d日")
else:
    print("Warning: Pattern not found")
    # 168行目付近を表示
    print("Lines 165-175:")
    for i in range(164, min(176, len(lines))):
        print(f"{i+1}: {lines[i][:100]}")

# 新しいRKSを作成（metaファイルも含めてコピー）
with zipfile.ZipFile(source_rks, 'r') as src:
    with zipfile.ZipFile(target_rks, 'w', zipfile.ZIP_DEFLATED) as dst:
        for item in src.namelist():
            if item == 'Program.cs':
                dst.writestr(item, modified_code.encode('utf-8-sig'))
            else:
                # meta, id, version などはそのままコピー
                dst.writestr(item, src.read(item))

print()
print(f"Created: {target_rks}")
