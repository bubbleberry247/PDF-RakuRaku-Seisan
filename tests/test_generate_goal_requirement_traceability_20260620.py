import importlib.util
import json
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "generate_goal_requirement_traceability_20260620.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location("generate_goal_requirement_traceability_20260620", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_rows_contains_full_goal_requirements() -> None:
    module = load_module()

    rows = module.build_rows()
    ids = {row.requirement_id for row in rows}

    assert "REQ-01" in ids
    assert "REQ-03" in ids
    assert "REQ-09" in ids
    assert len(rows) >= 9


def test_rks_requirement_is_not_proven() -> None:
    module = load_module()

    rks_row = next(row for row in module.build_rows() if row.requirement_id == "REQ-03")

    assert rks_row.current_status == "NOT_PROVEN"
    assert "open/build/runtime" in rks_row.remaining_gap


def test_sample_and_cost_requirements_use_dedicated_maps() -> None:
    module = load_module()
    rows = {row.requirement_id: row for row in module.build_rows()}

    assert "sample_data_evidence_map" in rows["REQ-01"].authoritative_evidence
    assert "business_cost_evidence_map" in rows["REQ-04"].authoritative_evidence


def test_outlook_com_bundle_ready_updates_sample_requirement_gap(tmp_path: Path) -> None:
    module = load_module()
    bundle_validation = tmp_path / "bundle_validation.json"
    bundle_sync = tmp_path / "bundle_sync.json"
    outlook_collect = tmp_path / "outlook_collect.json"
    bundle_validation.write_text(
        json.dumps(
            {
                "checks": [
                    {
                        "bundle": "OUTLOOK_COM_BUNDLE",
                        "final_evidence_ready": True,
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    bundle_sync.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "bundle": "OUTLOOK_COM_BUNDLE",
                        "ready_to_sync": True,
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    outlook_collect.write_text("{}", encoding="utf-8")
    module.BUNDLE_EVIDENCE_VALIDATION_JSON = bundle_validation
    module.BUNDLE_EVIDENCE_INTAKE_SYNC_JSON = bundle_sync
    module.OUTLOOK_BUNDLE_EVIDENCE_COLLECT_JSON = outlook_collect

    rows = {row.requirement_id: row for row in module.build_rows()}

    assert "dry-run/no-print/no-mail証跡取込済み" in rows["REQ-01"].remaining_gap
    assert "実印刷・実送信は別ゲート" in rows["REQ-01"].next_evidence_needed
    assert "OUTLOOK_COM_BUNDLEはfinal evidence取込済み" in rows["REQ-12"].remaining_gap
    assert "12-13" not in rows["REQ-12"].next_evidence_needed


def test_outlook_com_bundle_safe_evidence_ready_but_sync_blocked_keeps_bundle_active(tmp_path: Path) -> None:
    module = load_module()
    bundle_validation = tmp_path / "bundle_validation.json"
    bundle_sync = tmp_path / "bundle_sync.json"
    outlook_collect = tmp_path / "outlook_collect.json"
    bundle_validation.write_text(
        json.dumps(
            {
                "checks": [
                    {
                        "bundle": "OUTLOOK_COM_BUNDLE",
                        "final_evidence_ready": False,
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    bundle_sync.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "bundle": "OUTLOOK_COM_BUNDLE",
                        "ready_to_sync": False,
                        "blockers": "OPERATOR_RESULT_BLANK, REVIEWER_BLANK, REVIEWED_AT_BLANK",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    outlook_collect.write_text(
        json.dumps(
            {
                "status": "READY_FOR_FINAL_EVIDENCE_INTAKE",
                "ready_for_intake": True,
                "log_status": {
                    "check_exit": "0",
                    "scan_exit": "0",
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    module.BUNDLE_EVIDENCE_VALIDATION_JSON = bundle_validation
    module.BUNDLE_EVIDENCE_INTAKE_SYNC_JSON = bundle_sync
    module.OUTLOOK_BUNDLE_EVIDENCE_COLLECT_JSON = outlook_collect

    rows = {row.requirement_id: row for row in module.build_rows()}

    assert "証跡配置済み" in rows["REQ-01"].remaining_gap
    assert "最終取込は未完" in rows["REQ-01"].remaining_gap
    assert "安全証跡配置済み" in rows["REQ-12"].remaining_gap
    assert "最終記入のみ未完" in rows["REQ-12"].remaining_gap
    assert "残5バンドル" in rows["REQ-12"].remaining_gap
    assert "operator_result/reviewer/reviewed_atのみ" in rows["REQ-12"].next_evidence_needed
    assert "12-13" in rows["REQ-12"].next_evidence_needed


def test_outlook_com_bundle_not_ready_keeps_sample_requirement_hold(tmp_path: Path) -> None:
    module = load_module()
    bundle_validation = tmp_path / "bundle_validation.json"
    bundle_sync = tmp_path / "bundle_sync.json"
    outlook_collect = tmp_path / "outlook_collect.json"
    bundle_validation.write_text(
        json.dumps(
            {
                "checks": [
                    {
                        "bundle": "OUTLOOK_COM_BUNDLE",
                        "final_evidence_ready": False,
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    bundle_sync.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "bundle": "OUTLOOK_COM_BUNDLE",
                        "ready_to_sync": False,
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    outlook_collect.write_text("{}", encoding="utf-8")
    module.BUNDLE_EVIDENCE_VALIDATION_JSON = bundle_validation
    module.BUNDLE_EVIDENCE_INTAKE_SYNC_JSON = bundle_sync
    module.OUTLOOK_BUNDLE_EVIDENCE_COLLECT_JSON = outlook_collect

    rows = {row.requirement_id: row for row in module.build_rows()}

    assert "Outlook COM別HOLD" in rows["REQ-01"].remaining_gap
    assert "exit 0後" in rows["REQ-01"].next_evidence_needed
    assert "12-13" in rows["REQ-12"].next_evidence_needed


def test_summarize_business_cost_amount_evidence_includes_verified_scenarios(tmp_path: Path) -> None:
    module = load_module()
    cost_map = tmp_path / "business_cost_evidence_map.json"
    cost_map.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "scenario": "44",
                        "validation_result": "PASS",
                        "total_amount_yen": 20054,
                    },
                    {
                        "scenario": "63",
                        "validation_result": "PASS",
                        "total_amount_yen": 1205130,
                    },
                    {
                        "scenario": "58",
                        "validation_result": "PASS_PARSER_TEST_ONLY",
                        "total_amount_yen": None,
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    summary = module.summarize_business_cost_amount_evidence(cost_map)

    assert summary == "44/63のsample/dry-run/mock-apply金額は再計算済み"


def test_approval_reduction_requirement_uses_external_runbook() -> None:
    module = load_module()
    rows = {row.requirement_id: row for row in module.build_rows()}

    assert "external_approval_runbook" in rows["REQ-10"].authoritative_evidence
    assert rows["REQ-10"].current_status == "OK_FOR_BUNDLE_RUNBOOK_ONLY"


def test_evidence_collection_requirement_uses_intake_sync_report() -> None:
    module = load_module()
    rows = {row.requirement_id: row for row in module.build_rows()}

    assert "bundle_evidence_intake_sync" in rows["REQ-11"].authoritative_evidence
    assert "最終証跡取り込み同期" in rows["REQ-11"].remaining_gap


def test_backup_requirement_uses_code_artifact_backups() -> None:
    module = load_module()
    rows = {row.requirement_id: row for row in module.build_rows()}

    assert "goal_code_artifact_backups" in rows["REQ-08"].authoritative_evidence
    assert "別名保存" in rows["REQ-08"].requirement


def test_build_payload_counts_missing_sources(monkeypatch, tmp_path: Path) -> None:
    module = load_module()
    present = tmp_path / "present.md"
    missing = tmp_path / "missing.md"
    present.write_text("ok", encoding="utf-8")
    rows = [
        module.RequirementTraceRow(
            requirement_id="REQ-X",
            requirement="sample",
            current_status="PARTIAL_OK",
            authoritative_evidence=str(present),
            remaining_gap="gap",
            next_evidence_needed="next",
            source_exists=True,
        ),
        module.RequirementTraceRow(
            requirement_id="REQ-Y",
            requirement="sample",
            current_status="PARTIAL_OK",
            authoritative_evidence=str(missing),
            remaining_gap="gap",
            next_evidence_needed="next",
            source_exists=False,
        ),
    ]
    monkeypatch.setattr(module, "build_rows", lambda: rows)

    payload = module.build_payload()

    assert payload["overall_goal_complete"] is False
    assert payload["requirement_count"] == 2
    assert payload["missing_source_count"] == 1


def test_build_markdown_includes_trace_table() -> None:
    module = load_module()
    payload = {
        "generated_at": "2026-06-20T00:00:00",
        "overall_goal_complete": False,
        "safety": "read-only requirement traceability only; no external operation",
        "requirement_count": 1,
        "complete_or_safe_count": 0,
        "missing_source_count": 0,
        "rows": [
            {
                "requirement_id": "REQ-01",
                "requirement": "全シナリオサンプルデータを用意する",
                "current_status": "PARTIAL_OK",
                "authoritative_evidence": r"C:\evidence.md",
                "remaining_gap": "HOLD remains",
                "next_evidence_needed": "operator result",
                "source_exists": True,
            }
        ],
    }

    markdown = module.build_markdown(payload)

    assert "# 目標要件トレーサビリティ 2026-06-20" in markdown
    assert "| REQ-01 | 全シナリオサンプルデータを用意する | PARTIAL_OK" in markdown
