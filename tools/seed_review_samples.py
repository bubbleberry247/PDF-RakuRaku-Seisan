"""
review_helper テスト用サンプル20件を準備するスクリプト。
samples/bench_v4 の実際の請求書PDFを review_required へコピーし、
manifest にレコードを追記する。

カテゴリ内訳: fixed×7, variable×7, gray×3, regression×3
"""
import hashlib
import json
import shutil
import sys
from datetime import date
from pathlib import Path
from unicodedata import normalize as unic_normalize

# Windows cp932 端末で ✖ 等が UnicodeEncodeError になるのを防ぐ
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SCENARIO_DIR  = Path(__file__).resolve().parent.parent
SAMPLES_DIR   = SCENARIO_DIR / "samples" / "bench_v4"
SAVE_DIR      = SCENARIO_DIR / "output" / "請求書【現場】"

# payment_month を動的計算（今月 → 翌月末支払い）
def _payment_month() -> str:
    today = date.today()
    y, m = today.year, today.month
    py, pm = (y + 1, 1) if m == 12 else (y, m + 1)
    return f"{y}.{m}月分({py}.{pm}末支払い)"

PAYMENT_MONTH = _payment_month()
REVIEW_DIR    = SAVE_DIR / PAYMENT_MONTH / "要確認" / "review_required"
MANIFEST      = SCENARIO_DIR / "artifacts" / "processed_attachments_manifest.jsonl"

# ---- サンプル20件（fixed×7, variable×7, gray×3, regression×3） ----
SAMPLES = [
    # === fixed ===
    {
        "src": "真栄産業_20251225_65000_家族葬の結家西尾市一色町味浜改装工事.pdf",
        "entry_id": "SEED_F001",
        "sender": "maei@maei-sangyo.co.jp",
        "subject": "【請求書】家族葬の結家西尾市一色町味浜改装工事 2025年12月分",
        "review_reason": "low_confidence",
    },
    {
        "src": "パルカンパニー渡辺_20251025_【イズモ葬祭土橋】常用.pdf",
        "entry_id": "SEED_F002",
        "sender": "watanabe@palcompany.jp",
        "subject": "イズモ葬祭土橋店新築工事 常用請求書 10月分",
        "review_reason": "low_confidence",
    },
    {
        "src": "(有)竹下建築_20251125_24,433,337_津田様邸共同住宅新築工事　請求書.pdf",
        "entry_id": "SEED_F003",
        "sender": "takeshita@takeshita-kensetsu.co.jp",
        "subject": "津田様邸共同住宅新築工事 11月分請求書",
        "review_reason": "no_project_match",
    },
    {
        "src": "㈱モノタロウ_20251225_102283_モビテック.pdf",
        "entry_id": "SEED_F004",
        "sender": "order@monotaro.com",
        "subject": "【MonotaRO】請求書 2025年12月",
        "review_reason": "low_confidence",
    },
    {
        "src": "㈱タツノ開発_20251025_89050【松のやマイカリー食堂】.pdf",
        "entry_id": "SEED_F005",
        "sender": "info@tatsuno-kaihatsu.co.jp",
        "subject": "松のや・マイカリー食堂R安城店新築工事 請求書",
        "review_reason": "low_confidence",
    },
    {
        "src": "㈱セーファ_20250825_6930000イズモ葬祭豊田　新築工事.pdf",
        "entry_id": "SEED_F006",
        "sender": "keiri@sefa.co.jp",
        "subject": "イズモ葬祭豊田店新築工事 8月分請求書",
        "review_reason": "low_confidence",
    },
    {
        "src": "ワーク_20251225_660,000【富田様共同住宅】.pdf",
        "entry_id": "SEED_F007",
        "sender": "work@work-corp.jp",
        "subject": "冨田様邸共同住宅新築工事 12月分常用請求",
        "review_reason": "low_confidence",
    },
    # === variable ===
    {
        "src": "ティラド名古屋製作所テント張替え.pdf",
        "entry_id": "SEED_V001",
        "sender": "info@tirado-nagoya.co.jp",
        "subject": "テント張替え工事 請求書",
        "review_reason": "no_sender_rule",
    },
    {
        "src": "✖北恵㈱＿２０２６年1月26日＿539,000円_富田様邸共同住宅新築工事.pdf",
        "entry_id": "SEED_V002",
        "sender": "kitae@kitae.co.jp",
        "subject": "冨田様邸共同住宅新築工事 請求書 2026.1",
        "review_reason": "low_confidence",
    },
    {
        "src": "平林シート㈱_20250925_145,000_ティラド東浦トラックヤード通路正面文字.pdf",
        "entry_id": "SEED_V003",
        "sender": "hirabayashi@hirabayashi-sheet.co.jp",
        "subject": "ティラド東浦 トラックヤード通路 文字施工 請求書",
        "review_reason": "no_project_match",
    },
    {
        "src": "ティーエス・アクト㈱_20250825_220000.pdf",
        "entry_id": "SEED_V004",
        "sender": "billing@ts-act.co.jp",
        "subject": "ご請求書 2025年8月分",
        "review_reason": "no_sender_rule",
    },
    {
        "src": "✖三晃金属工業_20250725_180,000【相羽製作所】.pdf",
        "entry_id": "SEED_V005",
        "sender": "sanko@sanko-metal.co.jp",
        "subject": "相羽製作所新築工事 請求書 2025.7",
        "review_reason": "low_confidence",
    },
    {
        "src": "(岡田さんへ10.3)中部ﾎｰﾑｻｰﾋﾞｽ㈱_20250925_31,850_0072若濱様邸.pdf",
        "entry_id": "SEED_V006",
        "sender": "chubu@chubu-hs.co.jp",
        "subject": "若濱様邸 請求書 9月分",
        "review_reason": "no_project_match",
    },
    {
        "src": "samtec2026_1_25　21,440,375【愛三豊田.浅田LC】.pdf",
        "entry_id": "SEED_V007",
        "sender": "samtec2016@outlook.jp",
        "subject": "愛三工業様豊田・浅田レディースクリニック 2026年1月請求",
        "review_reason": "low_confidence",
    },
    # === gray ===
    {
        "src": "不地弘測量設計株式会社_20251220_1200000（モビテックテクニカルセンター）.pdf",
        "entry_id": "SEED_G001",
        "sender": "fuchihiro@fuchihiro-survey.co.jp",
        "subject": "モビテックシン・テクニカルセンター新築工事 測量費請求書",
        "review_reason": "low_confidence",
    },
    {
        "src": "samtec　2025₋12₋25　12,964,050【愛三工業豊田　陽だまりの森ｸﾘﾆｯｸ　浅田LC】.pdf",
        "entry_id": "SEED_G002",
        "sender": "samtec2016@outlook.jp",
        "subject": "愛三工業豊田・陽だまりの森クリニック・浅田LC 12月請求",
        "review_reason": "low_confidence",
    },
    {
        "src": "(株)オーテクニック_20260125_240,000_モビテック・シン・テクニカルセンター　請求書(常傭)改定2025.10.pdf",
        "entry_id": "SEED_G003",
        "sender": "fukuhara@o-technique.co.jp",
        "subject": "モビテックシンテクニカルセンター新築工事 常傭請求書",
        "review_reason": "low_confidence",
    },
    # === regression ===
    {
        "src": "アシタカ総建株式会社_20260225_1,090,000_株式会社モビテック シン･テクニカルセンター新築工事(常傭).pdf",
        "entry_id": "SEED_R001",
        "sender": "info@ashitaka-soken.co.jp",
        "subject": "モビテック シン・テクニカルセンター新築工事 常傭 2026.2",
        "review_reason": "low_confidence",
    },
    {
        "src": "クレーンタル野田_20260125_769,500【（仮称）中村区中島町三丁目計画新築工事】.pdf",
        "entry_id": "SEED_R002",
        "sender": "noda@crane-tal.co.jp",
        "subject": "（仮称）中村区中島町三丁目計画新築工事 請求書 2026.1",
        "review_reason": "no_project_match",
    },
    {
        "src": "髙田工業所_20260125_1890000_（仮称）中村区中島町三丁目計画新築工事.pdf",
        "entry_id": "SEED_R003",
        "sender": "takada@takada-kogyo.co.jp",
        "subject": "（仮称）中村区中島町三丁目計画新築工事 請求書",
        "review_reason": "no_project_match",
    },
]


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def manifest_key(entry_id: str, att_name: str, sha256: str) -> str:
    raw = "\n".join([entry_id, unic_normalize("NFKC", att_name), sha256])
    return hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()


