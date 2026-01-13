# -*- coding: utf-8 -*-
"""
Windows資格情報マネージャーからの認証情報取得

Usage:
    from common.credential_manager import get_credential

    user, password = get_credential("RK10_RakurakuSeisan")
"""
import ctypes
from ctypes import wintypes
from typing import Tuple, Optional

# Windows資格情報タイプ
CRED_TYPE_GENERIC = 1


class FILETIME(ctypes.Structure):
    """Windows FILETIME構造体"""
    _fields_ = [
        ('dwLowDateTime', wintypes.DWORD),
        ('dwHighDateTime', wintypes.DWORD)
    ]


class CREDENTIAL(ctypes.Structure):
    """Windows CREDENTIAL構造体"""
    _fields_ = [
        ('Flags', wintypes.DWORD),
        ('Type', wintypes.DWORD),
        ('TargetName', wintypes.LPWSTR),
        ('Comment', wintypes.LPWSTR),
        ('LastWritten', FILETIME),
        ('CredentialBlobSize', wintypes.DWORD),
        ('CredentialBlob', ctypes.POINTER(ctypes.c_byte)),
        ('Persist', wintypes.DWORD),
        ('AttributeCount', wintypes.DWORD),
        ('Attributes', ctypes.c_void_p),
        ('TargetAlias', wintypes.LPWSTR),
        ('UserName', wintypes.LPWSTR),
    ]


def _read_credential_raw(target_name: str) -> Optional[Tuple[str, str]]:
    """Windows資格情報を読み取る（内部関数）

    Args:
        target_name: 資格情報のターゲット名

    Returns:
        (username, password) のタプル、または None
    """
    advapi32 = ctypes.windll.advapi32
    advapi32.CredReadW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
        ctypes.POINTER(ctypes.POINTER(CREDENTIAL))
    ]
    advapi32.CredReadW.restype = wintypes.BOOL
    advapi32.CredFree.argtypes = [ctypes.c_void_p]

    cred_ptr = ctypes.POINTER(CREDENTIAL)()

    if advapi32.CredReadW(target_name, CRED_TYPE_GENERIC, 0, ctypes.byref(cred_ptr)):
        try:
            cred = cred_ptr.contents
            username = cred.UserName or ""

            if cred.CredentialBlobSize > 0:
                raw = bytes(ctypes.string_at(cred.CredentialBlob, cred.CredentialBlobSize))
                password = raw.decode('utf-16-le').rstrip('\x00')
            else:
                password = ""

            return (username, password)
        finally:
            advapi32.CredFree(cred_ptr)

    return None


def get_credential(target_name: str) -> Tuple[str, str]:
    """Windows資格情報マネージャーから認証情報を取得

    Args:
        target_name: 資格情報のターゲット名
                    例: "RK10_RakurakuSeisan"

    Returns:
        (username, password) のタプル

    Raises:
        ValueError: 資格情報が見つからない場合
    """
    result = _read_credential_raw(target_name)

    if result is None:
        raise ValueError(
            f"Windows資格情報が見つかりません: {target_name}\n"
            f"以下の手順で登録してください:\n"
            f"  1. コントロールパネル → 資格情報マネージャー\n"
            f"  2. Windows資格情報 → 汎用資格情報の追加\n"
            f"  3. インターネットまたはネットワークのアドレス: {target_name}\n"
            f"  4. ユーザー名とパスワードを入力"
        )

    return result


def get_credential_value(target_name: str) -> str:
    """資格情報のパスワード部分のみを取得

    ユーザー名が不要な場合（単一の値を保存している場合）に使用

    Args:
        target_name: 資格情報のターゲット名

    Returns:
        パスワード（または保存された値）
    """
    result = _read_credential_raw(target_name)

    if result is None:
        raise ValueError(f"Windows資格情報が見つかりません: {target_name}")

    username, password = result

    # パスワードがある場合はパスワードを、なければユーザー名を返す
    return password if password else username


if __name__ == "__main__":
    # テスト実行
    import sys
    sys.stdout.reconfigure(encoding='utf-8')

    test_targets = [
        "RK10_RakurakuSeisan",
        "ログインID　楽楽精算",
        "パスワード　楽楽精算",
    ]

    for target in test_targets:
        try:
            result = _read_credential_raw(target)
            if result:
                username, password = result
                masked_pw = password[:2] + "***" if len(password) > 2 else "***"
                print(f"OK {target}: user={username}, pass={masked_pw}")
            else:
                print(f"NG {target}: 未登録")
        except Exception as e:
            print(f"NG {target}: エラー - {e}")
