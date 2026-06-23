import csv
import importlib.util
import sys
from pathlib import Path


def load_module():
    repo_root = Path(__file__).parent.parent
    module_path = repo_root / "tools" / "build_s44_spot_check_handoff_candidates_20260620.py"
    spec = importlib.util.spec_from_file_location(
        "build_s44_spot_check_handoff_candidates_20260620",
        module_path,
    )
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


def base_row(tmp_path: Path, confirm_ok: str = "") -> dict[str, str]:
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 sample")
    return {
        "confirm_ok": confirm_ok,
        "reject_reason": "",
        "vendor_name": "テスト商事",
        "amount_estimate": "1234",
        "receiving_date": "20260131",
        "invoice_number": "T1234567890123",
        "filename": "sample.pdf",
        "operation_id": "operation-1",
        "pdf_path": str(pdf_path),
    }


def test_analyze_without_ok_rows_stays_hold(tmp_path: Path) -> None:
    module = load_module()
    csv_path = tmp_path / "spot.csv"
    write_csv(csv_path, [base_row(tmp_path, "")])

    summary = module.analyze_spot_check(csv_path)

    assert summary.status == "HOLD_NO_OK_ROWS"
    assert summary.ready_for_shadow_handoff is False
    assert summary.ok_count == 0
    assert summary.blank_count == 1


def test_build_review_aid_flags_amount_mismatch_without_approval(tmp_path: Path) -> None:
    module = load_module()
    row = {
        **base_row(tmp_path, ""),
        "amount_estimate": "1234",
        "filename": "operation_vendor_202601_2000.pdf",
    }

    review_rows = module.build_review_aid_rows([row])

    assert review_rows[0]["operator_entry_confirm_ok"] == ""
    assert review_rows[0]["filename_amount"] == "2000"
    assert review_rows[0]["amount_difference_yen"] == "-766"
    assert review_rows[0]["review_bucket"] == "AMOUNT_MISMATCH_REVIEW"
    assert "Compare amount_estimate" in review_rows[0]["operator_next_action"]
    assert "NEEDS_BUSINESS_CONFIRM_OK_OR_NG" in review_rows[0]["attention_reasons"]
    assert "AMOUNT_DIFFERS_FROM_FILENAME" in review_rows[0]["attention_reasons"]
    assert review_rows[0]["pdf_exists"] == "YES"


def test_build_review_aid_marks_amount_match_as_quick_review(tmp_path: Path) -> None:
    module = load_module()
    row = {
        **base_row(tmp_path, ""),
        "amount_estimate": "1234",
        "filename": "operation_vendor_202601_1234.pdf",
    }

    review_rows = module.build_review_aid_rows([row])

    assert review_rows[0]["review_bucket"] == "AMOUNT_MATCH_QUICK_REVIEW"
    assert review_rows[0]["review_sort_key"] == "50"
    assert "Open PDF briefly" in review_rows[0]["operator_next_action"]


def test_build_review_aid_marks_zero_amount_as_high_priority(tmp_path: Path) -> None:
    module = load_module()
    row = {
        **base_row(tmp_path, ""),
        "amount_estimate": "0",
        "filename": "operation_vendor_202601_1234.pdf",
    }

    review_rows = module.build_review_aid_rows([row])

    assert review_rows[0]["review_bucket"] == "AMOUNT_ZERO_REVIEW"
    assert review_rows[0]["review_sort_key"] == "30"
    assert "Do not enter OK" in review_rows[0]["operator_next_action"]


def test_parse_filename_amount_uses_amount_not_date_or_duplicate_suffix() -> None:
    module = load_module()

    assert module.parse_filename_amount("id_vendor_202604_220.pdf") == 220
    assert module.parse_filename_amount("id_vendor_202601_400_001.pdf") == 400


