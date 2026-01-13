# -*- coding: utf-8 -*-
"""
PDF回転補正強化テスト

問題点:
1. 横長PDFが正しく90度回転されていない可能性
2. 180度回転（上下逆さま）の検出がない
3. 傾き補正（deskew）がない

改善策:
A) 横長PDF/画像の90度回転（既存）
B) テキスト方向検出による回転補正
C) OpenCVによる傾き検出・補正（deskew）
D) OCRマルチパス（0/90/180/270度で試行）
"""
import os
import sys
from pathlib import Path
import tempfile
import shutil

sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding='utf-8')

import fitz
import cv2
import numpy as np
from PIL import Image

# ログ設定
from common.logger import setup_logger, get_logger
setup_logger("rotation_test")
logger = get_logger()


def pdf_to_image(pdf_path: Path, dpi: int = 150) -> np.ndarray:
    """PDFを画像に変換"""
    doc = fitz.open(str(pdf_path))
    page = doc[0]

    # 高解像度でレンダリング
    zoom = dpi / 72
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)

    # numpy配列に変換
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)

    # RGBに変換（アルファチャンネルがある場合は除去）
    if pix.n == 4:
        img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)

    doc.close()
    return img


def detect_text_orientation(img: np.ndarray) -> int:
    """
    テキストの向きを検出（0, 90, 180, 270度）

    Hough変換で主要な線の角度を検出し、テキスト行の方向を推定
    """
    # グレースケール変換
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    else:
        gray = img.copy()

    # エッジ検出
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)

    # Hough変換で直線検出
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=100,
                            minLineLength=50, maxLineGap=10)

    if lines is None:
        return 0

    # 各線の角度を計算
    angles = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        angle = np.arctan2(y2 - y1, x2 - x1) * 180 / np.pi
        angles.append(angle)

    if not angles:
        return 0

    # 角度のヒストグラムを作成して主要な角度を特定
    # 水平線（0度付近）が多ければ正常、垂直線（90度付近）が多ければ90度回転
    h_count = sum(1 for a in angles if abs(a) < 15 or abs(a) > 165)
    v_count = sum(1 for a in angles if 75 < abs(a) < 105)

    if v_count > h_count * 1.5:
        return 90  # 90度回転が必要

    return 0


def detect_skew_angle(img: np.ndarray) -> float:
    """
    傾き角度を検出（-45〜+45度）
    """
    # グレースケール変換
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    else:
        gray = img.copy()

    # 二値化
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # 輪郭を使って最小外接矩形を求める
    coords = np.column_stack(np.where(binary > 0))
    if len(coords) < 100:
        return 0.0

    # 主成分分析で傾きを検出
    mean = np.mean(coords, axis=0)
    centered = coords - mean
    cov = np.cov(centered.T)
    eigenvalues, eigenvectors = np.linalg.eig(cov)

    # 最大固有値に対応する固有ベクトルの角度
    idx = np.argmax(eigenvalues)
    angle = np.arctan2(eigenvectors[1, idx], eigenvectors[0, idx]) * 180 / np.pi

    # -45〜45度の範囲に正規化
    while angle > 45:
        angle -= 90
    while angle < -45:
        angle += 90

    return angle


