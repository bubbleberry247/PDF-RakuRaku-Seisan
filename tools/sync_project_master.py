# -*- coding: utf-8 -*-
"""軽技Web「受注工事一覧」エクスポート → project_master.xlsx 自動生成。

使い方:
  python tools/sync_project_master.py               # 通常実行
  python tools/sync_project_master.py --inspect     # UI識別子を表示して終了（現地調査用）
  python tools/sync_project_master.py --no-launch   # 軽技Web 既起動の場合
  python tools/sync_project_master.py --dry-run --input <xlsx>  # 軽技操作なし、変換のみ

前提:
  - VPN 接続済み（172.16.0.21 に到達可能）
  - Windows 資格情報マネージャーに "Karuwaza_Login_TIC" が登録済み
  - pywinauto インストール済み
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# --- パス定義 ---
TOOLS_DIR = Path(__file__).resolve().parent
SCENARIO_DIR = TOOLS_DIR.parent
CONFIG_DIR = SCENARIO_DIR / "config"
S38_TOOLS_DIR = Path(r"C:\ProgramData\RK10\Robots\38受注登録\tools")

# 軽技Web ショートカット
KARUWAZA_SHORTCUT = Path(r"C:\Users\masam\Desktop\基幹システム_資源配信.exe - ショートカット.lnk")

# 資格情報ターゲット
CREDENTIAL_TARGET = "Karuwaza_Login_TIC"

# マッピング JSON
MAPPING_JSON = CONFIG_DIR / "project_master_export_mapping_juchu.example.json"

# エクスポートファイルの出力先（デスクトップ）
EXPORT_GLOB = "受注工事一覧_*.xlsx"


# --- 資格情報取得（シナリオ38 credential_manager を流用）---
def _get_credential(target: str):
    if S38_TOOLS_DIR.exists():
        sys.path.insert(0, str(S38_TOOLS_DIR))
        try:
            from common.credential_manager import get_credential
            return get_credential(target)
        except ImportError:
            pass
    # フォールバック: ctypes 直接実装
    return _get_credential_raw(target)


def _get_credential_raw(target: str):
    CRED_TYPE_GENERIC = 1

    class CRED(ctypes.Structure):
        _fields_ = [
            ("Flags", wt.DWORD), ("Type", wt.DWORD),
            ("TargetName", wt.LPWSTR), ("Comment", wt.LPWSTR),
            ("LastWritten", wt.FILETIME), ("CredentialBlobSize", wt.DWORD),
            ("CredentialBlob", ctypes.POINTER(ctypes.c_byte)),
            ("Persist", wt.DWORD), ("AttributeCount", wt.DWORD),
            ("Attributes", ctypes.c_void_p), ("TargetAlias", wt.LPWSTR),
            ("UserName", wt.LPWSTR),
        ]

    ptr = ctypes.POINTER(CRED)()
    if not ctypes.windll.advapi32.CredReadW(target, CRED_TYPE_GENERIC, 0, ctypes.byref(ptr)):
        return None
    c = ptr.contents
    username = c.UserName or ""
    password = ""
    if c.CredentialBlob and c.CredentialBlobSize > 0:
        password = bytes(c.CredentialBlob[:c.CredentialBlobSize]).decode("utf-16-le")
    ctypes.windll.advapi32.CredFree(ptr)
    return (username, password)


# --- VPN チェック ---
def check_vpn(host: str = "172.16.0.21") -> None:
    result = subprocess.run(
        ["ping", host, "-n", "1", "-w", "2000"],
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"VPN未接続: {host} に到達できません。VPN接続後に再実行してください。")
    print(f"[OK] VPN接続確認: {host}")


# --- 軽技Web 起動 + 接続 ---
def launch_and_connect(no_launch: bool = False):
    from pywinauto import Application
    from pywinauto.application import ProcessNotFoundError

    if not no_launch:
        if not KARUWAZA_SHORTCUT.exists():
            raise FileNotFoundError(f"ショートカットが見つかりません: {KARUWAZA_SHORTCUT}")
        os.startfile(str(KARUWAZA_SHORTCUT))
        print("[INFO] 軽技Web を起動しました。メインメニュー表示を待機中...")

    app = Application(backend="uia")
    for attempt in range(24):  # 最大120秒
        try:
            app.connect(title_re=".*メインメニュー.*", timeout=5)
            print("[OK] 軽技Web メインメニューに接続しました")
            return app
        except Exception:
            print(f"  待機中... ({attempt + 1}/24)")
            # ログイン画面が出た場合は処理
            try:
                login_app = Application(backend="uia")
                login_app.connect(title_re=".*ログイン.*", timeout=2)
                _do_login(login_app)
            except Exception:
                pass
            time.sleep(5)

    raise TimeoutError("軽技Web メインメニューへの接続がタイムアウトしました（120秒）")


def _do_login(app) -> None:
    cred = _get_credential(CREDENTIAL_TARGET)
    if not cred:
        raise RuntimeError(f"資格情報が取得できません: {CREDENTIAL_TARGET}")
    username, password = cred
    win = app.top_window()
    # ID/PW フィールドを探して入力
    try:
        id_field = win.child_window(auto_id="txtUserId")
        id_field.set_text(username)
        pw_field = win.child_window(auto_id="txtPassword")
        pw_field.set_text(password)
        from pywinauto.keyboard import send_keys
        send_keys("{ENTER}")
        time.sleep(2.0)
        print("[INFO] ログイン操作を実行しました")
    except Exception as e:
        print(f"[WARN] ログイン操作に失敗しました（手動ログインが必要かもしれません）: {e}")


# --- UI 識別子を表示する調査用モード ---
def inspect_mode(app) -> None:
    print("\n=== UI 識別子（メインウィンドウ）===")
    main = app.top_window()
    main.print_control_identifiers()
    print("\n=== 受注管理タブ遷移後の識別子を確認するには --inspect を受注管理タブ選択後に再実行してください ===")


# --- 受注管理タブ → 受注工事一覧 遷移 ---
def navigate_to_juchu_list(app) -> object:
    """受注工事一覧 ウィンドウを返す。
    TODO T1: 現地確認が必要 → `python sync_project_master.py --inspect` で識別子を確認
    """
    from pywinauto.keyboard import send_keys

    main = app.top_window()

    # 受注管理タブ（Index: 0）を選択
    try:
        tab_ctrl = main.child_window(auto_id="TabMainMenu")
        juchu_tab = tab_ctrl.child_window(title="TabItem Index : 0")

        # 子ウィンドウ最小化 → タブ選択（MEMORY.md確定パターン）
        SW_MINIMIZE = 6
        for child in main.children():
            try:
                ctypes.windll.user32.ShowWindow(child.handle, SW_MINIMIZE)
            except Exception:
                pass
        juchu_tab.iface_selection_item.Select()
        time.sleep(1.0)
        print("[INFO] 受注管理タブを選択しました")
    except Exception as e:
        print(f"[WARN] タブ選択に失敗: {e} （手動で受注管理タブを開いてください）")

    # 受注工事一覧 ボタン/メニューを探す
    # TODO T1: サブメニューの正確な名前を --inspect で確認後に修正
    for title_candidate in ("受注工事一覧", "工事一覧", "受注一覧"):
        try:
            btn = main.child_window(title=title_candidate, found_index=0)
            btn.click_input()
            time.sleep(1.5)
            print(f"[INFO] 「{title_candidate}」をクリックしました")
            break
        except Exception:
            continue
    else:
        # BM_CLICK 直送フォールバック
        try:
            btn = main.child_window(title_re=".*一覧.*", found_index=0)
            hwnd = btn.handle
            ctypes.windll.user32.SendMessageW(hwnd, 0x00F5, 0, 0)  # BM_CLICK
            time.sleep(1.5)
            print("[INFO] BM_CLICK で一覧ボタンをクリックしました")
        except Exception as e:
            raise RuntimeError(
                f"受注工事一覧への遷移に失敗しました。\n"
                f"  → `python tools/sync_project_master.py --inspect` で UI 識別子を確認し、\n"
                f"    このスクリプトの navigate_to_juchu_list() を修正してください。\n"
                f"  元のエラー: {e}"
            )

    # 受注工事一覧 ウィンドウを取得
    try:
        list_win = app.window(title_re=".*受注工事一覧.*")
        list_win.wait("visible", timeout=10)
        print("[OK] 受注工事一覧 ウィンドウを確認しました")
        return list_win
    except Exception:
        print("[WARN] 受注工事一覧ウィンドウが見つかりません。メインウィンドウを使用します")
        return main


# --- 検索 → エクスポート ---
def export_to_xlsx(list_win) -> Path:
    from pywinauto.keyboard import send_keys

    # 件数フィールドに 9999 → F3（検索）
    try:
        search_field = list_win.child_window(auto_id="txt検索")
        search_field.set_text("9999")
        print("[INFO] 件数フィールドに 9999 を入力しました")
    except Exception as e:
        print(f"[WARN] txt検索フィールドが見つかりません: {e}")

    send_keys("{F3}")
    print("[INFO] F3（検索実行）を送信しました")
    # TODO T3: ステータスバー or グリッド行数で完了を検知する方式に変更
    time.sleep(4.0)

    # F10（Excel エクスポート）
    before = set(Path.home().glob(f"Desktop/{EXPORT_GLOB}"))
    send_keys("{F10}")
    print("[INFO] F10（Excel エクスポート）を送信しました")
    time.sleep(2.5)

    # 保存ダイアログ対応
    # TODO T2: 保存ダイアログの構造を現地確認後に調整
    _handle_save_dialog()
    time.sleep(5.0)

    after = set(Path.home().glob(f"Desktop/{EXPORT_GLOB}"))
    new_files = after - before
    if not new_files:
        raise RuntimeError(
            "エクスポートファイルが Desktop に生成されませんでした。\n"
            "  → 保存ダイアログが別の形式の場合、_handle_save_dialog() を修正してください。"
        )
    export_path = max(new_files)  # タイムスタンプ付きファイル名 → 最新が唯一のはず
    print(f"[OK] エクスポート完了: {export_path}")
    return export_path


def _handle_save_dialog(title: str = "保存先を指定してください", timeout: int = 10) -> None:
    from pywinauto.keyboard import send_keys

    hwnd = _find_dialog_hwnd(title, timeout)
    if hwnd:
        ctypes.windll.user32.SetForegroundWindow(hwnd)
        time.sleep(0.3)
        send_keys("{ENTER}")
        print(f"[INFO] 保存ダイアログ（{title}）に Enter を送信しました")
    else:
        print(f"[WARN] 保存ダイアログ「{title}」が見つかりませんでした（既に保存済みか別タイトルの可能性）")


def _find_dialog_hwnd(title: str, timeout: int = 10) -> int | None:
    """Win32 EnumWindows で指定タイトルのダイアログを探す。"""
    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
    def enum_callback(hwnd, _):
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd) + 1
        buf = ctypes.create_unicode_buffer(length)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length)
        if title in buf.value:
            found.append(hwnd)
        return True

    deadline = time.time() + timeout
    while time.time() < deadline:
        ctypes.windll.user32.EnumWindows(enum_callback, 0)
        if found:
            return found[0]
        found.clear()
        time.sleep(0.5)
    return None


# --- build_project_master_from_export.py 呼び出し ---
def build_project_master(export_path: Path) -> Path:
    today = datetime.now().strftime("%Y%m%d")
    output_path = CONFIG_DIR / f"project_master_v{today}.xlsx"

    # 既存マスターを base として継承
    existing = sorted(CONFIG_DIR.glob("project_master_v*.xlsx"))
    base_args = ["--base-master", str(existing[-1])] if existing else []

    cmd = [
        sys.executable,
        str(TOOLS_DIR / "build_project_master_from_export.py"),
        "--input", str(export_path),
        "--output", str(output_path),
        "--mapping-json", str(MAPPING_JSON),
        "--infer-busho-from-name",
        *base_args,
    ]
    print(f"[INFO] 変換コマンド: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.stdout:
        print(result.stdout.strip())
    if result.returncode != 0:
        raise RuntimeError(f"build_project_master_from_export 失敗:\n{result.stderr}")

    if not output_path.exists():
        raise RuntimeError(f"出力ファイルが見つかりません: {output_path}")
    print(f"[OK] project_master 更新完了: {output_path}")
    return output_path


# --- メイン ---
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="軽技Web 受注工事一覧 → project_master.xlsx 自動同期")
    ap.add_argument("--inspect", action="store_true", help="UI識別子を表示して終了（現地調査用）")
    ap.add_argument("--no-launch", action="store_true", help="軽技Web が既に起動済みの場合")
    ap.add_argument("--dry-run", action="store_true", help="軽技操作をスキップし、--input で変換のみ実行")
    ap.add_argument("--input", type=str, default=None, help="--dry-run 時の入力 xlsx パス")
    args = ap.parse_args(argv)

    if args.dry_run:
        if not args.input:
            ap.error("--dry-run には --input <xlsx> が必要です")
        export_path = Path(args.input)
        if not export_path.exists():
            ap.error(f"ファイルが見つかりません: {export_path}")
        build_project_master(export_path)
        return 0

    # VPN チェック
    check_vpn()

    # 軽技Web 起動・接続
    app = launch_and_connect(no_launch=args.no_launch)

    # 調査モード
    if args.inspect:
        inspect_mode(app)
        return 0

    # 受注工事一覧 に遷移
    list_win = navigate_to_juchu_list(app)

    # エクスポート
    export_path = export_to_xlsx(list_win)

    # project_master 生成
    build_project_master(export_path)

    print("\n✅ sync_project_master 完了")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