def test_decision_input_template_preserves_existing_operator_entry(tmp_path: Path) -> None:
    module = load_module()
    source_csv = tmp_path / "spot.csv"
    decision_csv = tmp_path / "decision.csv"
    row = base_row(tmp_path, "")
    write_csv(source_csv, [row])
    write_csv(
        decision_csv,
        [
            {
                "operation_id": "operation-1",
                "operator_entry_confirm_ok": "OK",
                "operator_entry_reject_reason": "",
                "reviewer": "reviewer-a",
                "reviewed_at": "2026-06-20T10:00:00",
                "vendor_name": "old",
                "amount_estimate": "old",
                "receiving_date": "old",
                "invoice_number": "old",
                "filename": "old",
                "pdf_path": "old",
                "pdf_exists": "NO",
            }
        ],
    )

    row_count = module.ensure_decision_input_template(source_csv, decision_csv)
    decision_rows = module.read_csv_rows(decision_csv)

    assert row_count == 1
    assert decision_rows[0]["operator_entry_confirm_ok"] == "OK"
    assert decision_rows[0]["reviewer"] == "reviewer-a"
    assert decision_rows[0]["review_bucket"] == "AMOUNT_MATCH_QUICK_REVIEW"
    assert "Open PDF briefly" in decision_rows[0]["operator_next_action"]
    assert decision_rows[0]["vendor_name"] == "テスト商事"


def test_decision_input_template_tolerates_locked_existing_file(tmp_path: Path, monkeypatch) -> None:
    module = load_module()
    source_csv = tmp_path / "spot.csv"
    decision_csv = tmp_path / "decision.csv"
    write_csv(source_csv, [base_row(tmp_path, "")])
    write_csv(
        decision_csv,
        [
            {
                "operation_id": "operation-1",
                "operator_entry_confirm_ok": "",
                "operator_entry_reject_reason": "",
                "reviewer": "",
                "reviewed_at": "",
                "vendor_name": "old",
                "amount_estimate": "old",
                "receiving_date": "old",
                "invoice_number": "old",
                "filename": "old",
                "pdf_path": "old",
                "pdf_exists": "NO",
            }
        ],
    )

    def raise_permission_error(path, rows):
        raise PermissionError("locked")

    monkeypatch.setattr(module, "write_csv", raise_permission_error)

    row_count = module.ensure_decision_input_template(source_csv, decision_csv)

    assert row_count == 1


def test_analyze_applies_repo_local_decision_input_without_source_write(tmp_path: Path) -> None:
    module = load_module()
    source_csv = tmp_path / "spot.csv"
    decision_csv = tmp_path / "decision.csv"
    write_csv(source_csv, [base_row(tmp_path, "")])
    write_csv(
        decision_csv,
        [
            {
                "operation_id": "operation-1",
                "operator_entry_confirm_ok": "OK",
                "operator_entry_reject_reason": "",
                "reviewer": "business-reviewer",
                "reviewed_at": "2026-06-21T12:00:00",
                "vendor_name": "テスト商事",
                "amount_estimate": "1234",
                "receiving_date": "20260131",
                "invoice_number": "T1234567890123",
                "filename": "sample.pdf",
                "pdf_path": str(tmp_path / "sample.pdf"),
                "pdf_exists": "YES",
            }
        ],
    )

    summary = module.analyze_spot_check(source_csv, decision_csv)
    source_rows_after = module.read_csv_rows(source_csv)

    assert summary.status == "READY_FOR_SHADOW_HANDOFF"
    assert summary.ok_count == 1
    assert summary.blank_count == 0
    assert summary.decision_overlay_applied_count == 1
    assert source_rows_after[0]["confirm_ok"] == ""


