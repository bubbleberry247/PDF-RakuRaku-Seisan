import zipfile
import os

v15_path = r"C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\scenario\４３ETC-実行環境選択可能版-20251227-1ー申請用ファイル作成_タスク結合版_fixed_v7_xpath_fix_v15.rks"
v16_path = r"C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\scenario\４３ETC-実行環境選択可能版-20251227-1ー申請用ファイル作成_タスク結合版_fixed_v7_xpath_fix_v16.rks"
new_cs_path = r"C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\shortest-test\program_v16.cs"

# Read new Program.cs
with open(new_cs_path, 'r', encoding='utf-8-sig') as f:
    new_code = f.read()

# Create new RKS from v15
with zipfile.ZipFile(v15_path, 'r') as src:
    with zipfile.ZipFile(v16_path, 'w', zipfile.ZIP_DEFLATED) as dst:
        for item in src.namelist():
            if item == 'Program.cs':
                dst.writestr(item, new_code.encode('utf-8-sig'))
            else:
                dst.writestr(item, src.read(item))

print(f'Created: {v16_path}')
print(f'Size: {os.path.getsize(v16_path)} bytes')
