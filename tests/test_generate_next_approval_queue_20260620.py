import importlib.util
import json
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "generate_next_approval_queue_20260620.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location("generate_next_approval_queue_20260620", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sample_unblock_payload() -> dict:
    return {
        "generated_at": "2026-06-20T13:00:43",
        "approval_bundles": [
            {
                "bundle": "BUSINESS_DATA_APPROVAL_BUNDLE",
                "owner": "業務担当者",
                "scenarios": "43, 47, 55, 63",
                "still_forbidden": "本番登録・実送信・本番Excel/サーバ確定書込",
            },
            {
                "bundle": "OUTLOOK_COM_BUNDLE",
                "owner": "PC/Outlook管理者",
                "scenarios": "12/13",
                "still_forbidden": "実印刷・実送信・メール状態変更",
            },
            {
                "bundle": "RK10_EDITOR_RUNTIME_BUNDLE",
                "owner": "RK10操作担当者",
                "scenarios": "37, 38, 42, 51/52, 56, 57, 58",
                "still_forbidden": "ButtonRun・本番書込・実メール・最終申請",
            },
        ],
    }


def test_build_rows_sorts_external_approval_priority_first() -> None:
    module = load_module()
    outlook_evidence = module.OutlookComEvidence(
        status="NO_CURRENT_OUTLOOK_COM_DIAGNOSIS",
        diagnosis="",
        next_action="",
        report_path="",
    )

    rows = module.build_rows(sample_unblock_payload(), outlook_evidence=outlook_evidence)

    assert [row.bundle for row in rows] == [
        "OUTLOOK_COM_BUNDLE",
        "BUSINESS_DATA_APPROVAL_BUNDLE",
        "RK10_EDITOR_RUNTIME_BUNDLE",
    ]
    assert rows[0].rank == 1
    assert rows[0].scenario_count == 1
    assert rows[1].scenario_count == 4


