import importlib.util
import json
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "generate_goal_unblock_board_20260620.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location("generate_goal_unblock_board_20260620", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_find_rks_status_matches_grouped_scenario() -> None:
    module = load_module()
    rows = [
        {
            "scenario": "37/47/55/63",
            "current_rks_status": "SAFE_STOP_SCOPE_ONLY",
        }
    ]

    assert module.find_rks_status("55", rows) == "SAFE_STOP_SCOPE_ONLY"
    assert module.find_rks_status("70", rows) == "NO_RKS_MATRIX_ROW"


def test_no_rks_matrix_row_does_not_force_rk10_bundle() -> None:
    module = load_module()

    bundle, owner, reason = module.classify_bundle(
        "43",
        "SCOPED_CONFIRMED_AFTER_FEEDBACK",
        "NO_RKS_MATRIX_ROW",
    )

    assert bundle == "BUSINESS_DATA_APPROVAL_BUNDLE"
    assert owner == "業務担当者"
    assert "実対象データ" in reason


def test_classify_outlook_ready_status_as_final_field_input() -> None:
    module = load_module()

    bundle, owner, reason = module.classify_bundle(
        "12/13",
        "READY_FOR_DRYRUN_NO_PRINT_NO_MAIL",
        "N_A_NO_PRIMARY_RKS",
    )

    assert bundle == "OUTLOOK_COM_BUNDLE"
    assert owner == "PC/Outlook管理者"
    assert "証跡は配置済み" in reason
    assert "未確認" not in reason


def test_classify_resolution_lane_separates_final_intake_from_gui() -> None:
    module = load_module()

    outlook_lane, outlook_action, outlook_hint = module.classify_resolution_lane(
        "12/13",
        "READY_FOR_DRYRUN_NO_PRINT_NO_MAIL",
        "N_A_NO_PRIMARY_RKS",
        "OUTLOOK_COM_BUNDLE",
    )
    rk10_lane, rk10_action, rk10_hint = module.classify_resolution_lane(
        "57",
        "RKS_OPEN_BUILD_OK_RUNTIME_LOG_MISSING",
        "RKS_OPEN_BUILD_OK_RUNTIME_LOG_MISSING",
        "RK10_EDITOR_RUNTIME_BUNDLE",
    )

    assert outlook_lane == "NEEDS_FINAL_INTAKE_ONLY"
    assert "operator_result" in outlook_action
    assert "実印刷・実送信承認は不要" in outlook_hint
    assert rk10_lane == "NEEDS_RK10_GUI_EVIDENCE"
    assert "open/build/runtime/latest log" in rk10_action
    assert "1回のRK10確認枠" in rk10_hint


def test_build_payload_groups_approval_bundles(monkeypatch) -> None:
    module = load_module()
    snapshot_payload = {
        "scenarios": [
            {
                "scenario": "44",
                "current_status": "HOLD_NO_CONFIRMED_ROWS",
                "next_action": "fill OK rows",
                "source": r"C:\evidence\s44.csv",
            },
            {
                "scenario": "57",
                "current_status": "RKS_OPEN_BUILD_OK_RUNTIME_LOG_MISSING",
                "next_action": "safe-stop rerun",
                "source": r"C:\evidence\s57.md",
            },
        ]
    }
    rks_payload = {
        "rows": [
            {
                "scenario": "57",
                "current_rks_status": "RKS_OPEN_BUILD_OK_RUNTIME_LOG_MISSING",
            }
        ]
    }
    monkeypatch.setattr(module, "build_snapshot_payload", lambda _exit_code: snapshot_payload)
    monkeypatch.setattr(module, "build_rks_payload", lambda: rks_payload)

    payload = module.build_payload(2)

    assert payload["scenario_count"] == 2
    assert payload["approval_required_count"] == 2
    assert payload["approval_bundle_count"] == 2
    assert payload["resolution_lane_counts"] == {
        "NEEDS_BUSINESS_REVIEW_INPUT": 1,
        "NEEDS_RK10_GUI_EVIDENCE": 1,
    }
    bundles = {item["bundle"] for item in payload["approval_bundles"]}
    assert bundles == {"BUSINESS_REVIEW_BUNDLE", "RK10_EDITOR_RUNTIME_BUNDLE"}


