import csv
import importlib.util
import json
import sys
from pathlib import Path

MATCHING_LOG_FILENAME = "s44_final_log_20260620_134500.txt"


def load_module():
    repo_root = Path(__file__).parent.parent
    tools_dir = repo_root / "tools"
    module_path = tools_dir / "sync_bundle_evidence_intake_20260620.py"
    sys.path.insert(0, str(tools_dir))
    spec = importlib.util.spec_from_file_location("sync_bundle_evidence_intake_20260620", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_pack(tmp_path: Path, bundle: str = "BUSINESS_REVIEW_BUNDLE") -> dict:
    pack_dir = tmp_path / "pack" / bundle.lower()
    final_dir = pack_dir / "final_evidence"
    final_dir.mkdir(parents=True, exist_ok=True)
    intake_path = pack_dir / "final_evidence_intake.csv"
    filename_template_path = pack_dir / "operator_evidence_filename_template.csv"
    filename_template_path.write_text(
        "\n".join(
            [
                "bundle,scenario,template_only_not_final_evidence,save_under_folder,evidence_kind,example_filename,purpose,notes",
                f"{bundle},44,YES,{final_dir / 'scenario_44'},log,s44_final_log_YYYYMMDD_HHMMSS.txt,Safe log,Template only",
            ]
        )
        + "\n",
        encoding="utf-8-sig",
    )
    return {
        "bundle": bundle,
        "scenarios": "44",
        "scenario_count": 1,
        "pack_dir": str(pack_dir),
        "intake_path": str(intake_path),
        "filename_template_path": str(filename_template_path),
        "final_evidence_dir": str(final_dir),
    }


def base_intake_row(bundle: str, scenario: str, evidence_path: Path) -> dict[str, str]:
    return {
        "bundle": bundle,
        "scenario": scenario,
        "required_final_evidence": "final log",
        "current_reference_evidence": "",
        "final_evidence_path": str(evidence_path),
        "operator_result": "OK",
        "reviewer": "field-user",
        "reviewed_at": "2026-06-20T13:45:00",
        "rakuraku_customer_login_used": "",
        "temporary_save_created": "",
        "created_data_cleanup_status": "",
        "created_data_cleanup_evidence_path": "",
        "cleanup_reviewer": "",
        "cleanup_reviewed_at": "",
        "notes": "",
    }


def test_build_bundle_sync_approves_when_intake_evidence_is_inside_final_dir(tmp_path: Path) -> None:
    module = load_module()
    pack = build_pack(tmp_path)
    evidence_file = Path(pack["final_evidence_dir"]) / MATCHING_LOG_FILENAME
    evidence_file.write_text("ok", encoding="utf-8")
    write_csv(
        Path(pack["intake_path"]),
        [base_intake_row(pack["bundle"], "44", evidence_file)],
    )

    result = module.build_bundle_sync(pack)

    assert result.ready_to_sync is True
    assert result.operator_result == "OK"
    assert result.evidence_path == str(evidence_file)
    assert result.reviewer == "field-user"
    assert result.reviewed_at == "2026-06-20T13:45:00"


def test_build_bundle_sync_blocks_filename_template_mismatch(tmp_path: Path) -> None:
    module = load_module()
    pack = build_pack(tmp_path)
    evidence_file = Path(pack["final_evidence_dir"]) / "run_log.txt"
    evidence_file.write_text("ok", encoding="utf-8")
    write_csv(
        Path(pack["intake_path"]),
        [base_intake_row(pack["bundle"], "44", evidence_file)],
    )

    result = module.build_bundle_sync(pack)

    assert result.ready_to_sync is False
    assert "FILENAME_TEMPLATE_MISMATCH" in result.blockers
    assert result.rows[0].final_evidence_filename_issue == "FILENAME_TEMPLATE_MISMATCH"
    assert result.rows[0].final_evidence_filename_mismatches == "run_log.txt"


def test_build_bundle_sync_blocks_missing_evidence_file(tmp_path: Path) -> None:
    module = load_module()
    pack = build_pack(tmp_path)
    missing_file = Path(pack["final_evidence_dir"]) / "missing.txt"
    write_csv(
        Path(pack["intake_path"]),
        [base_intake_row(pack["bundle"], "44", missing_file)],
    )

    result = module.build_bundle_sync(pack)

    assert result.ready_to_sync is False
    assert "FINAL_EVIDENCE_NOT_FOUND" in result.blockers


def test_build_bundle_sync_allows_supplemental_intake_rows_when_ready(tmp_path: Path) -> None:
    module = load_module()
    pack = build_pack(tmp_path)
    final_dir = Path(pack["final_evidence_dir"])
    template_path = Path(pack["filename_template_path"])
    with template_path.open("a", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                pack["bundle"],
                "47",
                "YES",
                str(final_dir / "scenario_47"),
                "log",
                "scenario_47_safe_stop_latest_clean_log_YYYYMMDD_HHMMSS.txt",
                "Safe-stop runtime latest clean log",
                "Template only",
            ]
        )
    scenario_44_file = final_dir / MATCHING_LOG_FILENAME
    scenario_47_dir = final_dir / "scenario_47"
    scenario_47_dir.mkdir()
    scenario_47_file = scenario_47_dir / "scenario_47_safe_stop_latest_clean_log_20260621_120000.txt"
    scenario_44_file.write_text("ok", encoding="utf-8")
    scenario_47_file.write_text("ok", encoding="utf-8")
    write_csv(
        Path(pack["intake_path"]),
        [
            base_intake_row(pack["bundle"], "44", scenario_44_file),
            base_intake_row(pack["bundle"], "47", scenario_47_file),
        ],
    )

    result = module.build_bundle_sync(pack)

    assert result.ready_to_sync is True
    assert "INTAKE_ROW_COUNT_MISMATCH" not in result.blockers
    assert result.ready_row_count == 2
    assert result.evidence_path == str(final_dir)


