# Playbook: RK10 UI自動化

## 概要
pywinautoを使用してRK10（KEYENCE RPA）のGUIを自動操作する手順

---

## 前提条件
- Python 3.11+
- pywinauto インストール済み（`pip install pywinauto`）
- pyautogui インストール済み（ダイアログ処理用）
- RK10 3.6.x インストール済み

---

## 基本セットアップ

```python
from pywinauto import Application
from pywinauto.keyboard import send_keys
import pyautogui
import time

# RK10アプリケーションに接続
app = Application(backend='uia').connect(title_re='.*RK-10.*')
main_window = app.window(title_re='.*RK-10.*')
```

---

## RK10 UI要素一覧

### メインウィンドウ

| 要素 | automation_id | 用途 |
|------|---------------|------|
| 実行ボタン | `ButtonRun` | シナリオ実行 |
| 部分実行ボタン | `PartlyRunButton` | 選択部分のみ実行 |
| 保存ボタン | `Saving` | シナリオ保存 |
| 停止ボタン | `StopButton` | 実行停止 |

### エラーダイアログ

| 要素 | automation_id | 説明 |
|------|---------------|------|
| コピーボタン | `CopyButton` | ビルドエラー時 |
| ファイル出力ボタン | `ContactInfoOutputButton` | ランタイムエラー時 |
| 閉じるボタン | `CloseButton` | 共通 |

---

## シナリオファイルを開く

```python
def open_scenario(rks_path):
    """シナリオファイルを開く"""
    # ファイル→開くメニュー
    main_window.menu_select("ファイル->開く")
    time.sleep(0.5)

    # ファイル選択ダイアログ
    file_dialog = app.window(title='開く')
    file_dialog.Edit.set_text(rks_path)
    file_dialog.Button1.click()  # 開く

    time.sleep(2)

    # 「編集しますか」ダイアログを処理
    handle_edit_dialog()

def handle_edit_dialog():
    """「編集しますか」ダイアログで「はい」をクリック

    注意: このダイアログはpywinautoで要素特定が困難なため
    pyautoguiの座標クリックを使用
    """
    time.sleep(0.5)
    pyautogui.click(515, 340)  # 「はい(Y)」ボタンの座標
```

---

## シナリオ実行

```python
def run_scenario():
    """シナリオを実行"""
    run_button = main_window.child_window(auto_id='ButtonRun')

    if run_button.is_enabled():
        run_button.click()
        print("シナリオ実行開始")
        return True
    else:
        print("実行ボタンが無効です")
        return False

def stop_scenario():
    """シナリオを停止"""
    stop_button = main_window.child_window(auto_id='StopButton')

    if stop_button.is_enabled():
        stop_button.click()
        print("シナリオ停止")
        return True
    return False
```

---

## 実行状態の監視

```python
def get_execution_state():
    """実行状態を取得

    Returns:
        str: 'idle', 'running', 'error', 'completed' のいずれか
    """
    run_button = main_window.child_window(auto_id='ButtonRun')
    stop_button = main_window.child_window(auto_id='StopButton')

    run_enabled = run_button.is_enabled()
    stop_enabled = stop_button.is_enabled()
    has_error = check_error_dialog()

    if has_error:
        return 'error'
    elif not run_enabled and stop_enabled:
        return 'running'
    elif run_enabled and not stop_enabled:
        return 'idle'  # または 'completed'

    return 'unknown'

def check_error_dialog():
    """エラーダイアログの存在をチェック"""
    try:
        # ビルドエラーダイアログ
        build_error = app.window(title_re='.*ビルドエラー.*')
        if build_error.exists(timeout=0.1):
            return True
    except:
        pass

    try:
        # ランタイムエラーダイアログ
        runtime_error = app.window(title_re='.*エラー.*')
        if runtime_error.exists(timeout=0.1):
            return True
    except:
        pass

    return False
```

---

## 実行完了待機

