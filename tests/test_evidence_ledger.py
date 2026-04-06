# -*- coding: utf-8 -*-
"""Tests for tools/common/evidence_ledger.py"""
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

# パスを通す
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.common.evidence_ledger import EvidenceLedger, EvidenceRecord, RunContext


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_ledger(tmp_path: Path) -> EvidenceLedger:
    """一時ディレクトリを使う EvidenceLedger。"""
    return EvidenceLedger(str(tmp_path / "evidence"))


# ---------------------------------------------------------------------------
# EvidenceRecord
# ---------------------------------------------------------------------------

class TestEvidenceRecord:
    def test_to_dict_roundtrip(self):
        rec = EvidenceRecord(
            run_id="20260406_ocr_001",
            timestamp="2026-04-06T00:00:00+00:00",
            pipeline="ocr",
            scenario="scenario-44",
        )
        data = rec.to_dict()
        restored = EvidenceRecord.from_dict(data)
        assert restored.run_id == rec.run_id
        assert restored.pipeline == rec.pipeline
        assert restored.scenario == rec.scenario

    def test_from_dict_ignores_unknown_fields(self):
        data = {
            "run_id": "abc",
            "timestamp": "2026-04-06T00:00:00+00:00",
            "pipeline": "ocr",
            "scenario": None,
            "unknown_future_field": "value",
        }
        rec = EvidenceRecord.from_dict(data)
        assert rec.run_id == "abc"

    def test_default_values(self):
        rec = EvidenceRecord(
            run_id="x",
            timestamp="2026-04-06T00:00:00+00:00",
            pipeline="test",
            scenario=None,
        )
        assert rec.status == "success"
        assert rec.input_files == []
        assert rec.errors == []
        assert rec.validations == []
        assert rec.env == "LOCAL"


# ---------------------------------------------------------------------------
# RunContext — context manager lifecycle
# ---------------------------------------------------------------------------

class TestRunContext:
    def test_save_on_exit(self, tmp_ledger: EvidenceLedger):
        """__exit__ 時に自動保存される。"""
        with tmp_ledger.start_run("ocr") as run:
            run.add_input("/tmp/a.pdf")
            run.add_metric("pages", 3)

        saved = tmp_ledger.get(run.run_id)
        assert saved is not None
        assert saved.pipeline == "ocr"
        assert "/tmp/a.pdf" in saved.input_files
        assert saved.output_summary["pages"] == 3

    def test_duration_recorded(self, tmp_ledger: EvidenceLedger):
        """duration_seconds が記録される。"""
        with tmp_ledger.start_run("scraper") as run:
            time.sleep(0.05)

        saved = tmp_ledger.get(run.run_id)
        assert saved is not None
        assert saved.duration_seconds >= 0.04

    def test_status_success_by_default(self, tmp_ledger: EvidenceLedger):
        with tmp_ledger.start_run("rpa_s55") as run:
            pass

        saved = tmp_ledger.get(run.run_id)
        assert saved.status == "success"

    def test_status_error_on_add_error(self, tmp_ledger: EvidenceLedger):
        """add_error() 呼び出し後は status='error'。"""
        with tmp_ledger.start_run("ocr") as run:
            run.add_error("ValueError", "something went wrong")

        saved = tmp_ledger.get(run.run_id)
        assert saved.status == "error"
        assert saved.errors[0]["type"] == "ValueError"

    def test_status_error_on_exception(self, tmp_ledger: EvidenceLedger):
        """未キャッチ例外でも status='error' になる。"""
        run_id = None
        try:
            with tmp_ledger.start_run("ocr") as run:
                run_id = run.run_id
                raise RuntimeError("unexpected failure")
        except RuntimeError:
            pass

        assert run_id is not None
        saved = tmp_ledger.get(run_id)
        assert saved is not None
        assert saved.status == "error"
        assert "RuntimeError" in saved.errors[0]["type"]
        assert "unexpected failure" in saved.errors[0]["message"]
        assert "RuntimeError" in saved.errors[0]["traceback"]

    def test_partial_status_preserved(self, tmp_ledger: EvidenceLedger):
        """明示的に set_status('partial') した場合は保持される。"""
        with tmp_ledger.start_run("rpa_s55") as run:
            run.add_error("MinorError", "non-fatal")
            run.set_status("partial")

        saved = tmp_ledger.get(run.run_id)
        assert saved.status == "partial"

    def test_validation_recorded(self, tmp_ledger: EvidenceLedger):
        with tmp_ledger.start_run("ocr") as run:
            run.add_validation("amount_present", True, "¥1,500 found")
            run.add_validation("date_present", False, "not found")

        saved = tmp_ledger.get(run.run_id)
        assert len(saved.validations) == 2
        assert saved.validations[0]["check"] == "amount_present"
        assert saved.validations[0]["result"] is True
        assert saved.validations[1]["result"] is False

    def test_warnings_recorded(self, tmp_ledger: EvidenceLedger):
        with tmp_ledger.start_run("scraper") as run:
            run.add_warning("DOM structure changed")

        saved = tmp_ledger.get(run.run_id)
        assert "DOM structure changed" in saved.warnings

    def test_reconciliation_recorded(self, tmp_ledger: EvidenceLedger):
        recon = {"total_EM": 10, "per_row_match_rate": 0.95}
        with tmp_ledger.start_run("ocr") as run:
            run.set_reconciliation(recon)

        saved = tmp_ledger.get(run.run_id)
        assert saved.reconciliation == recon

    def test_run_id_accessible_inside_context(self, tmp_ledger: EvidenceLedger):
        """with ブロック内で run_id にアクセスできる。"""
        with tmp_ledger.start_run("ocr") as run:
            assert run.run_id.startswith("2026")
            assert "ocr" in run.run_id

    def test_scenario_stored(self, tmp_ledger: EvidenceLedger):
        with tmp_ledger.start_run("ocr", scenario="scenario-44") as run:
            pass

        saved = tmp_ledger.get(run.run_id)
        assert saved.scenario == "scenario-44"

    def test_input_params_stored(self, tmp_ledger: EvidenceLedger):
        params = {"env": "LOCAL", "dry_run": True}
        with tmp_ledger.start_run("rpa_s55", input_params=params) as run:
            pass

        saved = tmp_ledger.get(run.run_id)
        assert saved.input_params["dry_run"] is True


