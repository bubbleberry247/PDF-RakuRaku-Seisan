# RK10でシナリオv16を自動実行するスクリプト
import subprocess
import time
import pyautogui
import pywinauto
from pywinauto import Application

RKS_PATH = r"C:\ProgramData\RK10\Robots\43 一般経費_日本情報サービス協同組合(ETC)明細の作成\scenario\４３ETC-実行環境選択可能版-20251227-1ー申請用ファイル作成_タスク結合版_fixed_v7_xpath_fix_v16.rks"

def main():
    print("=== RK10 v16 自動実行 ===")

    # RKSファイルを開く（RK10が起動する）
    print(f"Opening: {RKS_PATH}")
    subprocess.Popen(['cmd', '/c', 'start', '', RKS_PATH], shell=True)

    # RK10起動待機
    print("Waiting for RK10 to start...")
    time.sleep(8)

    # エディション選択ダイアログ処理
    try:
        app = Application(backend='uia').connect(title_re='.*エディション.*', timeout=10)
        dlg = app.window(title_re='.*エディション.*')
        print("Edition dialog found, selecting RPA開発版AI付...")

        # リストから「RPA開発版AI付」を選択
        try:
            list_box = dlg.child_window(control_type="List")
            items = list_box.children()
            for item in items:
                if "RPA開発版AI付" in item.window_text():
                    item.click_input()
                    break
        except:
            pass

        time.sleep(0.5)
        # OKボタン
        try:
            ok_btn = dlg.child_window(title="OK", control_type="Button")
            ok_btn.click_input()
        except:
            pyautogui.press('enter')

        print("Edition selected")
        time.sleep(3)
    except Exception as e:
        print(f"Edition dialog not found or already passed: {e}")

    # 「編集しますか」ダイアログ処理
    print("Checking for edit dialog...")
    time.sleep(2)
    try:
        # pyautoguiで座標クリック（標準位置）
        pyautogui.click(515, 340)
        print("Clicked 'Yes' on edit dialog")
        time.sleep(2)
    except Exception as e:
        print(f"Edit dialog handling: {e}")

    # RK10メインウィンドウに接続
    print("Connecting to RK10...")
    time.sleep(3)

    try:
        app = Application(backend='uia').connect(title_re='.*RK-10.*|.*シナリオエディター.*', timeout=30)
        main_win = app.window(title_re='.*RK-10.*|.*シナリオエディター.*')
        print(f"Connected to: {main_win.window_text()}")

        # 実行ボタンを探してクリック
        time.sleep(2)
        try:
            run_btn = main_win.child_window(auto_id="ButtonRun", control_type="Button")
            if run_btn.is_enabled():
                print("Clicking Run button...")
                run_btn.click_input()
                print("Scenario started!")
            else:
                print("Run button is disabled")
        except Exception as e:
            print(f"Could not find Run button: {e}")
            # フォールバック: F5キーで実行
            print("Trying F5 key...")
            pyautogui.press('f5')

    except Exception as e:
        print(f"Could not connect to RK10: {e}")
        return

    # 実行監視
    print("\n=== Monitoring execution ===")
    start_time = time.time()
    max_wait = 180  # 3分

    while time.time() - start_time < max_wait:
        try:
            # エラーダイアログチェック
            try:
                err_app = Application(backend='uia').connect(title_re='.*エラー.*|.*Error.*', timeout=1)
                err_dlg = err_app.window(title_re='.*エラー.*|.*Error.*')
                print(f"\n!!! ERROR DIALOG DETECTED !!!")
                print(f"Title: {err_dlg.window_text()}")

                # エラー内容をコピー
                try:
                    copy_btn = err_dlg.child_window(auto_id="CopyButton", control_type="Button")
                    copy_btn.click_input()
                    time.sleep(0.5)
                    import pyperclip
                    error_text = pyperclip.paste()
                    print(f"Error content:\n{error_text[:500]}")
                except:
                    pass

                # 閉じる
                try:
                    close_btn = err_dlg.child_window(auto_id="CloseButton", control_type="Button")
                    close_btn.click_input()
                except:
                    pyautogui.press('escape')

                break
            except:
                pass

            # 実行状態チェック
            try:
                run_btn = main_win.child_window(auto_id="ButtonRun", control_type="Button")
                stop_btn = main_win.child_window(auto_id="StopButton", control_type="Button")

                if run_btn.is_enabled() and not stop_btn.is_enabled():
                    elapsed = time.time() - start_time
                    print(f"\n=== Execution completed in {elapsed:.1f}s ===")
                    break
                else:
                    elapsed = time.time() - start_time
                    print(f"\rRunning... {elapsed:.0f}s", end='', flush=True)
            except:
                pass

            time.sleep(2)

        except Exception as e:
            print(f"\nMonitoring error: {e}")
            time.sleep(2)

    print("\n=== Done ===")

if __name__ == "__main__":
    main()
