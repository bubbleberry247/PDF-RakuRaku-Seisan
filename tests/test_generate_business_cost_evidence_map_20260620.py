import csv
import importlib.util
import json
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    module_path = repo_root / "tools" / "generate_business_cost_evidence_map_20260620.py"
    spec = importlib.util.spec_from_file_location(
        "generate_business_cost_evidence_map_20260620",
        module_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_parse_s55_stdout_extracts_transfer_count_and_amount(tmp_path: Path) -> None:
    module = load_module()
    stdout_path = tmp_path / "s55.stdout.txt"
    stdout_path.write_text(
        "\n".join(
            [
                "支払総額（転記分）: 12,938,354円",
                "支払件数（転記分）: 93件",
                "Process finished | mode=dry-run success=45 provisional=0 not_found=48 skipped=60 errors=0 overflow=0 total_amount=12,938,354 elapsed=266.9s",
            ]
        ),
        encoding="utf-8",
    )

    row = module.parse_s55_stdout(stdout_path)

    assert row.cost_evidence_status == "DRYRUN_BUSINESS_AMOUNT_REPORTED"
    assert row.item_count == 93
    assert row.total_amount_yen == 12_938_354
    assert row.validation_result == "PASS"
    assert row.production_ready is False


def test_build_s44_row_recalculates_shadow_handoff_amount(tmp_path: Path) -> None:
    module = load_module()
    data_path = tmp_path / "data.json"
    ready_path = tmp_path / "latest_ready.json"
    data_path.write_text(
        json.dumps(
            {
                "total_count": 2,
                "data": [
                    {"amount": 19690},
                    {"amount": 182},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    ready_path.write_text(
        json.dumps({"data_file_abs": str(data_path)}, ensure_ascii=False),
        encoding="utf-8",
    )

    row = module.build_s44_row(ready_path)

    assert row.item_count == 2
    assert row.total_amount_yen == 19_872
    assert row.validation_result == "PASS"


def test_build_s70_row_recalculates_selected_candidate_amount(tmp_path: Path) -> None:
    module = load_module()
    csv_path = tmp_path / "selected_candidates.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=["slip_no", "amount_yen"])
        writer.writeheader()
        writer.writerow({"slip_no": "00027001", "amount_yen": "12,345"})
        writer.writerow({"slip_no": "00027002", "amount_yen": "67890"})

    row = module.build_s70_row(csv_path)

    assert row.item_count == 2
    assert row.total_amount_yen == 80_235
    assert row.validation_result == "PASS"


def test_build_s12_13_row_reads_latest_scan_only_count_summary(tmp_path: Path) -> None:
    module = load_module()
    older_summary = tmp_path / "scenario_12_13_saved_pdf_count_summary_20260620_090000.csv"
    latest_summary = tmp_path / "scenario_12_13_saved_pdf_count_summary_20260620_100000.csv"
    fieldnames = [
        "generated_at",
        "check_outlook_com_exit",
        "scan_only_dryrun_exit",
        "dry_run",
        "scanned_messages",
        "saved_attachment_count",
        "printed_path_count",
        "url_only_task_count",
        "unresolved_count",
        "report_json_path",
    ]
    for path, saved_count in [(older_summary, "9"), (latest_summary, "0")]:
        with path.open("w", encoding="utf-8-sig", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerow(
                {
                    "generated_at": "2026-06-20T10:00:00",
                    "check_outlook_com_exit": "0",
                    "scan_only_dryrun_exit": "0",
                    "dry_run": "True",
                    "scanned_messages": "4",
                    "saved_attachment_count": saved_count,
                    "printed_path_count": "0",
                    "url_only_task_count": "0",
                    "unresolved_count": "0",
                    "report_json_path": r"C:\report.json",
                }
            )

    row = module.build_s12_13_row(tmp_path)

    assert row.cost_evidence_status == "OUTLOOK_COM_DRYRUN_COUNT_PROOF_NO_PRINT_NO_MAIL"
    assert row.item_count == 0
    assert row.total_amount_yen is None
    assert row.validation_result == "PASS_COUNT_ONLY"
    assert "no print" in row.safety_scope
    assert "saved 0 attachments" in row.remaining_gap


def test_parse_s47_stdout_extracts_flag_count_without_amount(tmp_path: Path) -> None:
    module = load_module()
    stdout_path = tmp_path / "s47.stdout.txt"
    stdout_path.write_text(
        "\n".join(
            [
                "[2026-06-20 09:24:40] Found 9 flags",
                "[2026-06-20 09:24:40] Total: 9, To send: 5, To skip: 4",
                "SUCCESS: 9 records, 5 to send",
            ]
        ),
        encoding="utf-8",
    )

    row = module.parse_s47_stdout(stdout_path)

    assert row.cost_evidence_status == "DRYRUN_FLAG_COUNT_PROOF_NO_AMOUNT_NO_UPLOAD"
    assert row.item_count == 9
    assert row.total_amount_yen is None
    assert row.validation_result == "PASS_COUNT_ONLY"
    assert row.production_ready is False
    assert "5 to send" in row.remaining_gap


def test_parse_s47_stdout_flags_count_mismatch(tmp_path: Path) -> None:
    module = load_module()
    stdout_path = tmp_path / "s47.stdout.txt"
    stdout_path.write_text(
        "\n".join(
            [
                "[2026-06-20 09:24:40] Found 9 flags",
                "[2026-06-20 09:24:40] Total: 8, To send: 5, To skip: 4",
            ]
        ),
        encoding="utf-8",
    )

    row = module.parse_s47_stdout(stdout_path)

    assert row.validation_result == "COUNT_MISMATCH"


def test_build_s37_row_reports_zero_target_sample_count(tmp_path: Path) -> None:
    module = load_module()
    report_path = tmp_path / "method1_report.json"
    report_path.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "check_id": "M1-01",
                        "passed": True,
                        "summary": "get-count=0",
                        "details": {"stdout": "0"},
                    },
                    {
                        "check_id": "M1-02",
                        "passed": True,
                        "summary": "status=失敗",
                        "details": {"stdout": "{}"},
                    },
                    {
                        "check_id": "M1-03",
                        "passed": True,
                        "summary": "all conversion rules matched",
                        "details": {"checked_items": "5"},
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    row = module.build_s37_row(report_path)

    assert row.cost_evidence_status == "RECORU_SAMPLE_ZERO_TARGET_AND_GUARD_COUNT_PROOF_NO_AMOUNT"
    assert row.item_count == 0
    assert row.total_amount_yen is None
    assert row.validation_result == "PASS_COUNT_ONLY"


def test_build_s38_row_reports_one_case_without_production_register(tmp_path: Path) -> None:
    module = load_module()
    review_path = tmp_path / "s38_safe_gate.json"
    review_path.write_text(
        json.dumps(
            {
                "data_count": 1,
                "safe_candidate_passed": True,
                "safe_to_prod_register": False,
                "checks": [
                    {"id": "karuwaza_not_executed", "result": "PASS"},
                    {"id": "production_excel_not_written", "result": "PASS"},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    row = module.build_s38_row(review_path)

    assert row.cost_evidence_status == "ORDER_REGISTRATION_ONE_CASE_PROOF_NO_PROD_REGISTER_NO_AMOUNT"
    assert row.item_count == 1
    assert row.validation_result == "PASS_COUNT_ONLY"


def test_build_s42_row_reports_drive_report_rows_without_mainsv_write(tmp_path: Path) -> None:
    module = load_module()
    review_path = tmp_path / "s42_safe_gate.json"
    review_path.write_text(
        json.dumps(
            {
                "local_candidate_passed": True,
                "latest": {
                    "csv": {"row_count_without_header": 554},
                    "excel": {"max_row": 560},
                },
                "csv_dry_run_result": {"exit_code": 0},
                "static_safety": {
                    "csv_to_excel_dry_run_no_save": True,
                    "no_mainsv_write_in_python_tools": True,
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    row = module.build_s42_row(review_path)

    assert row.cost_evidence_status == "DRIVE_REPORT_ROW_COUNT_PROOF_NO_MAINSV_WRITE"
    assert row.item_count == 554
    assert row.validation_result == "PASS_COUNT_ONLY"


def test_build_s43_row_reports_temporary_save_amount_without_final_click(tmp_path: Path) -> None:
    module = load_module()
    log_path = tmp_path / "scenario43.log"
    completion_path = tmp_path / "last_completion.json"
    log_path.write_text(
        "\n".join(
            [
                "rakuraku application amounts=[('販管費分', 81649), ('工事原価分(技術部(福岡))', 1400)] total=83049",
                "temporary save completed; page closed after save click dialogs=[]",
            ]
        ),
        encoding="utf-8",
    )
    completion_path.write_text(
        json.dumps(
            {
                "status": "COMPLETED_TEMPORARY_SAVE",
                "env": "LOCAL",
                "operator_name": "テスト masam",
                "log": str(log_path),
                "safe_boundary": "temporary_save_only_final_application_not_clicked",
                "final_application_clicked": False,
                "steps": [
                    {"name": "etc_zip_download_playwright", "return_code": 0},
                    {"name": "pdf_excel_archive_pipeline", "return_code": 0},
                    {"name": "rakuraku_temporary_save", "return_code": 0},
                ],
                "outputs": {"total_amount": 83049},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    row = module.build_s43_row(completion_path)

    assert row.cost_evidence_status == "RAKURAKU_TEMP_SAVE_AMOUNT_REPORTED_FINAL_NOT_CLICKED"
    assert row.item_count == 2
    assert row.total_amount_yen == 83_049
    assert row.validation_result == "PASS"


def test_build_s51_52_row_reports_draft_save_amount_without_final_submit(tmp_path: Path) -> None:
    module = load_module()
    result_path = tmp_path / "scenario52_result_2026-05.json"
    log_path = tmp_path / "scenario_52_20260621.log"
    result_path.write_text(
        json.dumps(
            {
                "status": "success",
                "month": "2026-05",
                "env": "PROD",
                "operator_name": "瀬戸阿紀子",
                "saved_invoice_total": 256081,
                "rakuraku_application_total": 256081,
                "rakuraku_application_amounts": {
                    "販管費": 105150,
                    "工事原価": 150931,
                },
                "receipt_registered": True,
                "payment_submitted": False,
                "payment_draft_saved": True,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    log_path.write_text(
        "\n".join(
            [
                "2026-06-21 08:54:20 [INFO]   支払依頼申請: スキップ",
                "2026-06-21 08:54:20 [INFO]   支払依頼一時保存: 完了",
                "2026-06-21 08:54:20 [INFO]   楽楽申請用合計: 256,081円",
                "2026-06-21 08:54:20 [INFO] 完了通知メール: スキップ（--no-mail）",
            ]
        ),
        encoding="utf-8",
    )

    row = module.build_s51_52_row(result_path, log_path)

    assert row.cost_evidence_status == "RAKURAKU_DRAFT_SAVE_AMOUNT_REPORTED_NO_FINAL_SUBMIT_NO_MAIL"
    assert row.item_count == 2
    assert row.total_amount_yen == 256_081
    assert row.validation_result == "PASS"
    assert row.production_ready is False
    assert "final submit" in row.remaining_gap


def test_build_s51_52_row_reports_excel_only_safe_stop_candidate_amounts(tmp_path: Path) -> None:
    module = load_module()
    result_path = tmp_path / "scenario52_result_2026-05.json"
    log_path = tmp_path / "scenario_52_20260621.log"
    result_path.write_text(
        json.dumps(
            {
                "status": "success",
                "month": "2026-05",
                "env": "PROD",
                "operator_name": "瀬戸阿紀子",
                "saved_invoice_total": 256081,
                "rakuraku_application_total_candidate": 256081,
                "rakuraku_application_amounts_candidate": {
                    "販管費": 105150,
                    "工事原価": 150931,
                },
                "receipt_registered": False,
                "payment_submitted": False,
                "payment_draft_saved": False,
                "rakuraku_application_skipped": True,
                "skipped_reason": "Excel data only until paper invoice integration is ready.",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    log_path.write_text(
        "\n".join(
            [
                "2026-06-21 12:34:39 [INFO] 保存PDF・確認資料用合計: 256,081円",
                "2026-06-21 12:34:39 [INFO] 楽楽申請用合計: 256,081円",
                "2026-06-21 12:34:39 [INFO] 【安全停止】瀬戸様確認結果により、現在51/52はExcelデータ保存までです。",
                "2026-06-21 12:34:39 [INFO] 紙請求書の取り込み・電話番号統合・管理表更新が完了するまで、楽楽精算登録と一時保存は行いません。",
            ]
        ),
        encoding="utf-8",
    )

    row = module.build_s51_52_row(result_path, log_path)

    assert row.cost_evidence_status == "SOFTBANK_EXCEL_ONLY_AMOUNT_REPORTED_RAKURAKU_SKIPPED"
    assert row.item_count == 2
    assert row.total_amount_yen == 256_081
    assert row.validation_result == "PASS"
    assert "Rakuraku registration and draft save were skipped" in row.remaining_gap


def test_build_s51_52_row_reports_manual_submission_amount_without_rakuraku(tmp_path: Path) -> None:
    module = load_module()
    result_path = tmp_path / "scenario52_result_2026-05.json"
    log_path = tmp_path / "scenario_52_20260623.log"
    result_path.write_text(
        json.dumps(
            {
                "status": "success",
                "month": "2026-05",
                "env": "LOCAL",
                "operator_name": "",
                "policy": "manual_rakuraku_submission_by_customer_staff",
                "application_amounts_candidate": {
                    "販管費": 105150,
                    "工事原価": 150931,
                },
                "total_amount": 256081,
                "receipt_registered": False,
                "payment_submitted": False,
                "payment_draft_saved": False,
                "rakuraku_application_skipped": True,
                "manual_submission_required": True,
                "manual_submission_basis": "scenario51_created_documents_plus_postal_invoice",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    log_path.write_text(
        "\n".join(
            [
                "2026-06-23 11:29:27 [INFO] 合計金額: 256,081円",
                "2026-06-23 11:29:27 [INFO] 【正常停止】SoftBank 51/52は楽楽精算へ自動申請しません。",
                "2026-06-23 11:29:27 [INFO] シナリオ作成資料と郵送請求を合算し、客先担当者が手動で楽楽精算へ申請します。",
                "2026-06-23 11:29:27 [INFO] 完了通知メール: スキップ（--no-mail）",
            ]
        ),
        encoding="utf-8",
    )

    row = module.build_s51_52_row(result_path, log_path)

    assert row.cost_evidence_status == "SOFTBANK_MANUAL_SUBMISSION_AMOUNT_REPORTED_RAKURAKU_SKIPPED"
    assert row.item_count == 2
    assert row.total_amount_yen == 256_081
    assert row.validation_result == "PASS"
    assert row.production_ready is False
    assert "amount difference is 0" in row.remaining_gap


def test_build_s51_52_row_rejects_missing_no_mail_marker(tmp_path: Path) -> None:
    module = load_module()
    result_path = tmp_path / "scenario52_result_2026-05.json"
    log_path = tmp_path / "scenario_52_20260621.log"
    result_path.write_text(
        json.dumps(
            {
                "status": "success",
                "env": "PROD",
                "saved_invoice_total": 256081,
                "rakuraku_application_total": 256081,
                "rakuraku_application_amounts": {"販管費": 105150, "工事原価": 150931},
                "receipt_registered": True,
                "payment_submitted": False,
                "payment_draft_saved": True,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    log_path.write_text(
        "\n".join(
            [
                "2026-06-21 08:54:20 [INFO]   支払依頼申請: スキップ",
                "2026-06-21 08:54:20 [INFO]   支払依頼一時保存: 完了",
                "2026-06-21 08:54:20 [INFO]   楽楽申請用合計: 256,081円",
            ]
        ),
        encoding="utf-8",
    )

    row = module.build_s51_52_row(result_path, log_path)

    assert row.validation_result == "NEEDS_REVIEW"


def test_build_s56_row_reports_local_copy_write_count(tmp_path: Path) -> None:
    module = load_module()
    review_path = tmp_path / "s56_safe_gate.json"
    review_path.write_text(
        json.dumps(
            {
                "local_candidate_passed": True,
                "safe_to_prod_execute": False,
                "latest_verified_log": {
                    "target_count": 2,
                    "write_count": 2,
                    "no_traceback": True,
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    row = module.build_s56_row(review_path)

    assert row.cost_evidence_status == "S56_LOCAL_COPY_WRITE_COUNT_PROOF_NO_PRODUCTION_MAIL"
    assert row.item_count == 2
    assert row.total_amount_yen is None
    assert row.validation_result == "PASS_COUNT_ONLY"


def test_build_s57_row_reports_dryrun_output_plan_without_final_copy(tmp_path: Path) -> None:
    module = load_module()
    run_plan_path = tmp_path / "run_plan.json"
    ui_run_path = tmp_path / "ui_run.json"
    post_check_path = tmp_path / "post_check.json"
    run_plan_path.write_text(
        json.dumps(
            {
                "dry_run": True,
                "period_yyyymm": "202605",
                "target_save_path": r"C:\staging\out.txt",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    ui_run_path.write_text(
        json.dumps(
            {
                "dry_run": True,
                "result_status": "completed",
                "steps": [
                    {"name": "login", "status": "dry-run"},
                    {"name": "save", "status": "dry-run"},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    post_check_path.write_text(
        json.dumps(
            {
                "status": "missing_allowed",
                "output_exists": False,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    row = module.build_s57_row(run_plan_path, ui_run_path, post_check_path)

    assert row.cost_evidence_status == "S57_DRYRUN_OUTPUT_PLAN_PROOF_NO_FINAL_COPY"
    assert row.item_count == 1
    assert row.validation_result == "PASS_COUNT_ONLY"


def test_build_s71_row_recalculates_amount_and_withholding(tmp_path: Path) -> None:
    module = load_module()
    plan_path = tmp_path / "transfer_plan.json"
    plan_path.write_text(
        json.dumps(
            [
                {"amount": 17160, "withholding_tax": 571},
                {"amount": 140415, "withholding_tax": 0},
                {"amount": 110000, "withholding_tax": 0},
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    row = module.build_s71_row(plan_path)

    assert row.item_count == 3
    assert row.total_amount_yen == 267_575
    assert row.withholding_tax_yen == 571
    assert row.validation_result == "PASS"


def test_build_s63_row_recalculates_local_dryrun_payment_items(tmp_path: Path) -> None:
    module = load_module()
    artifact_path = tmp_path / "scenario63_run.json"
    artifact_path.write_text(
        json.dumps(
            {
                "mode": "dry_run",
                "status": "completed",
                "submitted": False,
                "selected_items": 2,
                "items": [
                    {"source_no": "0001", "amount": 110000},
                    {"source_no": "0002", "amount": "125,950"},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    row = module.build_s63_row(artifact_path)

    assert row.cost_evidence_status == "LOCAL_DRYRUN_PAYMENT_ITEMS_AMOUNT_RECALCULATED"
    assert row.item_count == 2
    assert row.total_amount_yen == 235_950
    assert row.validation_result == "PASS"
    assert row.production_ready is False


def test_build_s58_row_recalculates_latest_test_suite_report(tmp_path: Path) -> None:
    module = load_module()
    report_path = tmp_path / "s58_test_report_20260621_211545.json"
    report_path.write_text(
        json.dumps(
            {
                "status": "completed",
                "case_count": 3,
                "passed_count": 3,
                "failed_count": 0,
                "results": [
                    {"actual": {"record_count": 2, "total_amount": 80235}, "outcome": "PASS"},
                    {"actual": {"record_count": 0, "total_amount": 0}, "outcome": "PASS"},
                    {"actual": {"record_count": 5, "total_amount": "166,665"}, "outcome": "PASS"},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    row = module.build_s58_row(tmp_path)

    assert row.cost_evidence_status == "LOCAL_SAMPLE_TEST_SUITE_AMOUNT_RECALCULATED"
    assert row.item_count == 7
    assert row.total_amount_yen == 246_900
    assert row.validation_result == "PASS"
    assert row.source == str(report_path)
    assert row.production_ready is False


def test_build_markdown_warns_scope_not_production() -> None:
    module = load_module()
    payload = {
        "generated_at": "2026-06-20T00:00:00",
        "safety": "read-only",
        "scenario_count": 1,
        "amount_verified_scenario_count": 1,
        "missing_or_invalid_cost_evidence_count": 0,
        "production_ready_count": 0,
        "safe_execution_map": r"C:\safe_execution_map.md",
        "rows": [
            {
                "scenario": "55",
                "cost_evidence_status": "DRYRUN_BUSINESS_AMOUNT_REPORTED",
                "item_count": 93,
                "total_amount_yen": 12938354,
                "withholding_tax_yen": None,
                "validation_result": "PASS",
                "safety_scope": "LOCAL dry-run",
                "source": r"C:\s55.stdout.txt",
                "source_exists": True,
                "production_ready": False,
                "remaining_gap": "production write remains separate",
            }
        ],
    }

    markdown = module.build_markdown(payload)

    assert "They do not prove production payment" in markdown
    assert "12,938,354" in markdown