# ---------------------------------------------------------------------------
# EvidenceLedger — generate_run_id
# ---------------------------------------------------------------------------

class TestGenerateRunId:
    def test_format(self, tmp_ledger: EvidenceLedger):
        """形式: YYYYMMDD_pipeline_NNN"""
        run_id = tmp_ledger.generate_run_id("ocr")
        parts = run_id.split("_")
        assert len(parts[0]) == 8
        assert parts[1] == "ocr"
        assert parts[-1].isdigit()

    def test_uniqueness_sequential(self, tmp_ledger: EvidenceLedger):
        """同日に複数生成したら連番が増える。"""
        id1 = tmp_ledger.generate_run_id("ocr")
        # 1件保存して連番をインクリメントさせる
        rec = EvidenceRecord(
            run_id=id1,
            timestamp=datetime.now(timezone.utc).isoformat(),
            pipeline="ocr",
            scenario=None,
        )
        tmp_ledger.save(rec)

        id2 = tmp_ledger.generate_run_id("ocr")
        assert id1 != id2

    def test_hyphen_replaced(self, tmp_ledger: EvidenceLedger):
        """パイプライン名のハイフンはアンダースコアに変換される。"""
        run_id = tmp_ledger.generate_run_id("rpa-s55")
        assert "rpa_s55" in run_id

    def test_different_pipelines_independent(self, tmp_ledger: EvidenceLedger):
        """パイプラインが異なれば連番は独立する。"""
        id_ocr = tmp_ledger.generate_run_id("ocr")
        id_rpa = tmp_ledger.generate_run_id("rpa_s55")
        assert "ocr" in id_ocr
        assert "rpa_s55" in id_rpa


# ---------------------------------------------------------------------------
# EvidenceLedger — save / get
# ---------------------------------------------------------------------------