def deskew_image(img: np.ndarray, angle: float) -> np.ndarray:
    """
    画像の傾きを補正
    """
    if abs(angle) < 0.5:  # 0.5度未満は補正しない
        return img

    h, w = img.shape[:2]
    center = (w // 2, h // 2)

    # 回転行列
    M = cv2.getRotationMatrix2D(center, angle, 1.0)

    # 回転後のサイズを計算
    cos = np.abs(M[0, 0])
    sin = np.abs(M[0, 1])
    new_w = int(h * sin + w * cos)
    new_h = int(h * cos + w * sin)

    # 回転行列の平行移動成分を調整
    M[0, 2] += (new_w - w) / 2
    M[1, 2] += (new_h - h) / 2

    # 回転実行
    rotated = cv2.warpAffine(img, M, (new_w, new_h),
                             flags=cv2.INTER_CUBIC,
                             borderMode=cv2.BORDER_REPLICATE)
    return rotated


def rotate_pdf(pdf_path: Path, rotation: int, output_path: Path) -> Path:
    """
    PDFを指定角度で回転

    Args:
        pdf_path: 入力PDF
        rotation: 回転角度（90, 180, 270）
        output_path: 出力パス

    Returns:
        回転後のPDFパス
    """
    doc = fitz.open(str(pdf_path))

    for page in doc:
        page.set_rotation(rotation)

    doc.save(str(output_path))
    doc.close()

    return output_path


def enhanced_rotation_correction(pdf_path: Path, output_dir: Path = None) -> Path:
    """
    強化版回転補正

    1. PDFの既存回転を正規化
    2. 横長検出→90度回転
    3. テキスト方向検出
    4. 傾き補正（deskew）
    """
    if output_dir is None:
        output_dir = pdf_path.parent

    doc = fitz.open(str(pdf_path))
    page = doc[0]

    logger.info(f"処理開始: {pdf_path.name}")
    logger.info(f"  ページサイズ: {page.rect.width:.0f}x{page.rect.height:.0f}")
    logger.info(f"  既存回転: {page.rotation}度")

    needs_rotation = 0

    # 1. 横長チェック
    if page.rect.width > page.rect.height:
        needs_rotation = 90
        logger.info("  → 横長ページ検出: 90度回転")

    # 2. 画像のアスペクト比チェック
    images = page.get_images()
    if images and needs_rotation == 0:
        xref = images[0][0]
        base_image = doc.extract_image(xref)
        img_w, img_h = base_image['width'], base_image['height']
        if img_w > img_h and page.rect.width < page.rect.height:
            needs_rotation = 90
            logger.info(f"  → 横長画像検出 ({img_w}x{img_h}): 90度回転")

    doc.close()

    # 3. 回転が必要な場合
    if needs_rotation > 0:
        rotated_path = output_dir / f"_rot{needs_rotation}_{pdf_path.name}"
        rotate_pdf(pdf_path, needs_rotation, rotated_path)
        logger.info(f"  → 回転済みPDF: {rotated_path.name}")
        return rotated_path

    return pdf_path


def test_sample_pdfs():
    """サンプルPDFで回転補正をテスト"""
    sample_dir = Path(r"C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\docs\sample PDF")
    output_dir = Path(r"C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\data\rotation_test")
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("PDF回転補正強化テスト")
    print("=" * 80)

    # 問題がありそうなPDFを優先テスト
    priority_pdfs = [
        "(株)ニトリ.pdf",  # 横長ページ・横長画像
        "20260108192522.pdf",  # 横長
        "東京インテリア家具.pdf",  # 横長
        "doc06562520260108152210.pdf",  # rotation=270
        "領収証2025.12.26.pdf",  # rotation=90
    ]

    for pdf_name in priority_pdfs:
        pdf_path = sample_dir / pdf_name
        if not pdf_path.exists():
            print(f"\n[SKIP] {pdf_name} - ファイルなし")
            continue

        print(f"\n--- {pdf_name} ---")

        try:
            # 強化版回転補正
            corrected = enhanced_rotation_correction(pdf_path, output_dir)

            # 補正後の画像を確認
            img = pdf_to_image(corrected)
            print(f"  画像サイズ: {img.shape[1]}x{img.shape[0]}")

            # 傾き検出
            skew = detect_skew_angle(img)
            print(f"  検出傾き: {skew:.2f}度")

            if abs(skew) > 1.0:
                print(f"  → 傾き補正推奨")

        except Exception as e:
            print(f"  [ERROR] {e}")

    print("\n" + "=" * 80)
    print(f"出力先: {output_dir}")


if __name__ == "__main__":
    test_sample_pdfs()