```python
def wait_for_completion(timeout=600):
    """シナリオ実行完了を待機

    Args:
        timeout: タイムアウト秒数

    Returns:
        str: 'completed', 'error', 'timeout' のいずれか
    """
    start_time = time.time()

    while time.time() - start_time < timeout:
        state = get_execution_state()

        if state == 'error':
            return 'error'
        elif state == 'idle':
            # 実行開始直後はidleの場合があるので少し待つ
            time.sleep(1)
            if get_execution_state() == 'idle':
                return 'completed'

        time.sleep(2)

    return 'timeout'
```

---

## エラー情報の取得

```python
def get_error_info():
    """エラーダイアログから情報を取得"""
    error_info = {
        'type': None,
        'message': None,
        'details': None
    }

    try:
        # ビルドエラー
        build_dialog = app.window(title_re='.*ビルドエラー.*')
        if build_dialog.exists(timeout=0.5):
            error_info['type'] = 'build'
            # コピーボタンでクリップボードに取得
            copy_btn = build_dialog.child_window(auto_id='CopyButton')
            copy_btn.click()
            time.sleep(0.2)
            import pyperclip
            error_info['message'] = pyperclip.paste()
            return error_info
    except:
        pass

    try:
        # ランタイムエラー
        error_dialog = app.window(title_re='.*エラー.*')
        if error_dialog.exists(timeout=0.5):
            error_info['type'] = 'runtime'
            # ファイル出力ボタンでログ出力
            output_btn = error_dialog.child_window(auto_id='ContactInfoOutputButton')
            if output_btn.exists():
                output_btn.click()
            return error_info
    except:
        pass

    return error_info

def close_error_dialog():
    """エラーダイアログを閉じる"""
    try:
        error_dialog = app.window(title_re='.*エラー.*|.*ビルドエラー.*')
        close_btn = error_dialog.child_window(auto_id='CloseButton')
        close_btn.click()
        return True
    except:
        return False
```

---

## 完全な自動実行スクリプト

```python
"""RK10シナリオ自動実行"""
from pywinauto import Application
import pyautogui
import time
import sys

def main(rks_path):
    # RK10に接続
    app = Application(backend='uia').connect(title_re='.*RK-10.*')
    main_window = app.window(title_re='.*RK-10.*')

    # シナリオを開く
    print(f"シナリオを開く: {rks_path}")
    open_scenario(rks_path)
    time.sleep(3)

    # 実行
    print("シナリオ実行開始")
    if not run_scenario():
        print("実行開始に失敗")
        return 1

    # 完了待機
    print("完了待機中...")
    result = wait_for_completion(timeout=600)

    if result == 'completed':
        print("シナリオ正常完了")
        return 0
    elif result == 'error':
        error = get_error_info()
        print(f"エラー発生: {error}")
        close_error_dialog()
        return 1
    else:
        print("タイムアウト")
        stop_scenario()
        return 1

if __name__ == '__main__':
    rks_path = sys.argv[1] if len(sys.argv) > 1 else None
    if not rks_path:
        print("Usage: python rk10_runner.py <scenario.rks>")
        sys.exit(1)

    sys.exit(main(rks_path))
```

---

## エディション選択（起動時）

```python
def select_edition():
    """RK10起動時のエディション選択で「RPA開発版AI付」を選択"""
    try:
        edition_dialog = app.window(title_re='.*エディション.*')
        if edition_dialog.exists(timeout=5):
            # リストから選択
            list_box = edition_dialog.child_window(control_type='ListBox')
            list_box.select('RPA開発版AI付')

            # OKボタン
            ok_btn = edition_dialog.child_window(title='OK')
            ok_btn.click()
            return True
    except:
        pass
    return False
```

---

## 注意事項

1. **ダイアログ処理が最優先**: 操作が効かない場合は必ずダイアログを確認
2. **座標クリック**: 一部のダイアログはpywinautoで特定困難なためpyautoguiを使用
3. **待機時間**: UI操作後は適切な待機を入れる（0.5〜2秒程度）
4. **バックエンド**: RK10はUIAバックエンドを使用（`backend='uia'`）
5. **権限**: 管理者権限が必要な場合がある