class TestSaveGet:
    def test_save_creates_json_file(self, tmp_ledger: EvidenceLedger):
        rec = EvidenceRecord(
            run_id=tmp_ledger.generate_run_id("ocr"),
            timestamp=datetime.now(timezone.utc).isoformat(),
            pipeline="ocr",
            scenario=None,
        )
        path = tmp_ledger.save(rec)
        assert Path(path).exists()
        assert path.endswith(".json")

    def test_get_returns_correct_record(self, tmp_ledger: EvidenceLedger):
        with tmp_ledger.start_run("ocr", scenario="scenario-44") as run:
            run.add_metric("pages", 7)

        fetched = tmp_ledger.get(run.run_id)
        assert fetched is not None
        assert fetched.run_id == run.run_id
        assert fetched.output_summary["pages"] == 7

    def test_get_nonexistent_returns_none(self, tmp_ledger: EvidenceLedger):
        assert tmp_ledger.get("nonexistent_run_id_xyz") is None

    def test_file_organized_by_month(self, tmp_ledger: EvidenceLedger):
        with tmp_ledger.start_run("ocr") as run:
            pass

        path = tmp_ledger.save(run.record)
        # パスに年月ディレクトリが含まれる (YYYY-MM)
        parts = Path(path).parts
        month_dirs = [p for p in parts if len(p) == 7 and "-" in p]
        assert len(month_dirs) == 1


# ---------------------------------------------------------------------------
# EvidenceLedger — query
# ---------------------------------------------------------------------------

class TestQuery:
    def _make_records(self, ledger: EvidenceLedger) -> list[str]:
        """テスト用レコードを複数作成して run_id リストを返す。"""
        run_ids = []
        for pipeline, scenario, status in [
            ("ocr", "scenario-44", "success"),
            ("ocr", "scenario-44", "error"),
            ("rpa_s55", "scenario-55", "success"),
            ("scraper", None, "partial"),
        ]:
            with ledger.start_run(pipeline, scenario=scenario) as run:
                if status != "success":
                    run.add_error("TestError", "test")
                    run.set_status(status)
            run_ids.append(run.run_id)
        return run_ids

    def test_query_all(self, tmp_ledger: EvidenceLedger):
        self._make_records(tmp_ledger)
        results = tmp_ledger.query(limit=100)
        assert len(results) == 4

    def test_query_by_pipeline(self, tmp_ledger: EvidenceLedger):
        self._make_records(tmp_ledger)
        results = tmp_ledger.query(pipeline="ocr")
        assert all(r.pipeline == "ocr" for r in results)
        assert len(results) == 2

    def test_query_by_scenario(self, tmp_ledger: EvidenceLedger):
        self._make_records(tmp_ledger)
        results = tmp_ledger.query(scenario="scenario-55")
        assert all(r.scenario == "scenario-55" for r in results)
        assert len(results) == 1

    def test_query_by_status(self, tmp_ledger: EvidenceLedger):
        self._make_records(tmp_ledger)
        results = tmp_ledger.query(status="error")
        assert all(r.status == "error" for r in results)

    def test_query_limit(self, tmp_ledger: EvidenceLedger):
        self._make_records(tmp_ledger)
        results = tmp_ledger.query(limit=2)
        assert len(results) <= 2

    def test_query_date_from(self, tmp_ledger: EvidenceLedger):
        self._make_records(tmp_ledger)
        today = datetime.now().strftime("%Y-%m-%d")
        results = tmp_ledger.query(date_from=today)
        # 今日作ったデータなので全件ヒットする
        assert len(results) == 4

    def test_query_date_from_future(self, tmp_ledger: EvidenceLedger):
        self._make_records(tmp_ledger)
        future = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        results = tmp_ledger.query(date_from=future)
        assert len(results) == 0

    def test_query_returns_newest_first(self, tmp_ledger: EvidenceLedger):
        """新しい順に返る（run_id の連番が大きい方が新しい）。"""
        self._make_records(tmp_ledger)
        results = tmp_ledger.query(limit=100)
        if len(results) >= 2:
            # タイムスタンプ順になっているか（同日なら run_id ソートで確認）
            names = [r.run_id for r in results]
            assert names == sorted(names, reverse=True)


# ---------------------------------------------------------------------------
# EvidenceLedger — latest
# ---------------------------------------------------------------------------