def test_build_payload_marks_sync_ready_outlook_bundle_not_approval_required(
    monkeypatch,
    tmp_path: Path,
) -> None:
    module = load_module()
    sync_path = tmp_path / "bundle_sync.json"
    sync_path.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "bundle": "OUTLOOK_COM_BUNDLE",
                        "scenarios": "12/13",
                        "ready_to_sync": True,
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    snapshot_payload = {
        "scenarios": [
            {
                "scenario": "12/13",
                "current_status": "READY_FOR_DRYRUN_NO_PRINT_NO_MAIL",
                "next_action": "keep no-print/no-mail boundary",
                "source": r"C:\evidence\s12_13.md",
            },
            {
                "scenario": "44",
                "current_status": "HOLD_NO_CONFIRMED_ROWS",
                "next_action": "fill OK rows",
                "source": r"C:\evidence\s44.csv",
            },
        ]
    }
    rks_payload = {
        "rows": [
            {
                "scenario": "12/13",
                "current_rks_status": "N_A_NO_PRIMARY_RKS",
            },
            {
                "scenario": "44",
                "current_rks_status": "BUSINESS_REVIEW_HOLD_BEFORE_RKS",
            },
        ]
    }
    monkeypatch.setattr(module, "BUNDLE_EVIDENCE_INTAKE_SYNC_JSON", sync_path)
    monkeypatch.setattr(module, "build_snapshot_payload", lambda _exit_code: snapshot_payload)
    monkeypatch.setattr(module, "build_rks_payload", lambda: rks_payload)

    payload = module.build_payload(0)

    indexed_rows = {row["scenario"]: row for row in payload["rows"]}
    assert payload["scenario_count"] == 2
    assert payload["approval_required_count"] == 1
    assert payload["approval_bundle_count"] == 2
    assert indexed_rows["12/13"]["approval_bundle"] == "OUTLOOK_COM_BUNDLE"
    assert indexed_rows["12/13"]["can_codex_complete_next_gate_without_approval"] is True
    assert "final evidence ready" in indexed_rows["12/13"]["blocked_until"]
    assert {bundle["bundle"] for bundle in payload["approval_bundles"]} == {
        "BUSINESS_REVIEW_BUNDLE",
        "OUTLOOK_COM_BUNDLE",
    }


def test_build_payload_keeps_outlook_bundle_active_when_sync_not_ready(
    monkeypatch,
    tmp_path: Path,
) -> None:
    module = load_module()
    sync_path = tmp_path / "bundle_sync.json"
    sync_path.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "bundle": "OUTLOOK_COM_BUNDLE",
                        "scenarios": "12/13",
                        "ready_to_sync": False,
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    snapshot_payload = {
        "scenarios": [
            {
                "scenario": "12/13",
                "current_status": "READY_FOR_DRYRUN_NO_PRINT_NO_MAIL",
                "next_action": "keep no-print/no-mail boundary",
                "source": r"C:\evidence\s12_13.md",
            },
        ]
    }
    rks_payload = {
        "rows": [
            {
                "scenario": "12/13",
                "current_rks_status": "N_A_NO_PRIMARY_RKS",
            },
        ]
    }
    monkeypatch.setattr(module, "BUNDLE_EVIDENCE_INTAKE_SYNC_JSON", sync_path)
    monkeypatch.setattr(module, "build_snapshot_payload", lambda _exit_code: snapshot_payload)
    monkeypatch.setattr(module, "build_rks_payload", lambda: rks_payload)

    payload = module.build_payload(0)

    indexed_rows = {row["scenario"]: row for row in payload["rows"]}
    assert payload["approval_required_count"] == 1
    assert payload["completed_bundles_excluded"] == []
    assert indexed_rows["12/13"]["can_codex_complete_next_gate_without_approval"] is False
    assert indexed_rows["12/13"]["owner"] == "PC/Outlook管理者"


