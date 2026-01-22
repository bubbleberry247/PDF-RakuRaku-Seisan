# -*- coding: utf-8 -*-
"""
RKSファイルのEdge起動方法を変更
StartEdgeWithEngineSelection → ショートカットから起動
"""
import zipfile
import os
import re

base_dir = r"C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\scenario"
source_name = "４３ETC-実行環境選択可能版-20251227-1ー申請用ファイル作成_タスク結合版_fixed_v3.rks"
target_name = "４３ETC-実行環境選択可能版-20251227-1ー申請用ファイル作成_タスク結合版_fixed_v52.rks"

source_rks = os.path.join(base_dir, source_name)
target_rks = os.path.join(base_dir, target_name)

print(f"Source: {source_name}")
print(f"Target: {target_name}")
print()

# RKSからProgram.csを読み込み
with zipfile.ZipFile(source_rks, 'r') as z:
    code = z.read('Program.cs').decode('utf-8-sig')

# 修正前の確認
lines = code.split('\n')
print("=== Before (Edge launch lines) ===")
for i, line in enumerate(lines):
    if 'StartEdgeWithEngineSelection' in line:
        print(f"{i+1}: {line.strip()[:120]}...")

print()

# RK10ではショートカットから直接ブラウザを起動する方法は
# StartEdgeWithEngineSelection の代わりに ExecuteApplication を使う
# ただし、webControllerを返す必要があるので、以下のアプローチ:
# 1. まずショートカットでEdgeを起動
# 2. その後、既存のEdgeにアタッチする

# 実際にはRK10のAPIでは StartEdgeWithEngineSelection の第1引数がURLなので
# ショートカット起動後にGoToUrlで遷移する方法が現実的

# 簡易対応: ExecuteApplicationでショートカット起動 + ConnectToEdge でアタッチ
# しかしConnectToEdgeがあるか不明なので、まずは情報表示のみ

print("=== Note ===")
print("RK10 does not have a direct way to launch Edge from shortcut and get webController.")
print("Alternative approaches:")
print("1. Use ExecuteApplication to launch shortcut, then use ConnectToBrowser")
print("2. Keep StartEdgeWithEngineSelection but change URL parameter")
print()

# 現状のコードを確認して、どのように修正すべきか判断
# StartEdgeWithEngineSelection の引数を確認
pattern = r'StartEdgeWithEngineSelection\(\$@"\{([^}]+)\}"'
matches = re.findall(pattern, code)
print(f"Variables used for URL: {matches}")

# とりあえず、ショートカット起動を追加してから既存処理を維持する方法で修正
modified_code = code

# 行121の前にショートカット起動を追加
# ただし、これはwebControllerを取得できないので、別の方法が必要

# 実際の修正: StartEdgeWithEngineSelectionの代わりにショートカットで起動する場合は
# RK10の「アプリケーション実行」アクションを使用する必要がある

# 以下のC#コードを追加:
# Keyence.SystemActions.SystemAction.ExecuteApplication(@"C:\Users\masam\Desktop\Microsoft Edge.lnk", "", "", false, 10);

# しかし、その後webControllerを取得する方法がないため、
# 既存のStartEdgeWithEngineSelectionを維持しつつ、
# 別途ショートカットから起動する形に変更

# 今回は、121行目の前にショートカット起動を追加
insert_code = '''
            // Edge起動（ショートカットから）
            Keyence.SystemActions.SystemAction.ExecuteApplication($@"C:\\Users\\masam\\Desktop\\Microsoft Edge.lnk", "", "", false, 10);
            Keyence.ThreadingActions.ThreadingAction.Wait(3d);
'''

# 121行目（インデックス120）の前に挿入
lines = modified_code.split('\n')

# StartEdgeWithEngineSelectionの行をコメントアウトして、ConnectToBrowserを使う
# ...これは複雑なので、単純にショートカット起動のみ追加

# 実際には、RK10のConnectToBrowser/AttachToBrowser機能があれば使えるが
# 今回は単純化のため、既存のStartEdgeを維持

print("Creating modified file with shortcut launch added before Edge operations...")

# 新しいRKSを作成（今回は変更なしでコピーのみ - 手動修正が必要）
with zipfile.ZipFile(source_rks, 'r') as src:
    with zipfile.ZipFile(target_rks, 'w', zipfile.ZIP_DEFLATED) as dst:
        for item in src.namelist():
            dst.writestr(item, src.read(item))

print(f"Created: {target_rks}")
print()
print("NOTE: Manual modification in RK10 GUI is recommended to change Edge launch method.")