class TestLatest:
    def test_latest_returns_most_recent(self, tmp_ledger: EvidenceLedger):
        with tmp_ledger.start_run("ocr") as run1:
            run1.add_metric("run", 1)
        with tmp_ledger.start_run("ocr") as run2:
            run2.add_metric("run", 2)

        latest = tmp_ledger.latest("ocr")
        assert latest is not None
        assert latest.run_id == run2.run_id

    def test_latest_none_when_no_records(self, tmp_ledger: EvidenceLedger):
        assert tmp_ledger.latest("nonexistent_pipeline") is None

    def test_latest_with_scenario_filter(self, tmp_ledger: EvidenceLedger):
        with tmp_ledger.start_run("ocr", scenario="scenario-44") as run44:
            pass
        with tmp_ledger.start_run("ocr", scenario="scenario-51") as run51:
            pass

        latest_44 = tmp_ledger.latest("ocr", scenario="scenario-44")
        assert latest_44 is not None
        assert latest_44.run_id == run44.run_id

        latest_51 = tmp_ledger.latest("ocr", scenario="scenario-51")
        assert latest_51 is not None
        assert latest_51.run_id == run51.run_id


# ---------------------------------------------------------------------------
# EvidenceLedger — summary
# ---------------------------------------------------------------------------

class TestSummary:
    def test_summary_basic(self, tmp_ledger: EvidenceLedger):
        with tmp_ledger.start_run("ocr") as run:
            pass
        with tmp_ledger.start_run("ocr") as run:
            run.add_error("E", "e")

        result = tmp_ledger.summary(days=1)
        assert result["total_runs"] == 2
        assert result["by_status"]["success"] == 1
        assert result["by_status"]["error"] == 1
        assert result["success_rate"] == 0.5

    def test_summary_empty(self, tmp_ledger: EvidenceLedger):
        result = tmp_ledger.summary(days=1)
        assert result["total_runs"] == 0
        assert result["success_rate"] == 0.0

    def test_summary_by_pipeline(self, tmp_ledger: EvidenceLedger):
        with tmp_ledger.start_run("ocr") as run:
            pass
        with tmp_ledger.start_run("rpa_s55") as run:
            pass

        result = tmp_ledger.summary(days=1)
        assert "ocr" in result["by_pipeline"]
        assert "rpa_s55" in result["by_pipeline"]
        assert result["by_pipeline"]["ocr"]["success"] == 1

    def test_summary_period_days(self, tmp_ledger: EvidenceLedger):
        with tmp_ledger.start_run("ocr") as run:
            pass
        result = tmp_ledger.summary(days=7)
        assert result["period_days"] == 7
        assert result["total_runs"] >= 1


# ---------------------------------------------------------------------------
# CLI smoke test
# ---------------------------------------------------------------------------

class TestCLI:
    def test_cli_summary(self, tmp_path: Path, capsys):
        """CLI summary コマンドが JSON を出力する。"""
        import subprocess
        result = subprocess.run(
            [
                sys.executable,
                "-m", "tools.common.evidence_ledger",
                "--base-dir", str(tmp_path / "evidence"),
                "summary",
                "--days", "7",
            ],
            capture_output=True,
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), ".."),
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "total_runs" in data
        assert "by_status" in data

    def test_cli_query_no_records(self, tmp_path: Path):
        import subprocess
        result = subprocess.run(
            [
                sys.executable,
                "-m", "tools.common.evidence_ledger",
                "--base-dir", str(tmp_path / "evidence"),
                "query",
                "--pipeline", "ocr",
            ],
            capture_output=True,
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), ".."),
        )
        assert result.returncode == 0
        assert "No records found." in result.stdout

    def test_cli_latest_no_records(self, tmp_path: Path):
        import subprocess
        result = subprocess.run(
            [
                sys.executable,
                "-m", "tools.common.evidence_ledger",
                "--base-dir", str(tmp_path / "evidence"),
                "latest",
                "--pipeline", "ocr",
            ],
            capture_output=True,
            text=True,
            cwd=os.path.join(os.path.dirname(__file__), ".."),
        )
        assert result.returncode == 0
        assert "No records" in result.stdout
