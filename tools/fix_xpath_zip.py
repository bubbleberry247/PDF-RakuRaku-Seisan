# -*- coding: utf-8 -*-
"""
RKSファイルのZIPダウンロードXPathを修正 v4
完成版.rks（metaファイルあり）をベースに、XPathのみ修正
旧: //a/div/div/p → 新: //a[contains(@class,'sc-gyycJP')][1]
"""
import zipfile
import os

base_dir = r"C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\scenario"
source_name = "４３ETC-実行環境選択可能版-20251227-1ー申請用ファイル作成完成版.rks"
target_name = "４３ETC-実行環境選択可能版-20251227-1ー申請用ファイル作成完成版_fixed_v56.rks"

source_rks = os.path.join(base_dir, source_name)
target_rks = os.path.join(base_dir, target_name)

print(f"Source: {source_name}")
print(f"Target: {target_name}")
print()

with zipfile.ZipFile(source_rks, 'r') as z:
    code = z.read('Program.cs').decode('utf-8-sig')

# 修正
# 旧XPath: //a/div/div/p
# 新XPath: //a[contains(@class,'sc-gyycJP')][1]

old_xpath = '//a/div/div/p'
new_xpath = "//a[contains(@class,'sc-gyycJP')][1]"

if old_xpath in code:
    modified_code = code.replace(old_xpath, new_xpath)
    print(f"Replaced: {old_xpath}")
    print(f"     --> {new_xpath}")
else:
    print(f"Pattern not found: {old_xpath}")
    # 別のXPathパターンを探す
    print("Searching for alternative patterns...")
    lines = code.split('\n')
    for i, line in enumerate(lines):
        if 'ZIPダウンロード' in line or '.zip' in line.lower():
            print(f"  Line {i+1}: {line.strip()[:100]}")
    modified_code = code

# 新しいRKSを作成
with zipfile.ZipFile(source_rks, 'r') as src:
    with zipfile.ZipFile(target_rks, 'w', zipfile.ZIP_DEFLATED) as dst:
        for item in src.namelist():
            if item == 'Program.cs':
                dst.writestr(item, modified_code.encode('utf-8-sig'))
            else:
                dst.writestr(item, src.read(item))

print()
print(f"Created: {target_rks}")