def test_analyze_rejects_invalid_decision_input_value(tmp_path: Path) -> None:
    module = load_module()
    source_csv = tmp_path / "spot.csv"
    decision_csv = tmp_path / "decision.csv"
    write_csv(source_csv, [base_row(tmp_path, "")])
    write_csv(
        decision_csv,
        [
            {
                "operation_id": "operation-1",
                "operator_entry_confirm_ok": "MAYBE",
                "operator_entry_reject_reason": "",
                "reviewer": "",
                "reviewed_at": "",
                "vendor_name": "テスト商事",
                "amount_estimate": "1234",
                "receiving_date": "20260131",
                "invoice_number": "T1234567890123",
                "filename": "sample.pdf",
                "pdf_path": str(tmp_path / "sample.pdf"),
                "pdf_exists": "YES",
            }
        ],
    )

    summary = module.analyze_spot_check(source_csv, decision_csv)

    assert summary.status == "HOLD_DECISION_INPUT_INVALID"
    assert summary.decision_overlay_invalid_count == 1


def test_analyze_rejects_row_ok_without_reviewer_fields(tmp_path: Path) -> None:
    module = load_module()
    source_csv = tmp_path / "spot.csv"
    decision_csv = tmp_path / "decision.csv"
    write_csv(source_csv, [base_row(tmp_path, "")])
    write_csv(
        decision_csv,
        [
            {
                "operation_id": "operation-1",
                "operator_entry_confirm_ok": "OK",
                "operator_entry_reject_reason": "",
                "reviewer": "",
                "reviewed_at": "",
                "vendor_name": "テスト商事",
                "amount_estimate": "1234",
                "receiving_date": "20260131",
                "invoice_number": "T1234567890123",
                "filename": "sample.pdf",
                "pdf_path": str(tmp_path / "sample.pdf"),
                "pdf_exists": "YES",
            }
        ],
    )

    summary = module.analyze_spot_check(source_csv, decision_csv)

    assert summary.status == "HOLD_DECISION_INPUT_INVALID"
    assert summary.ok_count == 0
    assert summary.decision_overlay_applied_count == 0
    assert summary.decision_overlay_invalid_count == 1
    assert "reviewer and reviewed_at" in summary.next_action


def test_analyze_rejects_row_ng_without_reject_reason(tmp_path: Path) -> None:
    module = load_module()
    source_csv = tmp_path / "spot.csv"
    decision_csv = tmp_path / "decision.csv"
    write_csv(source_csv, [base_row(tmp_path, "")])
    write_csv(
        decision_csv,
        [
            {
                "operation_id": "operation-1",
                "operator_entry_confirm_ok": "NG",
                "operator_entry_reject_reason": "",
                "reviewer": "business-reviewer",
                "reviewed_at": "2026-06-21T12:00:00",
                "vendor_name": "テスト商事",
                "amount_estimate": "1234",
                "receiving_date": "20260131",
                "invoice_number": "T1234567890123",
                "filename": "sample.pdf",
                "pdf_path": str(tmp_path / "sample.pdf"),
                "pdf_exists": "YES",
            }
        ],
    )

    summary = module.analyze_spot_check(source_csv, decision_csv)

    assert summary.status == "HOLD_DECISION_INPUT_INVALID"
    assert summary.ng_count == 0
    assert summary.decision_overlay_applied_count == 0
    assert summary.decision_overlay_invalid_count == 1
    assert "NG rows also require a reject reason" in summary.next_action


def test_analyze_ok_rows_builds_handoff_items(tmp_path: Path) -> None:
    module = load_module()
    csv_path = tmp_path / "spot.csv"
    write_csv(csv_path, [base_row(tmp_path, "OK")])

    summary = module.analyze_spot_check(csv_path)
    items = module.build_handoff_items(summary.ok_rows)

    assert summary.status == "READY_FOR_SHADOW_HANDOFF"
    assert summary.ready_for_shadow_handoff is True
    assert items[0]["vendor_name"] == "テスト商事"
    assert items[0]["amount"] == 1234
    assert items[0]["issue_date"] == "20260131"


