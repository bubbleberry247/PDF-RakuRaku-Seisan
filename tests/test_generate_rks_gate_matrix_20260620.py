import importlib.util
import json
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    module_path = repo_root / "tools" / "generate_rks_gate_matrix_20260620.py"
    spec = importlib.util.spec_from_file_location("generate_rks_gate_matrix_20260620", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_row_records_source_existence(tmp_path: Path) -> None:
    module = load_module()
    source = tmp_path / "evidence.md"
    source.write_text("ok", encoding="utf-8")

    result = module.row(
        "57",
        "current RKS",
        "RKS_OPEN_BUILD_OK_RUNTIME_LOG_MISSING",
        "open/build",
        "latest clean log",
        "safe-stop rerun",
        "production write",
        str(source),
    )

    assert result.source_exists is True
    assert result.scenario == "57"


def test_build_payload_counts_rows_and_missing_sources(tmp_path: Path, monkeypatch) -> None:
    module = load_module()
    present = tmp_path / "present.md"
    present.write_text("ok", encoding="utf-8")
    rows = [
        module.row(
            "57",
            "current RKS",
            "RKS_OPEN_BUILD_OK_RUNTIME_LOG_MISSING",
            "open/build",
            "latest clean log",
            "safe-stop rerun",
            "production write",
            str(present),
        ),
        module.row(
            "12/13",
            "Python",
            "N_A_NO_PRIMARY_RKS",
            "PDF extraction",
            "Outlook COM",
            "COM recheck",
            "print/mail",
            str(tmp_path / "missing.md"),
        ),
    ]
    monkeypatch.setattr(module, "build_rows", lambda: rows)
    monkeypatch.setattr(
        module,
        "RKS_RUNTIME_INTAKE_VALIDATION",
        tmp_path / "missing_runtime_validation.json",
    )

    payload = module.build_payload()

    assert payload["overall_rks_production_ready"] is False
    assert payload["row_count"] == 2
    assert payload["unresolved_rks_gate_count"] == 1
    assert payload["technical_unresolved_rks_gate_count"] == 1
    assert payload["deferred_rks_gate_count"] == 0
    assert payload["rks_technical_gate_complete"] is False
    assert payload["missing_source_count"] == 1
    assert "rks_static_guard_audit_20260620" in payload["supplemental_static_guard_audit"]
    assert payload["runtime_intake_validation_exists"] in {True, False}


def test_build_payload_uses_runtime_intake_to_resolve_rks_rows(tmp_path: Path, monkeypatch) -> None:
    module = load_module()
    source = tmp_path / "evidence.md"
    source.write_text("ok", encoding="utf-8")
    validation = tmp_path / "runtime_validation.json"
    validation.write_text(
        json.dumps(
            {
                "overall_rks_runtime_evidence_complete": True,
                "rows": [
                    {
                        "scenario": "57",
                        "requires_rk10_evidence": True,
                        "approved": True,
                        "latest_log_has_hard_errors": False,
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    rows = [
        module.row(
            "57",
            "current RKS",
            "RKS_OPEN_BUILD_OK_RUNTIME_LOG_MISSING",
            "open/build",
            "latest clean log",
            "safe-stop rerun",
            "production write",
            str(source),
        )
    ]
    monkeypatch.setattr(module, "build_rows", lambda: rows)
    monkeypatch.setattr(module, "RKS_RUNTIME_INTAKE_VALIDATION", validation)

    payload = module.build_payload()

    assert payload["overall_rks_production_ready"] is True
    assert payload["unresolved_rks_gate_count"] == 0
    assert payload["technical_unresolved_rks_gate_count"] == 0
    assert payload["deferred_rks_gate_count"] == 0
    assert payload["rks_technical_gate_complete"] is True
    assert payload["runtime_intake_validation_complete"] is True
    assert payload["rows"][0]["runtime_intake_status"] == "RKS_RUNTIME_EVIDENCE_CONFIRMED"
    assert payload["rows"][0]["runtime_intake_approved_count"] == 1


def test_build_payload_marks_deferred_runtime_rows_without_resolving(tmp_path: Path, monkeypatch) -> None:
    module = load_module()
    source = tmp_path / "evidence.md"
    source.write_text("ok", encoding="utf-8")
    validation = tmp_path / "runtime_validation.json"
    validation.write_text(
        json.dumps(
            {
                "overall_rks_runtime_evidence_complete": True,
                "rows": [
                    {
                        "scenario": "44",
                        "requires_rk10_evidence": False,
                        "approved": False,
                        "latest_log_has_hard_errors": False,
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    rows = [
        module.row(
            "44",
            "handoff then RKS",
            "BUSINESS_REVIEW_HOLD_BEFORE_RKS",
            "shadow contract",
            "business review",
            "review OK rows",
            "Rakuraku registration",
            str(source),
        )
    ]
    monkeypatch.setattr(module, "build_rows", lambda: rows)
    monkeypatch.setattr(module, "RKS_RUNTIME_INTAKE_VALIDATION", validation)

    payload = module.build_payload()

    assert payload["overall_rks_production_ready"] is False
    assert payload["unresolved_rks_gate_count"] == 1
    assert payload["technical_unresolved_rks_gate_count"] == 0
    assert payload["deferred_rks_gate_count"] == 1
    assert payload["rks_technical_gate_complete"] is True
    assert payload["rows"][0]["runtime_intake_status"] == "RKS_RUNTIME_DEFERRED_BY_PREREQUISITE_OR_ENTRY_DECISION"
    assert payload["rows"][0]["runtime_intake_required_count"] == 0


def test_outlook_12_13_row_uses_safe_evidence_when_collected(tmp_path: Path, monkeypatch) -> None:
    module = load_module()
    evidence_dir = tmp_path / "scenario_12_13"
    evidence_dir.mkdir()
    collect_json = tmp_path / "outlook_bundle_evidence_collect.json"
    collect_json.write_text(
        json.dumps(
            {
                "status": "READY_FOR_FINAL_EVIDENCE_INTAKE",
                "ready_for_intake": True,
                "evidence_path": str(evidence_dir),
                "log_status": {
                    "check_exit": "0",
                    "scan_exit": "0",
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "OUTLOOK_BUNDLE_EVIDENCE_COLLECT_JSON", collect_json)

    result = module.outlook_12_13_row()

    assert result.current_rks_status == "N_A_NO_PRIMARY_RKS"
    assert "Outlook COM check + scan-only dry-run/no-print/no-mail confirmed" in result.strongest_confirmed_scope
    assert "Outlook COM still HOLD" not in result.strongest_confirmed_scope
    assert result.primary_source == str(evidence_dir)
    assert result.source_exists is True


def test_s57_s58_rows_record_existing_logs_as_non_promotable() -> None:
    module = load_module()

    rows = {item.scenario: item for item in module.build_rows()}

    assert "not_promotable" in rows["57"].existing_evidence_search_result
    assert "no RKS execution/UI side effects" in rows["57"].existing_evidence_search_result
    assert "not_promotable" in rows["58"].existing_evidence_search_result
    assert "RKS editor open/build/runtime/latest clean log UNCONFIRMED" in rows["58"].existing_evidence_search_result


def test_build_markdown_includes_matrix_and_blocked_operations() -> None:
    module = load_module()
    payload = {
        "generated_at": "2026-06-20T00:00:00",
        "overall_rks_production_ready": False,
        "safety": "read-only",
        "row_count": 1,
        "unresolved_rks_gate_count": 1,
        "technical_unresolved_rks_gate_count": 1,
        "deferred_rks_gate_count": 0,
        "rks_technical_gate_complete": False,
        "missing_source_count": 0,
        "supplemental_static_guard_audit": "rks_static_guard_audit.md.numbered",
        "supplemental_static_guard_audit_exists": True,
        "runtime_intake_validation": "runtime.json",
        "runtime_intake_validation_exists": True,
        "runtime_intake_validation_complete": False,
        "rows": [
            {
                "scenario": "44",
                "operational_entry": "handoff",
                "current_rks_status": "BUSINESS_REVIEW_HOLD_BEFORE_RKS",
                "runtime_intake_status": "RKS_RUNTIME_EVIDENCE_PENDING",
                "runtime_intake_approved_count": 0,
                "runtime_intake_required_count": 1,
                "runtime_intake_source": "runtime.json",
                "strongest_confirmed_scope": "shadow contract",
                "missing_gate": "business spot check",
                "next_safe_action": "OK rows only",
                "blocked_operation": "Rakuraku registration",
                "primary_source": "source.md",
                "source_exists": True,
                "existing_evidence_search_result": "not_promotable: dry-run only",
            }
        ],
    }

    markdown = module.build_markdown(payload)

    assert "## Matrix" in markdown
    assert "BUSINESS_REVIEW_HOLD_BEFORE_RKS" in markdown
    assert "RKS_RUNTIME_EVIDENCE_PENDING" in markdown
    assert "Rakuraku registration" in markdown
    assert "## Existing Evidence Search Results" in markdown
    assert "not_promotable: dry-run only" in markdown
    assert "## Supplemental Static Guard Audit" in markdown
    assert "## Supplemental Runtime Intake Validation" in markdown
