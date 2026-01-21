# RK10でシナリオv16を自動実行するスクリプト v2
import subprocess
import time
import pyautogui
import pywinauto
from pywinauto import Application, Desktop

RKS_PATH = r"C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\scenario\４３ETC-実行環境選択可能版-20251227-1ー申請用ファイル作成_タスク結合版_fixed_v7_xpath_fix_v16.rks"

def find_rk10_window():
    """RK10のメインウィンドウを探す"""
    desktop = Desktop(backend='uia')
    windows = desktop.windows()

    for win in windows:
        try:
            title = win.window_text()
            if 'シナリオエディター' in title or 'RK-10' in title:
                # ButtonRunがあるウィンドウを探す
                try:
                    btn = win.child_window(auto_id="ButtonRun", control_type="Button")
                    if btn.exists():
                        return win
                except:
                    pass
        except:
            pass
    return None

def main():
    print("=== RK10 v16 自動実行 v2 ===")

    # 既存のRK10ウィンドウを探す
    print("Looking for existing RK10 window...")
    main_win = find_rk10_window()

    if main_win:
        print(f"Found RK10 window: {main_win.window_text()}")
    else:
        # RKSファイルを開く
        print(f"Opening: {RKS_PATH}")
        subprocess.Popen(['cmd', '/c', 'start', '', RKS_PATH], shell=True)

        # RK10起動待機
        print("Waiting for RK10 to start...")
        time.sleep(10)

        # 「編集しますか」ダイアログ処理
        print("Handling edit dialog...")
        time.sleep(1)
        pyautogui.click(515, 340)
        time.sleep(3)

        # ウィンドウを探す
        for _ in range(10):
            main_win = find_rk10_window()
            if main_win:
                break
            time.sleep(2)

    if not main_win:
        print("ERROR: Could not find RK10 window")
        return

    print(f"Connected to: {main_win.window_text()}")

    # フォーカスを合わせる
    main_win.set_focus()
    time.sleep(1)

    # 実行ボタンを探してクリック
    try:
        run_btn = main_win.child_window(auto_id="ButtonRun", control_type="Button")
        if run_btn.is_enabled():
            print("Clicking Run button...")
            run_btn.click_input()
            print("Scenario started!")
        else:
            print("Run button is disabled, scenario might already be running")
    except Exception as e:
        print(f"Could not click Run button: {e}")
        # F5キーで実行を試す
        print("Trying F5 key...")
        main_win.set_focus()
        pyautogui.press('f5')

    # 実行監視
    print("\n=== Monitoring execution ===")
    start_time = time.time()
    max_wait = 180  # 3分

    while time.time() - start_time < max_wait:
        try:
            # エラーダイアログチェック
            desktop = Desktop(backend='uia')
            for win in desktop.windows():
                try:
                    title = win.window_text()
                    if 'エラー' in title or 'Error' in title or '例外' in title:
                        print(f"\n!!! ERROR DIALOG: {title} !!!")

                        # エラー内容をコピー
                        try:
                            copy_btn = win.child_window(auto_id="CopyButton", control_type="Button")
                            if copy_btn.exists():
                                copy_btn.click_input()
                                time.sleep(0.5)
                                import pyperclip
                                error_text = pyperclip.paste()
                                print(f"Error:\n{error_text[:1000]}")
                        except:
                            pass

                        # 閉じる
                        try:
                            close_btn = win.child_window(auto_id="CloseButton", control_type="Button")
                            close_btn.click_input()
                        except:
                            win.close()

                        return
                except:
                    pass

            # 実行状態チェック
            try:
                run_btn = main_win.child_window(auto_id="ButtonRun", control_type="Button")

                if run_btn.is_enabled():
                    elapsed = time.time() - start_time
                    print(f"\n=== Execution completed in {elapsed:.1f}s ===")
                    return
                else:
                    elapsed = time.time() - start_time
                    print(f"\rRunning... {elapsed:.0f}s", end='', flush=True)
            except:
                pass

            time.sleep(2)

        except Exception as e:
            print(f"\nMonitoring error: {e}")
            time.sleep(2)

    print(f"\n=== Timeout after {max_wait}s ===")

if __name__ == "__main__":
    main()