def test_build_bundle_sync_does_not_require_cleanup_evidence_when_temp_save_created(tmp_path: Path) -> None:
    module = load_module()
    pack = build_pack(tmp_path)
    evidence_file = Path(pack["final_evidence_dir"]) / MATCHING_LOG_FILENAME
    evidence_file.write_text("ok", encoding="utf-8")
    row = base_intake_row(pack["bundle"], "44", evidence_file)
    row["temporary_save_created"] = "YES"
    row["created_data_cleanup_status"] = "削除済"
    write_csv(Path(pack["intake_path"]), [row])

    result = module.build_bundle_sync(pack)

    assert result.ready_to_sync is True
    assert "CLEANUP_EVIDENCE_PATH_BLANK" not in result.blockers
    assert result.created_data_cleanup_status == "削除済"
    assert result.created_data_cleanup_evidence_path == ""


def test_sync_operator_sheet_updates_ready_bundle_and_clears_stale_blocked_bundle(tmp_path: Path) -> None:
    module = load_module()
    ready_pack = build_pack(tmp_path, "BUSINESS_REVIEW_BUNDLE")
    ready_evidence = Path(ready_pack["final_evidence_dir"]) / MATCHING_LOG_FILENAME
    ready_evidence.write_text("ok", encoding="utf-8")
    write_csv(
        Path(ready_pack["intake_path"]),
        [base_intake_row(ready_pack["bundle"], "44", ready_evidence)],
    )
    blocked_pack = build_pack(tmp_path, "PAYMENT_APPROVAL_BUNDLE")
    blocked_missing = Path(blocked_pack["final_evidence_dir"]) / "missing.txt"
    write_csv(
        Path(blocked_pack["intake_path"]),
        [base_intake_row(blocked_pack["bundle"], "70", blocked_missing)],
    )
    pack_json = tmp_path / "bundle_evidence_packs.json"
    pack_json.write_text(
        json.dumps({"packs": [ready_pack, blocked_pack]}, ensure_ascii=False),
        encoding="utf-8",
    )
    operator_sheet = tmp_path / "bundle_operator_sheet.csv"
    write_csv(
        operator_sheet,
        [
            {
                "bundle": "BUSINESS_REVIEW_BUNDLE",
                "owner": "業務担当者",
                "scenarios": "44",
                "scenario_count": "1",
                "approval_scope": "",
                "allowed_operations": "",
                "evidence_to_capture": "",
                "hard_stops": "",
                "packet_csv_path": "",
                "prepared_evidence_pack_path": "",
                "operator_result": "",
                "evidence_path": "",
                "reviewer": "",
                "reviewed_at": "",
                "rakuraku_customer_login_used": "",
                "temporary_save_created": "",
                "created_data_cleanup_status": "",
                "created_data_cleanup_evidence_path": "",
                "cleanup_reviewer": "",
                "cleanup_reviewed_at": "",
                "notes": "",
            },
            {
                "bundle": "PAYMENT_APPROVAL_BUNDLE",
                "owner": "支払承認者",
                "scenarios": "70",
                "scenario_count": "1",
                "approval_scope": "",
                "allowed_operations": "",
                "evidence_to_capture": "",
                "hard_stops": "",
                "packet_csv_path": "",
                "prepared_evidence_pack_path": "",
                "operator_result": "OK",
                "evidence_path": str(blocked_missing),
                "reviewer": "stale-user",
                "reviewed_at": "2026-06-20T13:45:00",
                "rakuraku_customer_login_used": "",
                "temporary_save_created": "",
                "created_data_cleanup_status": "",
                "created_data_cleanup_evidence_path": "",
                "cleanup_reviewer": "",
                "cleanup_reviewed_at": "",
                "notes": "",
            },
        ],
    )

    payload = module.build_payload(pack_json, operator_sheet, apply_updates=True)

    with operator_sheet.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = {row["bundle"]: row for row in csv.DictReader(handle)}
    assert payload["ready_to_sync_count"] == 1
    assert payload["updated_bundle_count"] == 2
    assert rows["BUSINESS_REVIEW_BUNDLE"]["operator_result"] == "OK"
    assert rows["BUSINESS_REVIEW_BUNDLE"]["evidence_path"] == str(ready_evidence)
    assert rows["PAYMENT_APPROVAL_BUNDLE"]["operator_result"] == ""
    assert rows["PAYMENT_APPROVAL_BUNDLE"]["evidence_path"] == ""
    assert rows["PAYMENT_APPROVAL_BUNDLE"]["reviewer"] == ""
    assert rows["PAYMENT_APPROVAL_BUNDLE"]["reviewed_at"] == ""
    assert module.STALE_CLEAR_NOTE in rows["PAYMENT_APPROVAL_BUNDLE"]["notes"]
