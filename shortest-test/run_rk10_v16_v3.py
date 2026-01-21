# RK10でシナリオv16を自動実行するスクリプト v3
import time
import pyautogui
from pywinauto import Application, Desktop

def main():
    print("=== RK10 v16 自動実行 v3 ===")

    # RkScenarioManagerに接続
    print("Connecting to RkScenarioManager.exe...")
    try:
        app = Application(backend='uia').connect(path='RkScenarioManager.exe', timeout=10)
        print("Connected to RkScenarioManager")

        # トップレベルウィンドウを取得
        windows = app.windows()
        print(f"Found {len(windows)} windows")

        main_win = None
        for win in windows:
            try:
                title = win.window_text()
                print(f"  Window: {title}")
                # ButtonRunを持つウィンドウを探す
                try:
                    btn = win.child_window(auto_id="ButtonRun", control_type="Button")
                    if btn.exists():
                        main_win = win
                        print(f"  -> This window has ButtonRun!")
                        break
                except:
                    pass
            except Exception as e:
                print(f"  Error: {e}")

        if not main_win:
            print("Could not find main window with ButtonRun")
            # 全ウィンドウをダンプ
            desktop = Desktop(backend='uia')
            for w in desktop.windows():
                try:
                    t = w.window_text()
                    if t and ('RK' in t or 'シナリオ' in t or 'Keyence' in t):
                        print(f"Desktop window: {t}")
                except:
                    pass
            return

        print(f"\nUsing window: {main_win.window_text()}")
        main_win.set_focus()
        time.sleep(1)

        # 実行ボタンをクリック
        try:
            run_btn = main_win.child_window(auto_id="ButtonRun", control_type="Button")
            if run_btn.is_enabled():
                print("Clicking Run button...")
                run_btn.click_input()
                print("Scenario started!")
            else:
                print("Run button is disabled")
        except Exception as e:
            print(f"Run button error: {e}")
            return

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
                        if title and ('エラー' in title or 'Error' in title or '例外' in title):
                            print(f"\n!!! ERROR: {title} !!!")

                            # コピーボタン
                            try:
                                copy_btn = win.child_window(auto_id="CopyButton")
                                copy_btn.click_input()
                                time.sleep(0.5)
                                import pyperclip
                                print(f"Error content:\n{pyperclip.paste()[:1000]}")
                            except:
                                pass

                            # 閉じる
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

            # 実行状態チェック
            try:
                run_btn = main_win.child_window(auto_id="ButtonRun", control_type="Button")
                if run_btn.is_enabled():
                    print(f"\n=== Completed in {elapsed:.1f}s ===")
                    return
            except:
                pass

            print(f"\rRunning... {elapsed:.0f}s", end='', flush=True)
            time.sleep(2)

        print(f"\n=== Timeout ===")

    except Exception as e:
        print(f"Connection error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