def test_write_reports_generates_shadow_handoff_for_ok_rows(tmp_path: Path) -> None:
    module = load_module()
    csv_path = tmp_path / "spot.csv"
    out_dir = tmp_path / "out"
    write_csv(csv_path, [base_row(tmp_path, "OK")])

    summary = module.analyze_spot_check(csv_path)
    payload = module.write_reports(summary, out_dir)

    shadow = payload["shadow_handoff"]
    assert shadow["generated"] is True
    assert shadow["verified"] is True
    assert Path(shadow["data_file"]).exists()
    assert Path(shadow["latest_ready_file"]).exists()
    assert Path(payload["business_review_aid_csv"]).exists()
    assert payload["business_review_aid_row_count"] == 1


def test_write_reports_creates_priority_review_csvs_without_deciding(tmp_path: Path) -> None:
    module = load_module()
    csv_path = tmp_path / "spot.csv"
    out_dir = tmp_path / "out"
    quick_row = {
        **base_row(tmp_path, ""),
        "operation_id": "quick",
        "filename": "quick_vendor_202601_1234.pdf",
        "amount_estimate": "1234",
    }
    zero_row = {
        **base_row(tmp_path, ""),
        "operation_id": "zero",
        "filename": "zero_vendor_202601_1234.pdf",
        "amount_estimate": "0",
    }
    mismatch_row = {
        **base_row(tmp_path, ""),
        "operation_id": "mismatch",
        "filename": "mismatch_vendor_202601_2000.pdf",
        "amount_estimate": "1234",
    }
    write_csv(csv_path, [quick_row, zero_row, mismatch_row])

    summary = module.analyze_spot_check(csv_path)
    payload = module.write_reports(summary, out_dir)
    priority_rows = module.read_csv_rows(Path(payload["business_review_priority_csv"]))
    next_steps_md = Path(payload["business_review_next_steps_md"])

    assert [row["operation_id"] for row in priority_rows] == [
        "zero",
        "mismatch",
        "quick",
    ]
    assert payload["business_review_bucket_csvs"]["AMOUNT_ZERO_REVIEW"].endswith(
        "s44_review_01_amount_zero_review.csv"
    )
    assert Path(payload["business_review_bucket_csvs"]["AMOUNT_ZERO_REVIEW"]).exists()
    assert priority_rows[0]["operator_entry_confirm_ok"] == ""
    assert Path(payload["business_review_bucket_decision_input_csv"]).exists()
    assert payload["business_review_bucket_decision_input_row_count"] == 3
    assert next_steps_md.exists()
    next_steps_text = next_steps_md.read_text(encoding="utf-8")
    assert "Fastest Safe Input Path" in next_steps_text
    assert "AMOUNT_MATCH_QUICK_REVIEW" in next_steps_text
    assert "Review Order (fastest-to-unblock)" in next_steps_text
    assert next_steps_text.index("Quick amount-match rows") < next_steps_text.index(
        "High-risk zero amount rows"
    )
    assert "only reduces the first HOLD" in next_steps_text
    assert "cannot be bulk-marked `OK`" in next_steps_text
    assert "Minimum Inputs To Unblock" in next_steps_text
    assert "create `1` OK candidate(s)" in next_steps_text
    assert "leaves `2` risk row(s) held" in next_steps_text
    minimum_plan = payload["business_review_minimum_input_plan"]
    assert minimum_plan[0]["target"] == "AMOUNT_MATCH_QUICK_REVIEW bucket row"
    assert "Up to 1 row(s)" in minimum_plan[0]["ok_effect"]
    assert "Risk buckets cannot be bulk-approved" in minimum_plan[1]["ok_effect"]


