# -*- coding: utf-8 -*-
"""
Evidence Ledger — 構造化証跡台帳

全パイプライン（OCR/RPA/スクレイパー）の実行結果を run_id で統一管理。
Gate 4/5（ソース明記・矛盾チェック）の自動化基盤として機能する。

Usage:
    from tools.common.evidence_ledger import EvidenceLedger

    ledger = EvidenceLedger("evidence")

    with ledger.start_run("ocr", scenario="scenario-44") as run:
        run.add_input(pdf_path)
        run.add_metric("pages", 5)
        result = ocr_pipeline(pdf_path)
        run.add_output(result.output_path)
        run.add_metric("fields_extracted", len(result.fields))
        run.add_validation("amount_present", result.amount is not None)

CLI:
    python -m tools.common.evidence_ledger query --pipeline ocr --days 7
    python -m tools.common.evidence_ledger latest --pipeline rpa_s55
    python -m tools.common.evidence_ledger summary --days 30
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import time
import traceback
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

@dataclass
class EvidenceRecord:
    """単一実行の構造化証跡レコード。"""

    # Identity
    run_id: str
    timestamp: str          # ISO 8601
    pipeline: str           # "ocr", "rpa_s55", "rpa_s57", "scraper", etc.
    scenario: str | None    # "scenario-55", "scenario-44", etc.

    # Inputs
    input_files: list[str] = field(default_factory=list)
    input_params: dict[str, Any] = field(default_factory=dict)

    # Outputs
    output_files: list[str] = field(default_factory=list)
    output_summary: dict[str, Any] = field(default_factory=dict)

    # Quality
    status: str = "success"                         # "success", "partial", "error"
    errors: list[dict[str, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    # Validation
    validations: list[dict[str, Any]] = field(default_factory=list)
    reconciliation: dict[str, Any] | None = None

    # Traceability
    prompt_version: str | None = None
    model_version: str | None = None
    duration_seconds: float = 0.0

    # Metadata
    env: str = "LOCAL"
    operator: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "EvidenceRecord":
        """辞書からEvidenceRecordを復元する（不明フィールドは無視）。"""
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)

    def to_dict(self) -> dict:
        """シリアライズ可能な辞書に変換する。"""
        return asdict(self)


# ---------------------------------------------------------------------------
# Run Context
# ---------------------------------------------------------------------------

class RunContext:
    """with文でrunを記録するコンテキストマネージャー。"""

    def __init__(
        self,
        ledger: "EvidenceLedger",
        run_id: str,
        pipeline: str,
        scenario: str | None,
        env: str,
        operator: str,
        input_params: dict[str, Any],
        prompt_version: str | None,
        model_version: str | None,
    ) -> None:
        self._ledger = ledger
        self._record = EvidenceRecord(
            run_id=run_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            pipeline=pipeline,
            scenario=scenario,
            env=env,
            operator=operator,
            input_params=input_params,
            prompt_version=prompt_version,
            model_version=model_version,
        )
        self._start_time: float = 0.0

    # --- Fluent setters ---

    def add_input(self, file_path: str) -> "RunContext":
        """入力ファイルパスを追加する。"""
        self._record.input_files.append(str(file_path))
        return self

    def add_output(self, file_path: str) -> "RunContext":
        """出力ファイルパスを追加する。"""
        self._record.output_files.append(str(file_path))
        return self

    def add_metric(self, key: str, value: Any) -> "RunContext":
        """output_summary にキー/値を追加する。"""
        self._record.output_summary[key] = value
        return self

    def add_validation(self, check: str, result: bool, detail: str = "") -> "RunContext":
        """バリデーション結果を追加する。"""
        self._record.validations.append({
            "check": check,
            "result": result,
            "detail": detail,
        })
        return self

    def add_warning(self, message: str) -> "RunContext":
        """非致命的な警告を追加する。"""
        self._record.warnings.append(message)
        return self

    def add_error(
        self,
        error_type: str,
        message: str,
        tb: str = "",
    ) -> "RunContext":
        """エラー情報を追加する（status は自動で "error" になる）。"""
        self._record.errors.append({
            "type": error_type,
            "message": message,
            "traceback": tb,
        })
        self._record.status = "error"
        return self

    def set_reconciliation(self, result: dict) -> "RunContext":
        """照合結果（reconcile.py 出力）をセットする。"""
        self._record.reconciliation = result
        return self

    def set_status(self, status: str) -> "RunContext":
        """ステータスを明示的に設定する（'success'/'partial'/'error'）。"""
        assert status in ("success", "partial", "error"), f"Invalid status: {status}"
        self._record.status = status
        return self

    # --- Context protocol ---

    def __enter__(self) -> "RunContext":
        self._start_time = time.monotonic()
        return self

    def __exit__(
        self,
        exc_type: type | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool:
        self._record.duration_seconds = round(time.monotonic() - self._start_time, 3)

        # 未キャッチ例外 → エラーとして記録
        if exc_type is not None:
            self.add_error(
                error_type=exc_type.__name__,
                message=str(exc_val),
                tb="".join(traceback.format_exception(exc_type, exc_val, exc_tb)),
            )

        # errors があれば status を "error" に上書き（set_status で明示しない限り）
        if self._record.errors and self._record.status not in ("partial",):
            self._record.status = "error"

        self._ledger.save(self._record)

        # 例外は再 raise させる（suppress しない）
        return False

    @property
    def run_id(self) -> str:
        return self._record.run_id

    @property
    def record(self) -> EvidenceRecord:
        return self._record


# ---------------------------------------------------------------------------
# Ledger
# ---------------------------------------------------------------------------

class EvidenceLedger:
    """Evidence Ledger の主クラス。"""

    def __init__(self, base_dir: str = "evidence") -> None:
        self._base = Path(base_dir)
        self._base.mkdir(parents=True, exist_ok=True)

    # --- run_id generation ---

    def generate_run_id(self, pipeline: str) -> str:
        """連番ベースの run_id を生成する。

        形式: {YYYYMMDD}_{pipeline}_{seq:03d}
        例: 20260406_ocr_001, 20260406_rpa_s55_002
        """
        date_str = datetime.now().strftime("%Y%m%d")
        safe_pipeline = pipeline.replace("-", "_").replace(" ", "_")
        prefix = f"{date_str}_{safe_pipeline}_"

        # 既存ファイルから今日の連番を算出
        month_dir = self._month_dir(datetime.now())
        existing = glob.glob(str(month_dir / f"{prefix}*.json"))
        seq = len(existing) + 1
        return f"{prefix}{seq:03d}"

    # --- Primary API ---

    def start_run(
        self,
        pipeline: str,
        scenario: str | None = None,
        env: str = "LOCAL",
        operator: str = "",
        input_params: dict[str, Any] | None = None,
        prompt_version: str | None = None,
        model_version: str | None = None,
    ) -> RunContext:
        """新しい run を開始し、RunContext を返す。

        Returns:
            RunContext: with 文で使用可能なコンテキストマネージャー。
        """
        run_id = self.generate_run_id(pipeline)
        return RunContext(
            ledger=self,
            run_id=run_id,
            pipeline=pipeline,
            scenario=scenario,
            env=env,
            operator=operator,
            input_params=input_params or {},
            prompt_version=prompt_version,
            model_version=model_version,
        )

    def save(self, record: EvidenceRecord) -> str:
        """EvidenceRecord を JSON ファイルに保存する。

        Returns:
            str: 保存したファイルのフルパス。
        """
        ts = datetime.fromisoformat(record.timestamp.replace("Z", "+00:00"))
        month_dir = self._month_dir(ts)
        month_dir.mkdir(parents=True, exist_ok=True)

        file_path = month_dir / f"{record.run_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(record.to_dict(), f, ensure_ascii=False, indent=2)

        return str(file_path)

    def get(self, run_id: str) -> EvidenceRecord | None:
        """run_id で単一レコードを取得する。"""
        # run_id から日付部分を抽出して月ディレクトリを特定
        # 形式: YYYYMMDD_pipeline_seq
        parts = run_id.split("_")
        if parts and len(parts[0]) == 8:
            try:
                dt = datetime.strptime(parts[0], "%Y%m%d")
                month_dir = self._month_dir(dt)
                file_path = month_dir / f"{run_id}.json"
                if file_path.exists():
                    return self._load_file(file_path)
            except ValueError:
                pass

        # フォールバック: 全ファイルを走査
        for file_path in self._all_json_files():
            if file_path.stem == run_id:
                return self._load_file(file_path)

        return None

    def latest(
        self,
        pipeline: str,
        scenario: str | None = None,
    ) -> EvidenceRecord | None:
        """指定パイプラインの最新 run を返す。"""
        records = self.query(pipeline=pipeline, scenario=scenario, limit=1)
        return records[0] if records else None

    def query(
        self,
        pipeline: str | None = None,
        scenario: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        status: str | None = None,
        limit: int = 20,
    ) -> list[EvidenceRecord]:
        """条件でレコードを検索し、新しい順で返す。

        Args:
            pipeline: パイプライン名でフィルタ（部分一致可）。
            scenario: シナリオ名でフィルタ（部分一致可）。
            date_from: 開始日（YYYY-MM-DD）。
            date_to: 終了日（YYYY-MM-DD）。
            status: "success" / "partial" / "error" でフィルタ。
            limit: 最大返却件数。

        Returns:
            list[EvidenceRecord]: 新しい順のレコードリスト。
        """
        from_dt = _parse_date(date_from) if date_from else None
        to_dt = _parse_date(date_to, end_of_day=True) if date_to else None

        results: list[EvidenceRecord] = []
        # 新しい月から走査するためにソートを逆順にする
        for json_file in sorted(self._all_json_files(), key=lambda p: p.name, reverse=True):
            if len(results) >= limit:
                break

            record = self._load_file(json_file)
            if record is None:
                continue

            # フィルタ適用
            if pipeline and pipeline not in record.pipeline:
                continue
            if scenario and record.scenario and scenario not in record.scenario:
                continue
            if scenario and record.scenario is None:
                continue
            if status and record.status != status:
                continue

            # 日付フィルタ
            try:
                rec_dt = datetime.fromisoformat(
                    record.timestamp.replace("Z", "+00:00")
                ).replace(tzinfo=None)
            except ValueError:
                rec_dt = None

            if from_dt and rec_dt and rec_dt < from_dt:
                continue
            if to_dt and rec_dt and rec_dt > to_dt:
                continue

            results.append(record)

        return results

    def summary(self, days: int = 7) -> dict[str, Any]:
        """直近 N 日間の集計統計を返す。"""
        date_from = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        records = self.query(date_from=date_from, limit=10000)

        total = len(records)
        by_pipeline: dict[str, dict[str, int]] = {}
        status_counts: dict[str, int] = {"success": 0, "partial": 0, "error": 0}

        for r in records:
            status_counts[r.status] = status_counts.get(r.status, 0) + 1
            if r.pipeline not in by_pipeline:
                by_pipeline[r.pipeline] = {"success": 0, "partial": 0, "error": 0}
            by_pipeline[r.pipeline][r.status] = (
                by_pipeline[r.pipeline].get(r.status, 0) + 1
            )

        return {
            "period_days": days,
            "total_runs": total,
            "by_status": status_counts,
            "by_pipeline": by_pipeline,
            "success_rate": round(status_counts["success"] / total, 3) if total else 0.0,
        }

    # --- Internals ---

    def _month_dir(self, dt: datetime) -> Path:
        return self._base / dt.strftime("%Y-%m")

    def _all_json_files(self) -> list[Path]:
        """全 JSON ファイルを新しい順で返す。"""
        pattern = str(self._base / "**" / "*.json")
        files = [Path(p) for p in glob.glob(pattern, recursive=True)]
        return sorted(files, key=lambda p: p.name, reverse=True)

    def _load_file(self, file_path: Path) -> EvidenceRecord | None:
        """JSON ファイルを読み込んで EvidenceRecord を返す。失敗時は None。"""
        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)
            return EvidenceRecord.from_dict(data)
        except (json.JSONDecodeError, TypeError, KeyError):
            return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_date(date_str: str, end_of_day: bool = False) -> datetime:
    """YYYY-MM-DD 文字列を datetime に変換する。"""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    if end_of_day:
        dt = dt.replace(hour=23, minute=59, second=59)
    return dt


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli_query(args: argparse.Namespace, ledger: EvidenceLedger) -> None:
    records = ledger.query(
        pipeline=args.pipeline,
        scenario=getattr(args, "scenario", None),
        date_from=getattr(args, "date_from", None),
        date_to=getattr(args, "date_to", None),
        status=getattr(args, "status", None),
        limit=getattr(args, "limit", 20),
    )
    if not records:
        print("No records found.")
        return
    for r in records:
        print(
            f"{r.run_id}  {r.timestamp[:19]}  "
            f"pipeline={r.pipeline}  scenario={r.scenario or '-'}  "
            f"status={r.status}  duration={r.duration_seconds}s"
        )


def _cli_latest(args: argparse.Namespace, ledger: EvidenceLedger) -> None:
    record = ledger.latest(
        args.pipeline,
        scenario=getattr(args, "scenario", None),
    )
    if record is None:
        print(f"No records for pipeline='{args.pipeline}'")
        return
    print(json.dumps(record.to_dict(), ensure_ascii=False, indent=2))


def _cli_summary(args: argparse.Namespace, ledger: EvidenceLedger) -> None:
    days = getattr(args, "days", 7)
    result = ledger.summary(days=days)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="evidence_ledger",
        description="Evidence Ledger CLI",
    )
    parser.add_argument(
        "--base-dir",
        default="evidence",
        help="Storage base directory (default: evidence)",
    )
    sub = parser.add_subparsers(dest="command")

    # query
    q = sub.add_parser("query", help="Query records by filters")
    q.add_argument("--pipeline", default=None)
    q.add_argument("--scenario", default=None)
    q.add_argument("--date-from", dest="date_from", default=None)
    q.add_argument("--date-to", dest="date_to", default=None)
    q.add_argument("--status", choices=["success", "partial", "error"], default=None)
    q.add_argument("--limit", type=int, default=20)
    q.add_argument("--days", type=int, default=None, help="Shortcut: last N days")

    # latest
    lt = sub.add_parser("latest", help="Get most recent run for a pipeline")
    lt.add_argument("--pipeline", required=True)
    lt.add_argument("--scenario", default=None)

    # summary
    sm = sub.add_parser("summary", help="Summary stats for recent runs")
    sm.add_argument("--days", type=int, default=7)

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    ledger = EvidenceLedger(args.base_dir)

    if args.command == "query":
        # --days shortcut
        if getattr(args, "days", None):
            args.date_from = (
                datetime.now() - timedelta(days=args.days)
            ).strftime("%Y-%m-%d")
        _cli_query(args, ledger)
    elif args.command == "latest":
        _cli_latest(args, ledger)
    elif args.command == "summary":
        _cli_summary(args, ledger)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
