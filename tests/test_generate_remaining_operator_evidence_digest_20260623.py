import importlib.util
import json
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "generate_remaining_operator_evidence_digest_20260623.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location(
        "generate_remaining_operator_evidence_digest_20260623",
        module_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_digest_rows_uses_latest_file_and_boundary(tmp_path: Path) -> None:
    module = load_module()
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    old_log = evidence_dir / "old.txt"
    latest_log = evidence_dir / "latest.txt"
    old_log.write_text("old dry-run", encoding="utf-8")
    latest_log.write_text(
        "Payment execution, mail, RK10 ButtonRun, and production writes are not executed.",
        encoding="utf-8",
    )

    execution_payload = {
        "rows": [
            {
                "bundle": "PAYMENT_APPROVAL_BUNDLE",
                "scenario": "70",
                "status": "MISSING_OPERATOR_FIELDS",
                "missing_fields": "operator_result, reviewer, reviewed_at",
                "evidence_path": str(evidence_dir),
                "evidence_exists": True,
                "approved": False,
                "csv_path": r"C:\packet.csv",
            }
        ]
    }
    boundary_payload = {
        "rows": [
            {
                "bundle": "PAYMENT_APPROVAL_BUNDLE",
                "scenario": "70",
                "boundary_class": "HUMAN_OR_EXTERNAL_APPROVAL_REQUIRED_NO_AUTO_APPROVAL",
                "codex_can_continue_with": "証跡フォルダ案内まで",
                "human_or_external_input_needed": "operator_result/reviewer/reviewed_at",
            }
        ]
    }

    rows = module.build_digest_rows(execution_payload, boundary_payload)

    assert len(rows) == 1
    assert rows[0].latest_evidence_file == str(latest_log)
    assert rows[0].evidence_file_count == 2
    assert rows[0].boundary_class == "HUMAN_OR_EXTERNAL_APPROVAL_REQUIRED_NO_AUTO_APPROVAL"
    assert "not executed" in rows[0].side_effect_boundary_lines


def test_build_payload_excludes_approved_rows(tmp_path: Path) -> None:
    module = load_module()
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "log.txt").write_text("DRY-RUN complete", encoding="utf-8")
    execution_json = tmp_path / "execution.json"
    boundary_json = tmp_path / "boundary.json"
    execution_json.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "bundle": "OUTLOOK_COM_BUNDLE",
                        "scenario": "12/13",
                        "evidence_path": str(evidence_dir),
                        "evidence_exists": True,
                        "approved": True,
                    },
                    {
                        "bundle": "BUSINESS_REVIEW_BUNDLE",
                        "scenario": "44",
                        "status": "MISSING_OPERATOR_FIELDS",
                        "missing_fields": "operator_result, reviewer, reviewed_at",
                        "evidence_path": str(evidence_dir),
                        "evidence_exists": True,
                        "approved": False,
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    boundary_json.write_text(json.dumps({"rows": []}), encoding="utf-8")

    payload = module.build_payload(execution_json, boundary_json)

    assert payload["pending_row_count"] == 1
    assert payload["evidence_exists_count"] == 1
    assert payload["rows"][0]["scenario"] == "44"


def test_build_payload_excludes_scope_excluded_rows(tmp_path: Path) -> None:
    module = load_module()
    execution_json = tmp_path / "execution.json"
    boundary_json = tmp_path / "boundary.json"
    scope_json = tmp_path / "scope_exclusions.json"
    execution_json.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "bundle": "BUSINESS_DATA_APPROVAL_BUNDLE",
                        "scenario": "43",
                        "status": "MISSING_OPERATOR_FIELDS",
                        "missing_fields": "operator_result, reviewer, reviewed_at",
                        "evidence_path": str(tmp_path / "scenario_43"),
                        "evidence_exists": True,
                        "approved": False,
                    },
                    {
                        "bundle": "BUSINESS_REVIEW_BUNDLE",
                        "scenario": "44",
                        "status": "MISSING_OPERATOR_FIELDS",
                        "missing_fields": "operator_result, reviewer, reviewed_at",
                        "evidence_path": str(tmp_path / "scenario_44"),
                        "evidence_exists": True,
                        "approved": False,
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    boundary_json.write_text(json.dumps({"rows": []}), encoding="utf-8")
    scope_json.write_text(
        json.dumps({"exclusions": [{"scenario": "43", "active": True}]}),
        encoding="utf-8",
    )

    payload = module.build_payload(execution_json, boundary_json, scope_json)

    assert payload["raw_pending_row_count"] == 2
    assert payload["pending_row_count"] == 1
    assert payload["scope_excluded_row_count"] == 1
    assert payload["scope_excluded_scenarios"] == ["43"]
    assert payload["rows"][0]["scenario"] == "44"


def test_write_outputs_creates_numbered_reports(tmp_path: Path) -> None:
    module = load_module()
    payload = {
        "generated_at": "2026-06-23T06:30:00",
        "execution_validation_json": r"C:\execution.json",
        "boundary_json": r"C:\boundary.json",
        "scope_exclusions_json": r"C:\scope.json",
        "safety": "read-only",
        "rk10_license_dialog_policy": "RPA開発版AI付きが既定選択ならOKのみ",
        "raw_pending_row_count": 1,
        "scope_excluded_scenarios": [],
        "scope_excluded_row_count": 0,
        "pending_row_count": 1,
        "evidence_exists_count": 1,
        "latest_file_exists_count": 1,
        "attention_row_count": 0,
        "boundary_counts": {
            "HUMAN_OR_EXTERNAL_APPROVAL_REQUIRED_NO_AUTO_APPROVAL": 1
        },
        "rows": [
            {
                "bundle": "BUSINESS_REVIEW_BUNDLE",
                "scenario": "44",
                "status": "MISSING_OPERATOR_FIELDS",
                "missing_fields": "operator_result",
                "evidence_path": r"C:\evidence",
                "evidence_exists": "YES",
                "evidence_file_count": 1,
                "latest_evidence_file": r"C:\evidence\log.txt",
                "latest_evidence_file_exists": "YES",
                "latest_evidence_modified_at": "2026-06-23T06:30:00",
                "attention_terms": "",
                "side_effect_boundary_lines": "dry-run",
                "boundary_class": "HUMAN_OR_EXTERNAL_APPROVAL_REQUIRED_NO_AUTO_APPROVAL",
                "codex_can_continue_with": "案内まで",
                "human_or_external_input_needed": "reviewer",
                "source_packet_csv": r"C:\packet.csv",
            }
        ],
    }

    module.write_outputs(payload, tmp_path)

    assert (tmp_path / "remaining_operator_evidence_digest.json.numbered").exists()
    assert (tmp_path / "remaining_operator_evidence_digest.csv.numbered").exists()
    assert (tmp_path / "remaining_operator_evidence_digest.md.numbered").exists()
