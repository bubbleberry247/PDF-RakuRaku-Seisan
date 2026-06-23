import csv
import importlib.util
import json
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    module_path = repo_root / "tools" / "check_hold_release_gates_20260620.py"
    spec = importlib.util.spec_from_file_location("check_hold_release_gates_20260620", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_check_s44_without_ok_rows_stays_hold(tmp_path: Path) -> None:
    module = load_module()
    path = tmp_path / "s44.csv"
    write_csv(
        path,
        [
            {"confirm_ok": "", "reject_reason": ""},
            {"confirm_ok": "NG", "reject_reason": "amount mismatch"},
        ],
    )

    result = module.check_s44(path)

    assert result.ready is False
    assert result.status == "HOLD_NO_CONFIRMED_ROWS"
    assert "0 OK rows" in result.reason


def test_check_s44_with_ok_rows_is_candidate_ready(tmp_path: Path) -> None:
    module = load_module()
    path = tmp_path / "s44.csv"
    write_csv(
        path,
        [
            {"confirm_ok": "OK", "reject_reason": ""},
            {"confirm_ok": "", "reject_reason": ""},
        ],
    )

    result = module.check_s44(path)

    assert result.ready is True
    assert result.status == "READY_FOR_LIVE_HANDOFF_CANDIDATE_FILTER"
    assert "1 OK rows" in result.reason


def test_check_s70_requires_business_approval_fields(tmp_path: Path) -> None:
    module = load_module()
    path = tmp_path / "s70.csv"
    write_csv(
        path,
        [
            {
                "required_expected_count": "TODO_business_confirm",
                "required_expected_total_amount_yen": "TODO_business_confirm",
                "required_bank_transfer_confirmed": "TODO_true_after_bank_evidence",
                "required_approver": "TODO_name_or_approval_record",
                "execute_allowed_now": "NO",
            }
        ],
    )

    result = module.check_s70(path)

    assert result.ready is False
    assert result.status == "HOLD_PAYMENT_EXECUTE_NOT_ALLOWED"
    assert "required_expected_count" in result.reason


def test_check_s70_ready_is_preview_only(tmp_path: Path) -> None:
    module = load_module()
    path = tmp_path / "s70.csv"
    write_csv(
        path,
        [
            {
                "required_expected_count": "12",
                "required_expected_total_amount_yen": "345678",
                "required_bank_transfer_confirmed": "true",
                "required_approver": "approved-by-manager",
                "execute_allowed_now": "YES",
            }
        ],
    )

    result = module.check_s70(path)

    assert result.ready is True
    assert result.status == "READY_FOR_CONFIRM_PREVIEW_ONLY"
    assert "execute still needs separate explicit approval" in result.next_action


def test_check_s71_requires_all_ready_rows(tmp_path: Path) -> None:
    module = load_module()
    path = tmp_path / "s71.csv"
    write_csv(
        path,
        [
            {"required_var": "RK10_AzureDI_Endpoint", "status": "READY"},
            {"required_var": "budget_approval", "status": "MISSING"},
        ],
    )

    result = module.check_s71(path)

    assert result.ready is False
    assert result.status == "HOLD_AZURE_OCR_GATE_MISSING"
    assert "budget_approval" in result.reason


def test_check_s12_13_requires_zero_exit_code_without_collected_evidence(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = load_module()
    missing_collect_json = tmp_path / "missing_outlook_bundle_evidence_collect.json"
    monkeypatch.setattr(module, "OUTLOOK_BUNDLE_EVIDENCE_COLLECT_JSON", missing_collect_json)

    hold_result = module.check_s12_13(2)
    ready_result = module.check_s12_13(0)

    assert hold_result.ready is False
    assert hold_result.status == "HOLD_OUTLOOK_COM_NOT_READY"
    assert ready_result.ready is True
    assert ready_result.status == "READY_FOR_DRYRUN_NO_PRINT_NO_MAIL"


def test_check_s12_13_ready_uses_collected_scan_evidence_even_when_exit_input_is_stale(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = load_module()
    collect_json = tmp_path / "outlook_bundle_evidence_collect.json"
    collect_json.write_text(
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
    monkeypatch.setattr(module, "OUTLOOK_BUNDLE_EVIDENCE_COLLECT_JSON", collect_json)

    result = module.check_s12_13(2)

    assert result.ready is True
    assert result.status == "READY_FOR_DRYRUN_NO_PRINT_NO_MAIL"
    assert "collected Outlook COM check + scan-only dry-run/no-print/no-mail evidence is ready" in result.reason
    assert "s12_exit_code_input=2" in result.reason
    assert "operator_result/reviewer/reviewed_at" in result.next_action
    assert "Run dry-run/no-print/no-mail" not in result.next_action
    assert result.source == str(collect_json)
