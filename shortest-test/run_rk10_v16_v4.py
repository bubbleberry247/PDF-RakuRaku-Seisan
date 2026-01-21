# RK10でシナリオv16を自動実行するスクリプト v4
import subprocess
import time
import pyautogui
from pywinauto import Application, Desktop

RKS_V16 = r"C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\scenario\４３ETC-実行環境選択可能版-20251227-1ー申請用ファイル作成_タスク結合版_fixed_v7_xpath_fix_v16.rks"

def main():
    print("=== RK10 v16 自動実行 v4 ===")

    # v16を開く
    print(f"Opening v16: {RKS_V16}")
    subprocess.Popen(['cmd', '/c', 'start', '', RKS_V16], shell=True)

    # 待機
    print("Waiting for file to open...")
    time.sleep(5)

    # 「編集しますか」ダイアログ - はい(Y)をクリック
    print("Handling edit dialog (clicking Yes)...")
    pyautogui.click(515, 340)
    time.sleep(3)

    # RK10に接続
    print("Connecting to RkScenarioManager...")
    app = Application(backend='uia').connect(path='RkScenarioManager.exe', timeout=10)

    # v16ウィンドウを探す
    main_win = None
    for win in app.windows():
        try:
            title = win.window_text()
            if 'v16' in title:
                main_win = win
                print(f"Found v16 window: {title[:50]}...")
                break
        except:
            pass

    if not main_win:
        print("v16 window not found, using first scenario window...")
        for win in app.windows():
            try:
                title = win.window_text()
                if 'シナリオエディター' in title or 'fixed_v7_xpath_fix_v16' in title:
                    main_win = win
                    break
            except:
                pass

    if not main_win:
        # 最後に開いたウィンドウを使う
        windows = app.windows()
        for win in windows:
            try:
                title = win.window_text()
                if 'シナリオエディター' in title:
                    main_win = win
                    break
            except:
                pass

    if not main_win:
        print("ERROR: Could not find scenario window")
        return

    print(f"Using window: {main_win.window_text()[:60]}...")
    main_win.set_focus()
    time.sleep(1)

    # 子コントロールを列挙してButtonRunを探す
    print("Looking for Run button...")
    run_btn = None
    try:
        # 直接auto_idで探す
        run_btn = main_win.child_window(auto_id="ButtonRun")
        print(f"Found ButtonRun: enabled={run_btn.is_enabled()}")
    except Exception as e:
        print(f"ButtonRun not found directly: {e}")

        # 全ボタンを列挙
        print("Listing all buttons...")
        try:
            buttons = main_win.descendants(control_type="Button")
            for btn in buttons[:20]:
                try:
                    name = btn.window_text()
                    aid = btn.automation_id()
                    print(f"  Button: '{name}' (auto_id: {aid})")
                    if 'Run' in aid or '実行' in name:
                        run_btn = btn
                except:
                    pass
        except Exception as e2:
            print(f"Error listing buttons: {e2}")

    if run_btn:
        if run_btn.is_enabled():
            print("\nClicking Run button...")
            run_btn.click_input()
            print("Scenario started!")
        else:
            print("Run button is disabled")
            return
    else:
        print("Run button not found, trying F5...")
        main_win.set_focus()
        time.sleep(0.5)
        pyautogui.press('f5')
        print("Sent F5 key")

    # 実行監視
    print("\n=== Monitoring execution ===")
    start_time = time.time()
    max_wait = 180

    while time.time() - start_time < max_wait:
        elapsed = time.time() - start_time

        # エラーダイアログチェック
        try:
            desktop = Desktop(backend='uia')
            for win in desktop.windows():
                try:
                    title = win.window_text()
                    if title and ('エラー' in title or 'Error' in title):
                        print(f"\n!!! ERROR: {title} !!!")
                        try:
                            copy_btn = win.child_window(auto_id="CopyButton")
                            copy_btn.click_input()
                            time.sleep(0.5)
                            import pyperclip
                            print(f"Content:\n{pyperclip.paste()[:1500]}")
                        except:
                            pass
                        try:
                            close_btn = win.child_window(auto_id="CloseButton")
                            close_btn.click_input()
                        except:
                            pass
                        return
                except:
                    pass
        except:
            pass

        # 完了チェック
        try:
            if run_btn and run_btn.is_enabled():
                print(f"\n=== Completed in {elapsed:.1f}s ===")
                return
        except:
            pass

        print(f"\rRunning... {elapsed:.0f}s", end='', flush=True)
        time.sleep(2)

    print(f"\n=== Timeout ===")

if __name__ == "__main__":
    main()
