# -*- coding: utf-8 -*-
"""
RKSファイルのEdge起動をショートカット経由に変更 v2
ExecuteApplication の引数を正しく修正
"""
import zipfile
import os

base_dir = r"C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\scenario"
source_name = "４３ETC-実行環境選択可能版-20251227-1ー申請用ファイル作成_タスク結合版_fixed_v3.rks"
target_name = "４３ETC-実行環境選択可能版-20251227-1ー申請用ファイル作成_タスク結合版_fixed_v53.rks"

source_rks = os.path.join(base_dir, source_name)
target_rks = os.path.join(base_dir, target_name)

print(f"Source: {source_name}")
print(f"Target: {target_name}")
print()

with zipfile.ZipFile(source_rks, 'r') as z:
    code = z.read('Program.cs').decode('utf-8-sig')

# ExecuteApplication の正しいシグネチャ:
# ExecuteApplication(string path, string arguments, string workingDirectory,
#                    WindowStyleType windowStyle, ProcessWaitingMethod waitMethod, int timeoutSecond)
#
# WindowStyleType: Normal, Minimized, Maximized, Hidden
# ProcessWaitingMethod: DoNotWait, WaitForExit, WaitForInputIdle

shortcut_launch = '''            // ショートカットからEdge起動
            Keyence.SystemActions.SystemAction.ExecuteApplication($@"C:\\Users\\masam\\Desktop\\Microsoft Edge.lnk", "", "", Keyence.SystemActions.WindowStyleType.Normal, Keyence.SystemActions.ProcessWaitingMethod.DoNotWait, 10);
            Keyence.ThreadingActions.ThreadingAction.Wait(3d);
'''

# 行121を特定して前に挿入
lines = code.split('\n')
new_lines = []
for i, line in enumerate(lines):
    if i == 120:  # 0-indexed, so line 121 is index 120
        new_lines.append(shortcut_launch.rstrip())
    new_lines.append(line)

modified_code = '\n'.join(new_lines)

# 新しいRKSを作成
with zipfile.ZipFile(source_rks, 'r') as src:
    with zipfile.ZipFile(target_rks, 'w', zipfile.ZIP_DEFLATED) as dst:
        for item in src.namelist():
            if item == 'Program.cs':
                dst.writestr(item, modified_code.encode('utf-8-sig'))
            else:
                dst.writestr(item, src.read(item))

print(f"Created: {target_rks}")
print()
print("Fixed ExecuteApplication with correct parameters:")
print("- WindowStyleType.Normal")
print("- ProcessWaitingMethod.DoNotWait")
print("- timeoutSecond: 10")