def test_write_operator_next_steps_tolerates_locked_existing_file(tmp_path: Path, monkeypatch) -> None:
    module = load_module()
    next_steps_path = tmp_path / "s44_business_review_next_steps.md"
    next_steps_path.write_text("existing\n", encoding="utf-8")

    original_write_text = module.Path.write_text

    def raise_permission_error_for_canonical(self, *args, **kwargs):
        if self == next_steps_path:
            raise PermissionError("locked")
        return original_write_text(self, *args, **kwargs)

    monkeypatch.setattr(module.Path, "write_text", raise_permission_error_for_canonical)
    summary = module.SpotCheckSummary(
        generated_at="2026-06-21T10:00:00",
        source_csv="source.csv",
        source_exists=True,
        row_count=1,
        ok_count=0,
        ng_count=0,
        blank_count=1,
        invalid_ok_count=0,
        missing_pdf_count=0,
        decision_input_csv="decision.csv",
        decision_input_exists=True,
        decision_input_row_count=1,
        decision_input_sha256="",
        decision_overlay_applied_count=0,
        decision_overlay_invalid_count=0,
        bucket_decision_input_csv="bucket.csv",
        bucket_decision_input_exists=True,
        bucket_decision_input_row_count=1,
        bucket_decision_input_sha256="",
        bucket_decision_overlay_applied_count=0,
        bucket_decision_overlay_invalid_count=0,
        ready_for_shadow_handoff=False,
        status="HOLD_NO_OK_ROWS",
        next_action="review",
        ok_rows=[],
        pending_rows=[],
        invalid_ok_rows=[],
        missing_pdf_rows=[],
    )

    result = module.write_operator_next_steps_file(
        tmp_path,
        summary,
        tmp_path / "bucket.csv",
        tmp_path / "priority.csv",
        {},
        {},
    )

    locked_copy = Path(str(next_steps_path) + ".locked_copy")
    assert result == locked_copy
    assert "2026-06-21T10:00:00" in locked_copy.read_text(encoding="utf-8")
    assert Path(str(locked_copy) + ".numbered").exists()


def test_bucket_decision_template_groups_blank_review_buckets(tmp_path: Path) -> None:
    module = load_module()
    source_csv = tmp_path / "spot.csv"
    decision_csv = tmp_path / "decision.csv"
    bucket_decision_csv = tmp_path / "bucket_decision.csv"
    quick_a = {
        **base_row(tmp_path, ""),
        "operation_id": "quick-a",
        "filename": "quick_a_vendor_202601_1234.pdf",
    }
    quick_b = {
        **base_row(tmp_path, ""),
        "operation_id": "quick-b",
        "filename": "quick_b_vendor_202601_1234.pdf",
    }
    mismatch = {
        **base_row(tmp_path, ""),
        "operation_id": "mismatch",
        "filename": "mismatch_vendor_202601_2000.pdf",
    }
    write_csv(source_csv, [quick_a, quick_b, mismatch])
    write_csv(
        decision_csv,
        [
            {
                "operation_id": "quick-b",
                "operator_entry_confirm_ok": "OK",
                "operator_entry_reject_reason": "",
                "reviewer": "row-reviewer",
                "reviewed_at": "2026-06-21T10:00:00",
                "vendor_name": "テスト商事",
                "amount_estimate": "1234",
                "receiving_date": "20260131",
                "invoice_number": "T1234567890123",
                "filename": "quick_b_vendor_202601_1234.pdf",
                "pdf_path": str(tmp_path / "sample.pdf"),
                "pdf_exists": "YES",
            }
        ],
    )
    write_csv(
        bucket_decision_csv,
        [
            {
                "review_bucket": "AMOUNT_MATCH_QUICK_REVIEW",
                "bucket_decision": "OK",
                "bucket_reject_reason": "",
                "reviewer": "bucket-reviewer",
                "reviewed_at": "2026-06-21T11:00:00",
                "eligible_row_count": "old",
                "can_apply_ok": "old",
                "can_apply_ng": "old",
                "operator_next_action": "old",
                "allowed_scope": "old",
                "still_forbidden": "old",
            }
        ],
    )

    row_count = module.ensure_bucket_decision_input_template(
        source_csv,
        decision_csv,
        bucket_decision_csv,
    )
    rows = module.read_csv_rows(bucket_decision_csv)
    rows_by_bucket = {row["review_bucket"]: row for row in rows}

    assert row_count == 2
    assert rows_by_bucket["AMOUNT_MATCH_QUICK_REVIEW"]["eligible_row_count"] == "1"
    assert rows_by_bucket["AMOUNT_MATCH_QUICK_REVIEW"]["bucket_decision"] == "OK"
    assert rows_by_bucket["AMOUNT_MATCH_QUICK_REVIEW"]["can_apply_ok"] == "YES"
    assert rows_by_bucket["AMOUNT_MISMATCH_REVIEW"]["eligible_row_count"] == "1"
    assert rows_by_bucket["AMOUNT_MISMATCH_REVIEW"]["can_apply_ok"] == "NO"


