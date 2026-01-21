# -*- coding: utf-8 -*-
# RK10でシナリオv16を自動実行するスクリプト v5
import subprocess
import time
import pyautogui
from pywinauto import Application, Desktop

RKS_V16 = r"C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\scenario\４３ETC-実行環境選択可能版-20251227-1ー申請用ファイル作成_タスク結合版_fixed_v7_xpath_fix_v16.rks"

def main():
    print("=== RK10 v16 自動実行 v5 ===")

    # v16を開く
    print(f"Opening v16...")
    subprocess.Popen(['cmd', '/c', 'start', '', RKS_V16], shell=True)

    # 待機
    print("Waiting for file to open...")
    time.sleep(6)

    # 「編集しますか」ダイアログ - はい(Y)をクリック
    print("Handling edit dialog...")
    pyautogui.click(515, 340)
    time.sleep(4)

    # RK10に接続 - プロセス名で接続
    print("Connecting to RkScenarioManager...")
    app = Application(backend='uia').connect(path='RkScenarioManager.exe', timeout=10)

    # 全ウィンドウを取得し、ButtonRunを持つものを探す
    print("Looking for window with ButtonRun...")
    windows = app.windows()
    print(f"Found {len(windows)} windows")

    main_win = None
    for win in windows:
        try:
            # ButtonRunを探す
            try:
                children = win.descendants(control_type="Button")
                for child in children:
                    try:
                        aid = child.automation_id()
                        if aid == "ButtonRun":
                            main_win = win
                            print(f"Found window with ButtonRun!")
                            break
                    except:
                        pass
                if main_win:
                    break
            except:
                pass
        except:
            pass

    if not main_win:
        print("No window with ButtonRun found")
        print("Trying to use keyboard shortcut...")

        # アクティブウィンドウをフォーカス
        time.sleep(1)
        pyautogui.hotkey('alt', 'tab')
        time.sleep(1)

        # F5で実行
        print("Sending F5 to start scenario...")
        pyautogui.press('f5')
        time.sleep(2)
    else:
        main_win.set_focus()
        time.sleep(0.5)

        # ButtonRunをクリック
        try:
            run_btn = main_win.child_window(auto_id="ButtonRun")
            if run_btn.is_enabled():
                print("Clicking ButtonRun...")
                run_btn.click_input()
                print("Scenario started!")
            else:
                print("ButtonRun is disabled")
        except Exception as e:
            print(f"Error clicking ButtonRun: {e}")
            print("Trying F5...")
            pyautogui.press('f5')

    # 実行監視
    print("\n=== Monitoring ===")
    start_time = time.time()
    max_wait = 180
    last_status = ""

    while time.time() - start_time < max_wait:
        elapsed = time.time() - start_time

        # エラーダイアログチェック
        try:
            desktop = Desktop(backend='uia')
            for win in desktop.windows():
                try:
                    title = win.window_text()
                    if title:
                        # エンコーディング問題を回避
                        try:
                            if 'エラー' in title or 'Error' in title or 'error' in title.lower():
                                print(f"\n!!! ERROR DIALOG: {title} !!!")

                                # コピー
                                try:
                                    copy_btn = win.child_window(auto_id="CopyButton")
                                    copy_btn.click_input()
                                    time.sleep(0.5)
                                    import pyperclip
                                    error_text = pyperclip.paste()
                                    print(f"\nError content:\n{error_text[:2000]}")
                                except Exception as ce:
                                    print(f"Could not copy error: {ce}")

                                # 閉じる
                                try:
                                    close_btn = win.child_window(auto_id="CloseButton")
                                    close_btn.click_input()
                                except:
                                    try:
                                        win.close()
                                    except:
                                        pyautogui.press('escape')

                                return
                        except:
                            pass
                except:
                    pass
        except:
            pass

        # 完了チェック - ButtonRunが有効になったら完了
        if main_win:
            try:
                run_btn = main_win.child_window(auto_id="ButtonRun")
                stop_btn = main_win.child_window(auto_id="StopButton")

                run_enabled = run_btn.is_enabled()
                stop_enabled = stop_btn.is_enabled()

                status = f"Run={run_enabled}, Stop={stop_enabled}"
                if status != last_status:
                    print(f"\n  Status: {status}")
                    last_status = status

                if run_enabled and not stop_enabled:
                    print(f"\n=== Completed in {elapsed:.1f}s ===")
                    return
            except:
                pass

        print(f"\rRunning... {elapsed:.0f}s", end='', flush=True)
        time.sleep(2)

    print(f"\n=== Timeout after {max_wait}s ===")

if __name__ == "__main__":
    main()
