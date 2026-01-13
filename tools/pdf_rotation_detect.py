# -*- coding: utf-8 -*-
"""
PDF回転方向検出モジュール（強化版）

スキャンPDFの正しい向きを検出する
- 4方向（0/90/180/270度）の全自動判定
- 複数の判定基準を組み合わせたスコアリング
  - 水平エッジ比率（テキスト行検出）
  - 上部テキスト密度（レシートヘッダー検出）
  - 行連続性分析（水平プロジェクション）
  - Hough変換による線分検出

Updated: 2026-01-14 - Document AI廃止対応
"""
import sys
from pathlib import Path
from typing import Tuple, List, Dict
import tempfile

sys.path.insert(0, str(Path(__file__).parent))

import fitz
import cv2
import numpy as np
from PIL import Image

from common.logger import get_logger


class PDFRotationDetector:
    """PDF回転方向検出クラス（強化版）"""

    # 回転スコアの最小差分（これ以下は回転しない）
    ROTATION_MIN_DIFF = 0.1

    def __init__(self, dpi: int = 150):
        self.dpi = dpi
        self.logger = get_logger()

    def pdf_to_image(self, pdf_path: Path) -> np.ndarray:
        """PDFを画像に変換"""
        doc = fitz.open(str(pdf_path))
        page = doc[0]

        zoom = self.dpi / 72
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)

        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)

        if pix.n == 4:
            img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)
        elif pix.n == 1:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)

        doc.close()
        return img

    def rotate_image(self, img: np.ndarray, angle: int) -> np.ndarray:
        """
        画像を回転（90度単位）

        Args:
            img: 入力画像
            angle: 回転角度（90, 180, 270）

        Returns:
            回転後の画像
        """
        if angle == 90:
            return cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
        elif angle == 180:
            return cv2.rotate(img, cv2.ROTATE_180)
        elif angle == 270:
            return cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
        return img

    def detect_text_score(self, img: np.ndarray) -> float:
        """
        テキストの「読みやすさ」スコアを計算（基本版）

        正しい向きの場合:
        - 水平方向のエッジが多い（テキスト行）
        - 上部にテキストが集中（レシートの場合）

        Returns:
            スコア（高いほど正しい向き）
        """
        # グレースケール
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        else:
            gray = img.copy()

        h, w = gray.shape

        # 1. 水平エッジの検出（テキスト行は水平エッジが多い）
        # Sobelフィルタで水平方向のエッジを検出
        sobel_h = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        sobel_v = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)

        h_score = np.sum(np.abs(sobel_h))
        v_score = np.sum(np.abs(sobel_v))

        # 水平エッジが多いほど良い
        edge_ratio = h_score / (v_score + 1)

        # 2. 上部のテキスト密度（レシートは上部に店名等がある）
        # 画像を上下に分割して、上部のテキスト密度をチェック
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        top_half = binary[:h//2, :]
        bottom_half = binary[h//2:, :]

        top_density = np.sum(top_half) / top_half.size
        bottom_density = np.sum(bottom_half) / bottom_half.size

        # 上部にテキストが多いほど良い（軽い重み付け）
        position_score = top_density / (bottom_density + 0.01)

        # 3. テキスト領域の連続性（正しい向きは横方向に連続）
        # 水平方向のプロジェクション（行ごとのピクセル数）
        h_projection = np.sum(binary, axis=1)
        # 垂直方向のプロジェクション（列ごとのピクセル数）
        v_projection = np.sum(binary, axis=0)

        # 水平プロジェクションの分散が高いほど、行が明確
        h_var = np.var(h_projection)
        v_var = np.var(v_projection)

        projection_score = h_var / (v_var + 1)

        # 総合スコア
        total_score = edge_ratio * 0.4 + position_score * 0.2 + projection_score * 0.4

        return total_score

    def detect_text_score_enhanced(self, img: np.ndarray) -> Dict[str, float]:
        """
        テキストの「読みやすさ」スコアを計算（強化版）

        複数の判定基準を個別に返す:
        - edge_ratio: 水平エッジ比率
        - position_score: 上部テキスト密度
        - projection_score: 行連続性
        - hough_score: Hough変換による水平線検出

        Returns:
            各スコアの辞書
        """
        # グレースケール
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        else:
            gray = img.copy()

        h, w = gray.shape
        scores = {}

        # 1. 水平エッジ比率
        sobel_h = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        sobel_v = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        h_score = np.sum(np.abs(sobel_h))
        v_score = np.sum(np.abs(sobel_v))
        scores['edge_ratio'] = h_score / (v_score + 1)

        # 2. 上部テキスト密度
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        top_half = binary[:h//2, :]
        bottom_half = binary[h//2:, :]
        top_density = np.sum(top_half) / top_half.size
        bottom_density = np.sum(bottom_half) / bottom_half.size
        scores['position_score'] = top_density / (bottom_density + 0.01)

        # 3. 行連続性（水平プロジェクション）
        h_projection = np.sum(binary, axis=1)
        v_projection = np.sum(binary, axis=0)
        h_var = np.var(h_projection)
        v_var = np.var(v_projection)
        scores['projection_score'] = h_var / (v_var + 1)

        # 4. Hough変換による水平線検出（強化版）
        edges = cv2.Canny(gray, 50, 150)
        lines = cv2.HoughLines(edges, 1, np.pi / 180, 100)

        horizontal_count = 0
        vertical_count = 0
        if lines is not None:
            for line in lines[:50]:  # 最大50本
                theta = line[0][1]
                angle_deg = np.degrees(theta)
                # 水平線（0度または180度付近）
                if abs(angle_deg - 90) < 15 or abs(angle_deg - 270) < 15:
                    horizontal_count += 1
                # 垂直線（90度付近）
                elif abs(angle_deg) < 15 or abs(angle_deg - 180) < 15:
                    vertical_count += 1

        scores['hough_score'] = horizontal_count / (vertical_count + 1)

        # 総合スコア
        scores['total'] = (
            scores['edge_ratio'] * 0.3 +
            scores['position_score'] * 0.2 +
            scores['projection_score'] * 0.3 +
            scores['hough_score'] * 0.2
        )

        return scores

    def detect_best_rotation(self, pdf_path: Path, use_enhanced: bool = True) -> int:
        """
        最適な回転角度を検出

        4方向（0, 90, 180, 270度）でスコアを計算し、
        最も読みやすい向きを選択

        Args:
            pdf_path: 入力PDF
            use_enhanced: 強化版スコアリングを使用するか

        Returns:
            最適な回転角度（0, 90, 180, 270）
        """
        img = self.pdf_to_image(pdf_path)

        rotations = [0, 90, 180, 270]
        scores = []

        for angle in rotations:
            if angle == 0:
                rotated = img
            else:
                rotated = self.rotate_image(img, angle)

            if use_enhanced:
                score_dict = self.detect_text_score_enhanced(rotated)
                score = score_dict['total']
            else:
                score = self.detect_text_score(rotated)

            scores.append(score)
            self.logger.debug(f"回転 {angle}度: スコア {score:.4f}")

        best_idx = np.argmax(scores)
        best_angle = rotations[best_idx]

        # スコア差が小さい場合は回転しない
        max_score = max(scores)
        current_score = scores[0]  # 0度のスコア
        if max_score - current_score < self.ROTATION_MIN_DIFF:
            self.logger.info(
                f"回転検出: スコア差 {max_score - current_score:.3f} < {self.ROTATION_MIN_DIFF} → 回転なし"
            )
            return 0

        self.logger.info(
            f"回転検出: 0度={scores[0]:.2f}, 90度={scores[1]:.2f}, "
            f"180度={scores[2]:.2f}, 270度={scores[3]:.2f} → {best_angle}度を選択"
        )

        return best_angle

    def detect_best_rotation_with_details(self, pdf_path: Path) -> Tuple[int, Dict]:
        """
        最適な回転角度を検出（詳細情報付き）

        Returns:
            (最適な回転角度, 詳細情報の辞書)
        """
        img = self.pdf_to_image(pdf_path)

        rotations = [0, 90, 180, 270]
        all_scores = {}

        for angle in rotations:
            if angle == 0:
                rotated = img
            else:
                rotated = self.rotate_image(img, angle)

            score_dict = self.detect_text_score_enhanced(rotated)
            all_scores[angle] = score_dict

        # 総合スコアで最良を選択
        best_angle = max(rotations, key=lambda a: all_scores[a]['total'])

        details = {
            'scores': all_scores,
            'best_angle': best_angle,
            'confidence': all_scores[best_angle]['total'] - all_scores[0]['total']
        }

        return best_angle, details

    def detect_orientation_for_landscape(self, pdf_path: Path) -> int:
        """
        横長PDFの正しい向きを検出

        横長PDFを縦長にする場合、90度か270度の2択
        どちらが正しいかをテキスト検出で判定

        Returns:
            回転角度（90 or 270）
        """
        img = self.pdf_to_image(pdf_path)

        # 90度と270度のスコアを比較
        img_90 = self.rotate_image(img, 90)
        img_270 = self.rotate_image(img, 270)

        score_90 = self.detect_text_score(img_90)
        score_270 = self.detect_text_score(img_270)

        best_angle = 90 if score_90 > score_270 else 270

        self.logger.info(
            f"横長PDF向き検出: 90度={score_90:.2f}, 270度={score_270:.2f} → {best_angle}度"
        )

        return best_angle


def test_rotation_detection():
    """テスト"""
    from common.logger import setup_logger
    setup_logger("rotation_detect_test")

    sample_dir = Path(r"C:\ProgramData\RK10\Robots\44PDF一般経費楽楽精算申請\docs\sample PDF")

    detector = PDFRotationDetector(dpi=150)

    test_files = [
        "(株)ニトリ.pdf",
        "東京インテリア家具.pdf",
        "20260108192522.pdf",
        "0109セリア(百均)買物.pdf",
    ]

    print("=" * 80)
    print("PDF回転方向検出テスト")
    print("=" * 80)

    for fname in test_files:
        pdf_path = sample_dir / fname
        if not pdf_path.exists():
            continue

        print(f"\n--- {fname} ---")

        # PDFのサイズ確認
        doc = fitz.open(str(pdf_path))
        page = doc[0]
        is_landscape = page.rect.width > page.rect.height
        doc.close()

        print(f"  横長: {is_landscape}")

        if is_landscape:
            # 横長の場合は90度か270度
            best = detector.detect_orientation_for_landscape(pdf_path)
            print(f"  推奨回転: {best}度")
        else:
            # 縦長の場合は全方向チェック
            best = detector.detect_best_rotation(pdf_path)
            print(f"  推奨回転: {best}度")


if __name__ == "__main__":
    test_rotation_detection()