def test_single_entry_input_syncs_bucket_ok_to_shadow_handoff(tmp_path: Path) -> None:
    module = load_module()
    source_csv = tmp_path / "spot.csv"
    decision_csv = tmp_path / "decision.csv"
    bucket_decision_csv = tmp_path / "bucket_decision.csv"
    single_entry_csv = tmp_path / "single_entry.csv"
    quick_row = {
        **base_row(tmp_path, ""),
        "operation_id": "quick",
        "filename": "quick_vendor_202601_1234.pdf",
    }
    write_csv(source_csv, [quick_row])

    module.ensure_decision_input_template(source_csv, decision_csv)
    module.ensure_bucket_decision_input_template(
        source_csv,
        decision_csv,
        bucket_decision_csv,
    )
    module.ensure_single_entry_input_template(
        source_csv,
        decision_csv,
        bucket_decision_csv,
        single_entry_csv,
    )
    single_rows = module.read_csv_rows(single_entry_csv)
    for row in single_rows:
        if row["entry_type"] == "BUCKET":
            row["decision"] = "OK"
            row["reviewer"] = "business-reviewer"
            row["reviewed_at"] = "2026-06-21T12:00:00"
    module.write_csv(
        single_entry_csv,
        single_rows,
        fieldnames=module.SINGLE_ENTRY_INPUT_FIELDS,
    )

    row_sync_count, bucket_sync_count = module.sync_single_entry_input_to_decision_inputs(
        single_entry_csv,
        decision_csv,
        bucket_decision_csv,
    )
    summary = module.analyze_spot_check(
        source_csv,
        decision_csv,
        bucket_decision_csv,
    )

    assert row_sync_count == 0
    assert bucket_sync_count == 1
    assert summary.status == "READY_FOR_SHADOW_HANDOFF"
    assert summary.ok_count == 1
    assert summary.bucket_decision_overlay_applied_count == 1


def test_write_reports_emits_single_entry_input_file(tmp_path: Path) -> None:
    module = load_module()
    source_csv = tmp_path / "spot.csv"
    out_dir = tmp_path / "out"
    quick_row = {
        **base_row(tmp_path, ""),
        "operation_id": "quick",
        "filename": "quick_vendor_202601_1234.pdf",
    }
    write_csv(source_csv, [quick_row])

    summary = module.analyze_spot_check(source_csv)
    payload = module.write_reports(summary, out_dir)

    single_entry_csv = Path(payload["business_review_single_entry_input_csv"])
    single_rows = module.read_csv_rows(single_entry_csv)
    assert single_entry_csv.exists()
    assert payload["business_review_single_entry_input_row_count"] == 2
    assert {row["entry_type"] for row in single_rows} == {"BUCKET", "ROW"}
    assert "single_entry_input_csv" in Path(
        payload["business_review_next_steps_md"]
    ).read_text(encoding="utf-8")