def main():
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)

    print(f"payment_month : {PAYMENT_MONTH}")
    print(f"review_dir    : {REVIEW_DIR}")
    print()

    # 既存サンプル（SEED_ 付きのもの）をクリア
    for pdf in REVIEW_DIR.glob("*.pdf"):
        pdf.unlink()
        print(f"  削除: {pdf.name}")
    state_file = SAVE_DIR / PAYMENT_MONTH / "要確認" / "_review_state.json"
    if state_file.exists():
        state_file.unlink()
        print("  state リセット")

    records = []
    skipped = []
    for s in SAMPLES:
        src = SAMPLES_DIR / s["src"]
        if not src.exists():
            skipped.append(s["src"])
            continue

        dest = REVIEW_DIR / src.name
        shutil.copy2(str(src), str(dest))
        sha = sha256_of(dest)
        att_name = src.name
        key = manifest_key(s["entry_id"], att_name, sha)

        rec = {
            "key": key,
            "message_entry_id": s["entry_id"],
            "attachment_name": att_name,
            "sha256": sha,
            "saved_path": str(dest),
            "routing_state": "review_required",
            "sender": s["sender"],
            "subject": s["subject"],
            "review_reason": s["review_reason"],
            "resolved_by": None,
            "resolved_at": None,
        }
        records.append(rec)
        print(f"  OK: {att_name[:60]}  (key={key[:12]}...)")

    with MANIFEST.open("a", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"\n{len(records)} 件配置完了（スキップ {len(skipped)} 件）")
    if skipped:
        for s in skipped:
            print(f"  SKIP: {s}")
    print(f"\n次: python tools\\start_review_helper.py")


if __name__ == "__main__":
    main()