def test_load_completed_bundles_uses_intake_only_when_sync_is_missing(
    tmp_path: Path,
) -> None:
    module = load_module()
    evidence_dir = tmp_path / "bundle_evidence_packs" / "outlook_com_bundle" / "final_evidence" / "scenario_12_13"
    evidence_dir.mkdir(parents=True)
    (evidence_dir / "scenario_12_13_dryrun_no_print_no_mail_20260620_120000.log").write_text(
        "dry-run completed; no-print; no-mail",
        encoding="utf-8",
    )
    intake_path = tmp_path / "bundle_evidence_packs" / "outlook_com_bundle" / "final_evidence_intake.csv"
    intake_path.write_text(
        "\n".join(
            [
                "bundle,scenario,final_evidence_path,operator_result,reviewer,reviewed_at",
                f"OUTLOOK_COM_BUNDLE,12/13,{evidence_dir},OK,Human Reviewer,2026-06-21T12:00:00",
            ]
        ),
        encoding="utf-8",
    )
    missing_sync = tmp_path / "missing_bundle_sync.json"
    module.BUNDLE_EVIDENCE_PACKS_DIR = tmp_path / "bundle_evidence_packs"

    completed = module.load_completed_bundles(missing_sync)

    assert completed == {"OUTLOOK_COM_BUNDLE"}


def test_load_completed_bundles_rejects_legacy_outlook_auto_collector_intake(
    tmp_path: Path,
) -> None:
    module = load_module()
    evidence_dir = tmp_path / "bundle_evidence_packs" / "outlook_com_bundle" / "final_evidence" / "scenario_12_13"
    evidence_dir.mkdir(parents=True)
    (evidence_dir / "scenario_12_13_dryrun_no_print_no_mail_20260620_120000.log").write_text(
        "dry-run completed; no-print; no-mail",
        encoding="utf-8",
    )
    intake_path = tmp_path / "bundle_evidence_packs" / "outlook_com_bundle" / "final_evidence_intake.csv"
    intake_path.write_text(
        "\n".join(
            [
                "bundle,scenario,final_evidence_path,operator_result,reviewer,reviewed_at",
                f"OUTLOOK_COM_BUNDLE,12/13,{evidence_dir},OK,OUTLOOK_COM_BUNDLE_AUTO_COLLECTOR,2026-06-21T12:00:00",
            ]
        ),
        encoding="utf-8",
    )
    missing_sync = tmp_path / "missing_bundle_sync.json"
    module.BUNDLE_EVIDENCE_PACKS_DIR = tmp_path / "bundle_evidence_packs"

    completed = module.load_completed_bundles(missing_sync)

    assert completed == set()


def test_build_markdown_includes_bundle_and_scenario_board() -> None:
    module = load_module()
    payload = {
        "generated_at": "2026-06-20T00:00:00",
        "overall_goal_complete": False,
        "safety": "read-only evidence board only; no external operation",
        "safe_refresh_available_without_new_approval": True,
        "fixed_safe_runner": r"C:\python.exe -X utf8 C:\repo\tools\run_safe_goal_checks_20260620.py --s12-exit-code 2",
        "scenario_count": 1,
        "approval_required_count": 1,
        "approval_bundle_count": 1,
        "approval_bundles": [
            {
                "bundle": "OUTLOOK_COM_BUNDLE",
                "owner": "PC/Outlook管理者",
                "scenarios": "12/13",
                "approval_scope": "COM check only",
                "still_forbidden": "real print/send",
            }
        ],
        "rows": [
            {
                "scenario": "12/13",
                "current_status": "HOLD_OUTLOOK_COM_NOT_READY",
                "rks_status": "N_A_NO_PRIMARY_RKS",
                "approval_bundle": "OUTLOOK_COM_BUNDLE",
                "owner": "PC/Outlook管理者",
                "can_codex_complete_next_gate_without_approval": False,
                "blocked_until": "COM exit 0",
                "next_action": "check COM",
                "source": r"C:\evidence\s12.md",
            }
        ],
    }

    markdown = module.build_markdown(payload)

    assert "# 目標HOLD解除ボード 2026-06-20" in markdown
    assert "OUTLOOK_COM_BUNDLE" in markdown
    assert "| 12/13 | HOLD_OUTLOOK_COM_NOT_READY | N_A_NO_PRIMARY_RKS | OUTLOOK_COM_BUNDLE" in markdown