def test_analyze_applies_bucket_ok_only_for_quick_review_rows(tmp_path: Path) -> None:
    module = load_module()
    source_csv = tmp_path / "spot.csv"
    bucket_decision_csv = tmp_path / "bucket_decision.csv"
    quick_a = {
        **base_row(tmp_path, ""),
        "operation_id": "quick-a",
        "filename": "quick_a_vendor_202601_1234.pdf",
    }
    quick_b = {
        **base_row(tmp_path, ""),
        "operation_id": "quick-b",
        "filename": "quick_b_vendor_202601_1234.pdf",
    }
    write_csv(source_csv, [quick_a, quick_b])
    write_csv(
        bucket_decision_csv,
        [
            {
                "review_bucket": "AMOUNT_MATCH_QUICK_REVIEW",
                "bucket_decision": "OK",
                "bucket_reject_reason": "",
                "reviewer": "business-reviewer",
                "reviewed_at": "2026-06-21T11:00:00",
                "eligible_row_count": "2",
                "can_apply_ok": "YES",
                "can_apply_ng": "YES",
                "operator_next_action": "",
                "allowed_scope": "",
                "still_forbidden": "",
            }
        ],
    )

    summary = module.analyze_spot_check(source_csv, None, bucket_decision_csv)
    source_rows_after = module.read_csv_rows(source_csv)

    assert summary.status == "READY_FOR_SHADOW_HANDOFF"
    assert summary.ok_count == 2
    assert summary.blank_count == 0
    assert summary.bucket_decision_overlay_applied_count == 2
    assert summary.bucket_decision_overlay_invalid_count == 0
    assert source_rows_after[0]["confirm_ok"] == ""


def test_analyze_rejects_bucket_ok_for_amount_mismatch(tmp_path: Path) -> None:
    module = load_module()
    source_csv = tmp_path / "spot.csv"
    bucket_decision_csv = tmp_path / "bucket_decision.csv"
    mismatch = {
        **base_row(tmp_path, ""),
        "operation_id": "mismatch",
        "filename": "mismatch_vendor_202601_2000.pdf",
    }
    write_csv(source_csv, [mismatch])
    write_csv(
        bucket_decision_csv,
        [
            {
                "review_bucket": "AMOUNT_MISMATCH_REVIEW",
                "bucket_decision": "OK",
                "bucket_reject_reason": "",
                "reviewer": "business-reviewer",
                "reviewed_at": "2026-06-21T11:00:00",
                "eligible_row_count": "1",
                "can_apply_ok": "NO",
                "can_apply_ng": "YES",
                "operator_next_action": "",
                "allowed_scope": "",
                "still_forbidden": "",
            }
        ],
    )

    summary = module.analyze_spot_check(source_csv, None, bucket_decision_csv)

    assert summary.status == "HOLD_DECISION_INPUT_INVALID"
    assert summary.ok_count == 0
    assert summary.bucket_decision_overlay_applied_count == 0
    assert summary.bucket_decision_overlay_invalid_count == 1


def test_analyze_applies_bucket_ng_with_shared_reason(tmp_path: Path) -> None:
    module = load_module()
    source_csv = tmp_path / "spot.csv"
    bucket_decision_csv = tmp_path / "bucket_decision.csv"
    mismatch = {
        **base_row(tmp_path, ""),
        "operation_id": "mismatch",
        "filename": "mismatch_vendor_202601_2000.pdf",
    }
    write_csv(source_csv, [mismatch])
    write_csv(
        bucket_decision_csv,
        [
            {
                "review_bucket": "AMOUNT_MISMATCH_REVIEW",
                "bucket_decision": "NG",
                "bucket_reject_reason": "amount mismatch rejected as a bucket",
                "reviewer": "business-reviewer",
                "reviewed_at": "2026-06-21T11:00:00",
                "eligible_row_count": "1",
                "can_apply_ok": "NO",
                "can_apply_ng": "YES",
                "operator_next_action": "",
                "allowed_scope": "",
                "still_forbidden": "",
            }
        ],
    )

    summary = module.analyze_spot_check(source_csv, None, bucket_decision_csv)

    assert summary.status == "HOLD_NO_OK_ROWS"
    assert summary.ng_count == 1
    assert summary.blank_count == 0
    assert summary.bucket_decision_overlay_applied_count == 1
    assert summary.pending_rows[0]["reject_reason"] == "amount mismatch rejected as a bucket"