def test_build_payload_uses_unblock_board_source(monkeypatch, tmp_path: Path) -> None:
    module = load_module()
    external_runbook_json = tmp_path / "external_approval_runbook.json"
    external_runbook_json.write_text(
        json.dumps(
            {
                "outlook_bundle_script": r"C:\repo\outlook_com_bundle_dryrun.ps1",
                "outlook_recovery_checklist": r"C:\repo\outlook_com_recovery_checklist.md",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "EXTERNAL_RUNBOOK_JSON", external_runbook_json)
    monkeypatch.setattr(module, "build_unblock_payload", lambda _exit_code: sample_unblock_payload())
    monkeypatch.setattr(module, "load_completed_bundles", lambda: set())
    monkeypatch.setattr(module, "build_rks_runtime_focus_rows", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        module,
        "detect_outlook_com_evidence",
        lambda: module.OutlookComEvidence(
            status="NO_CURRENT_OUTLOOK_COM_DIAGNOSIS",
            diagnosis="",
            next_action="",
            report_path="",
        ),
    )

    payload = module.build_payload(2)

    assert payload["overall_goal_complete"] is False
    assert payload["queue_count"] == 3
    assert payload["next_bundle"] == "OUTLOOK_COM_BUNDLE"
    assert payload["next_operator_action"].startswith("Classic Outlook")
    assert payload["source_unblock_board_generated_at"] == "2026-06-20T13:00:43"
    assert payload["rks_runtime_focus_count"] == 0
    assert payload["outlook_bundle_script"] == r"C:\repo\outlook_com_bundle_dryrun.ps1"
    assert payload["outlook_recovery_checklist"] == r"C:\repo\outlook_com_recovery_checklist.md"


def test_build_rows_excludes_completed_bundles() -> None:
    module = load_module()

    rows = module.build_rows(
        sample_unblock_payload(),
        completed_bundles={"OUTLOOK_COM_BUNDLE"},
    )

    assert [row.bundle for row in rows] == [
        "BUSINESS_DATA_APPROVAL_BUNDLE",
        "RK10_EDITOR_RUNTIME_BUNDLE",
    ]


def test_load_completed_bundles_uses_bundle_sync_ready_to_sync(tmp_path: Path) -> None:
    module = load_module()
    sync_path = tmp_path / "bundle_sync.json"
    sync_path.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "bundle": "OUTLOOK_COM_BUNDLE",
                        "ready_to_sync": False,
                    },
                    {
                        "bundle": "BUSINESS_REVIEW_BUNDLE",
                        "ready_to_sync": True,
                    },
                ],
                "checks": [
                    {
                        "bundle": "OUTLOOK_COM_BUNDLE",
                        "final_evidence_ready": True,
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    completed = module.load_completed_bundles(sync_path)

    assert completed == {"BUSINESS_REVIEW_BUNDLE"}


def test_outlook_ready_status_keeps_outlook_active_but_not_next() -> None:
    module = load_module()
    outlook_evidence = module.OutlookComEvidence(
        status="OUTLOOK_COM_READY",
        diagnosis="COM check and scan-only dry-run both exited 0.",
        next_action="",
        report_path=r"C:\repo\outlook.md",
    )

    rows = module.build_rows(
        sample_unblock_payload(),
        outlook_evidence=outlook_evidence,
    )

    assert [row.bundle for row in rows] == [
        "BUSINESS_DATA_APPROVAL_BUNDLE",
        "RK10_EDITOR_RUNTIME_BUNDLE",
        "OUTLOOK_COM_BUNDLE",
    ]
    outlook_row = rows[-1]
    assert outlook_row.rank == 7
    assert "operator_result/reviewer/reviewed_at" in outlook_row.operator_action
    assert "証跡配置済み" in outlook_row.why_next


def test_outlook_com_evidence_updates_operator_action(tmp_path: Path) -> None:
    module = load_module()
    diagnosis_path = tmp_path / "outlook_com_environment_diagnosis.json"
    report_path = tmp_path / "outlook_com_environment_diagnosis.md.numbered"
    diagnosis_path.write_text(
        json.dumps(
            {
                "status": "OUTLOOK_RUNNING_BUT_COM_AUTOMATION_REJECTED",
                "diagnosis": "Classic Outlook is running but COM attach failed.",
                "next_action": "Close all Outlook windows, clear modal prompts, reopen Classic Outlook, then rerun OUTLOOK_COM_BUNDLE.",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    report_path.write_text("# report\n", encoding="utf-8")

    outlook_evidence = module.detect_outlook_com_evidence(diagnosis_path, report_path)
    rows = module.build_rows(sample_unblock_payload(), outlook_evidence=outlook_evidence)
    outlook_row = next(row for row in rows if row.bundle == "OUTLOOK_COM_BUNDLE")

    assert outlook_evidence.status == "OUTLOOK_RUNNING_BUT_COM_AUTOMATION_REJECTED"
    assert outlook_evidence.report_path == str(report_path)
    assert outlook_row.operator_action.startswith("Close all Outlook windows")


def test_build_rks_runtime_focus_rows_keeps_only_required_unapproved_rows(tmp_path: Path, monkeypatch) -> None:
    module = load_module()
    validation_path = tmp_path / "rks_runtime_validation.json"
    validation_path.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "scenario": "57",
                        "source_status": "WAITING_OPERATOR_RK10_EVIDENCE",
                        "rks_path": r"C:\RK10\57.rks",
                        "requires_rk10_evidence": True,
                        "approved": False,
                        "issue_codes": "LATEST_LOG_PATH_MISSING_OR_NOT_FOUND",
                        "operator_decision": "",
                        "rk10_editor_open": "CONFIRMED",
                        "rk10_build": "CONFIRMED",
                        "runtime_or_safe_stop": "",
                        "latest_log_clean": "",
                        "latest_log_path": "",
                        "operator_name": "probe-import",
                        "checked_at": "2026-06-18T10:32:56",
                    },
                    {
                        "scenario": "37",
                        "source_status": "WAITING_OPERATOR_RK10_EVIDENCE",
                        "rks_path": r"C:\RK10\37.rks",
                        "requires_rk10_evidence": True,
                        "approved": True,
                        "issue_codes": "",
                    },
                    {
                        "scenario": "44",
                        "source_status": "WAITING_PREREQUISITE_BEFORE_RKS_RUNTIME",
                        "rks_path": r"C:\RK10\44.rks",
                        "requires_rk10_evidence": False,
                        "approved": False,
                        "issue_codes": "",
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "RKS_RUNTIME_FINAL_EVIDENCE_DIR", tmp_path / "final")

    rows = module.build_rks_runtime_focus_rows(validation_path)

    assert [row.scenario for row in rows] == ["57"]
    assert rows[0].confirmed_evidence == "RK10 editor open, RK10 build"
    assert "runtime_or_safe_stop" in rows[0].remaining_inputs
    assert "rk10_editor_open" not in rows[0].remaining_inputs
    assert "no-mail/no-upload/no-write" in rows[0].next_safe_action
    assert "ButtonRun" in rows[0].blocked_operation
    assert rows[0].evidence_folder.endswith("final\\57")


def test_rk10_cold_evidence_updates_runtime_actions(tmp_path: Path, monkeypatch) -> None:
    module = load_module()
    validation_path = tmp_path / "rks_runtime_validation.json"
    checklist_path = tmp_path / "rk10_editor_recovery_checklist.md.numbered"
    checklist_path.write_text(
        "- 58原本、58 ASCII別名コピー、過去成功済み63の全てが `RK10_EDITOR_OPEN_TIMEOUT`。\n"
        "- 58固有ではなく、現在のRK10 Editor環境がcold。"
        "画面証跡ではRK10ライセンス有効期限警告が出ている。\n",
        encoding="utf-8",
    )
    validation_path.write_text(
        json.dumps(
            {
                "rows": [
                {
                    "scenario": "58",
                    "source_status": "WAITING_OPERATOR_RK10_EVIDENCE",
                    "rks_path": r"C:\RK10\58.rks",
                    "requires_rk10_evidence": True,
                    "approved": False,
                    "issue_codes": "LATEST_LOG_PATH_MISSING_OR_NOT_FOUND",
                    "operator_decision": "",
                    "rk10_editor_open": "",
                    "rk10_build": "",
                    "runtime_or_safe_stop": "",
                    "latest_log_clean": "",
                    "latest_log_path": "",
                    "operator_name": "",
                    "checked_at": "",
                }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "RKS_RUNTIME_FINAL_EVIDENCE_DIR", tmp_path / "final")

    cold_evidence = module.detect_rk10_cold_evidence(checklist_path)
    rows = module.build_rks_runtime_focus_rows(
        validation_path,
        checklist_path,
        cold_evidence,
    )
    queue_rows = module.build_rows(sample_unblock_payload(), cold_evidence)
    rk10_row = next(row for row in queue_rows if row.bundle == "RK10_EDITOR_RUNTIME_BUNDLE")

    assert cold_evidence.status == "RK10_EDITOR_ENV_COLD_LICENSE_PROMPT"
    assert rows[0].rk10_cold_status == "RK10_EDITOR_ENV_COLD_LICENSE_PROMPT"
    assert rows[0].confirmed_evidence == "none"
    assert "rk10_editor_open" in rows[0].remaining_inputs
    assert rows[0].rk10_recovery_checklist == str(checklist_path)
    assert rows[0].next_safe_action.startswith("先にRK10ライセンス復旧")
    assert rk10_row.operator_action.startswith("RK10ライセンス復旧")


def test_build_markdown_keeps_safety_boundaries() -> None:
    module = load_module()
    rows = [row.__dict__ for row in module.build_rows(sample_unblock_payload())]
    payload = {
        "generated_at": "2026-06-20T13:30:00",
        "overall_goal_complete": False,
        "safety": "read-only approval queue; no external operation",
        "queue_count": len(rows),
        "next_bundle": "OUTLOOK_COM_BUNDLE",
        "next_operator_action": "Classic Outlookを通常画面で復旧する",
        "outlook_com_status": "OUTLOOK_RUNNING_BUT_COM_AUTOMATION_REJECTED",
        "outlook_com_diagnosis_report": r"C:\repo\outlook_com_environment_diagnosis.md.numbered",
        "outlook_bundle_script": r"C:\repo\outlook_com_bundle_dryrun.ps1",
        "outlook_recovery_checklist": r"C:\repo\outlook_com_recovery_checklist.md",
        "rk10_editor_cold_status": "RK10_EDITOR_ENV_COLD_LICENSE_PROMPT",
        "rk10_recovery_checklist": r"C:\repo\rk10_editor_recovery_checklist.md.numbered",
        "rks_runtime_focus_count": 1,
        "rks_runtime_focus_source": r"C:\repo\rks_runtime_validation.json",
        "rks_runtime_focus_rows": [
            {
                "scenario": "58",
                "source_status": "WAITING_OPERATOR_RK10_EVIDENCE",
                "rks_path": r"C:\RK10\58.rks",
                "issue_codes": "LATEST_LOG_PATH_MISSING_OR_NOT_FOUND",
                "confirmed_evidence": "none",
                "remaining_inputs": "latest_log_path",
                "latest_log_path": "",
                "evidence_folder": r"C:\repo\final\58",
                "rk10_cold_status": "RK10_EDITOR_ENV_COLD_LICENSE_PROMPT",
                "rk10_recovery_checklist": r"C:\repo\rk10_editor_recovery_checklist.md.numbered",
                "next_safe_action": "支払日/対象区分を選び、no-mail/no-write safe-stopでlatest clean logを取得する",
                "blocked_operation": "MainSV本番TXT書込, 保存通知メール送信, RK10 ButtonRun",
            }
        ],
        "external_runbook": r"C:\repo\external_approval_runbook.md.numbered",
        "external_runbook_json": r"C:\repo\external_approval_runbook.json",
        "rows": rows,
    }

    markdown = module.build_markdown(payload)

    assert "next_bundle: `OUTLOOK_COM_BUNDLE`" in markdown
    assert "OUTLOOK_RUNNING_BUT_COM_AUTOMATION_REJECTED" in markdown
    assert "outlook_com_bundle_dryrun.ps1" in markdown
    assert "outlook_com_recovery_checklist.md" in markdown
    assert "削除証跡は承認ゲートの必須条件にしない" in markdown
    assert "実印刷・実送信・メール状態変更" in markdown
    assert "## Focused RKS Runtime Rows" in markdown
    assert "| 58 | WAITING_OPERATOR_RK10_EVIDENCE" in markdown
    assert "RK10_EDITOR_ENV_COLD_LICENSE_PROMPT" in markdown
    assert "rk10_editor_recovery_checklist.md.numbered" in markdown
    assert "前提条件待ち・入口選定待ちは含めない" in markdown
    assert "--execute" not in markdown
